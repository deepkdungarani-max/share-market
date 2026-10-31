"""Download NSE and rupee-pair candles from Yahoo Finance into the local DB (a pair's daily candles are built
from its hourly ones: see forex_daily).

Usage: python -m app.fetch [15m|1h|1d ...]
"""
import math
import sys
import time
import warnings

import pandas as pd
import yfinance as yf

from .config import FOREX, INTERVALS, TICKERS
from .db import connect

# yfinance still uses pandas' deprecated inplace= API; the warnings drown the real output.
warnings.filterwarnings("ignore", module="yfinance")
warnings.filterwarnings("ignore", message=".*inplace keyword.*")


def ticker_for(symbol: str) -> str:
    return TICKERS.get(symbol, f"{symbol}.NS")


def download(ticker: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False, threads=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    df.index = pd.to_datetime(df.index, utc=True)
    return df


FX_DAY_SHIFT = pd.Timedelta(hours=2)  # a forex day runs 22:00 to 22:00 UTC: New York's 5 PM, the market's own close


def forex_daily(ticker: str, period: str) -> pd.DataFrame:
    """A rupee pair's daily candles, built from its hourly ones. Yahoo's daily forex bars can't be used: their
    close is the day's opening rate while their high and low span the whole day, so they give the day's move
    away (a model reached a false 79% on them). A day runs 22:00 to 22:00 UTC (05:30 to 03:30 IST) and is
    dated by the UTC day it ends on, so Sunday evening's first hours count to Monday. Yahoo keeps 730 days of
    hourly bars, so that is as far back as these go; the DB keeps every day once fetched."""
    hourly = download(ticker, "1h", {"max": "730d"}.get(period, period))
    if hourly.empty:
        return hourly
    days = hourly.groupby((hourly.index + FX_DAY_SHIFT).normalize())
    daily = pd.DataFrame({"open": days["open"].first(), "high": days["high"].max(), "low": days["low"].min(),
                          "close": days["close"].last(), "volume": days["volume"].sum()})
    return daily[daily.index.dayofweek < 5]  # Friday's trickle after the close would make a Saturday stub


def save(conn, symbol: str, interval: str, df: pd.DataFrame) -> int:
    rows = [
        (symbol, interval, int(ts.value // 1_000_000), r.open, r.high, r.low, r.close, float(r.volume or 0))
        for ts, r in zip(df.index, df.itertuples(index=False))
    ]
    before = conn.total_changes
    # Upsert: the still-forming candle is saved mid-session and must be overwritten once it closes.
    conn.executemany(
        """INSERT INTO candles VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(symbol, interval, ts) DO UPDATE SET
             open=excluded.open, high=excluded.high, low=excluded.low,
             close=excluded.close, volume=excluded.volume""",
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def refresh(conn, symbol: str, interval: str, period: str | None = None) -> int:
    period = period or INTERVALS[interval]
    if interval == "1d" and symbol in FOREX:
        df = forex_daily(ticker_for(symbol), period)
    else:
        df = download(ticker_for(symbol), interval, period)
    return save(conn, symbol, interval, df) if not df.empty else 0


KEPT_DAYS = {"15m": 59, "1h": 729}  # how far back Yahoo serves each intraday interval


def catch_up(conn, symbol: str, interval: str) -> int:
    """Download everything newer than the last candle the DB has, however long the gap (the server off, the
    laptop asleep for days), within what Yahoo keeps. Without any candle yet, the full history."""
    last = conn.execute("SELECT MAX(ts) FROM candles WHERE symbol = ? AND interval = ?", (symbol, interval)).fetchone()[0]
    if last is None:
        return refresh(conn, symbol, interval)
    days = math.ceil((time.time() * 1000 - last) / 86_400_000) + 2  # the last candle itself may have been forming
    return refresh(conn, symbol, interval, f"{max(5, min(days, KEPT_DAYS.get(interval, days)))}d")


def main(intervals: list[str]) -> None:
    conn = connect()
    for interval in intervals:
        for symbol in TICKERS:
            try:
                saved = refresh(conn, symbol, interval)
            except Exception as e:  # one bad ticker must not stop the rest
                print(f"[{interval}] {symbol:<11} FAILED: {e}")
                continue
            print(f"[{interval}] {symbol:<11} {saved:>6} candles saved")
    total = conn.execute("SELECT interval, COUNT(*) FROM candles GROUP BY interval").fetchall()
    print("DB totals:", dict(total))
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:] or list(INTERVALS))
