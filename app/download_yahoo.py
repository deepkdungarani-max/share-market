"""Download what Yahoo Finance keeps for every company listed on NSE (+ the main indices):
1-minute bars (~30 days), 15-minute (~60 days), 1-hour (~2 years) and daily (since listing).

Yahoo keeps only a rolling window of intraday bars, so run this regularly: 1-minute bars older
than ~30 days are gone for good. Resumable and incremental: a symbol/interval already fetched
today is skipped, and later runs only fetch bars newer than what the DB has.

Usage: python -m app.download_yahoo [1m 15m 1h 1d]
"""
import csv
import io
import sys
import time
import urllib.request
import warnings
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError, YFTickerMissingError, YFTzMissingError

from .config import FOREX
from .market_db import connect
from .system import keep_awake, logger, progress, single_instance

warnings.filterwarnings("ignore")  # after importing yfinance, which floods pandas deprecation warnings

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
LISTS = {
    "main": "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    "sme": "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv",
}
INDICES = ["^NSEI", "^NSEBANK", "^INDIAVIX", "^BSESN", "^CRSLDX", "^NSMIDCP", "^CNXIT", "^CNXAUTO", "^CNXFMCG",
           "^CNXPHARMA", "^CNXMETAL", "^CNXREALTY", "^CNXENERGY", "^CNXPSUBANK", "^CNXMEDIA", "^CNXINFRA"]
# interval: (how many days back Yahoo serves it, most days it returns per request)
LIMITS = {"1m": (29, 7), "15m": (59, 59), "1h": (729, 729)}
ORDER = ["1m", "15m", "1h", "1d"]  # shortest-lived first: 1-minute bars vanish after ~30 days
DELAY = 0.3                       # seconds between requests
IST = timezone(timedelta(hours=5, minutes=30))

say = logger("yahoo")

class YahooDown(Exception):
    """Yahoo keeps refusing this request even after waiting."""


def iso_date(v: str) -> str | None:
    for fmt in ("%d-%b-%Y", "%d-%b-%y"):  # main board: 06-OCT-2008, SME: 22-Oct-26
        try:
            return datetime.strptime(v.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def listed_symbols(conn) -> list[str]:
    """Every company listed on NSE today (main board + SME), refreshed into nse_listed."""
    for board, url in LISTS.items():
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
        except Exception as e:
            say(f"Couldn't fetch the {board} list ({e}) — using the symbols already in the DB")
            continue
        rows = [{k.strip().replace("_", " ").upper(): (v or "").strip() for k, v in r.items() if k}
                for r in csv.DictReader(io.StringIO(raw))]
        with conn:
            conn.executemany("INSERT OR REPLACE INTO nse_listed VALUES (?,?,?,?,?,?)", [
                (r["SYMBOL"], r.get("NAME OF COMPANY"), r.get("SERIES"), iso_date(r.get("DATE OF LISTING", "")),
                 r.get("ISIN NUMBER"), board)
                for r in rows if r.get("SYMBOL")])
    return [r[0] for r in conn.execute("SELECT symbol FROM nse_listed ORDER BY symbol")]


def history(ticker: str, interval: str, start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
    """Bars from Yahoo; empty when Yahoo has none. Waits out rate limits."""
    kw = {"interval": interval, "auto_adjust": False, "actions": interval == "1d", "raise_errors": True}
    kw.update({"period": "max"} if start is None else {"start": start, "end": end})
    for attempt in range(1, 6):
        try:
            return yf.Ticker(ticker).history(**kw)
        except (YFPricesMissingError, YFTickerMissingError, YFTzMissingError):
            return pd.DataFrame()
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            # yfinance chokes on some thinly traded tickers (e.g. KeyError 'tradingPeriods'): no usable data
            return pd.DataFrame()
        except YFRateLimitError:
            say(f"  Yahoo rate limit — pausing {2 * attempt} min")
            time.sleep(120 * attempt)
        except Exception as e:  # network hiccups
            say(f"  {ticker} {interval}: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(10 * attempt)
    raise YahooDown(f"{ticker} {interval}")


def save_intraday(conn, symbol: str, interval: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = [(symbol, interval, int(ts.value // 1_000_000), float(o), float(h), float(lo), float(c), int(v) if v == v else None)
            for ts, o, h, lo, c, v in zip(df.index.tz_convert("UTC"), df["Open"], df["High"], df["Low"], df["Close"], df["Volume"])
            if c == c]  # skip Yahoo's empty (NaN) bars
    conn.executemany("INSERT OR REPLACE INTO yahoo_intraday VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def save_daily(conn, symbol: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    zero = pd.Series(0.0, index=df.index)
    adj = df["Adj Close"] if "Adj Close" in df else df["Close"]
    rows = [(symbol, ts.date().isoformat(), float(o), float(h), float(lo), float(c), float(a), int(v) if v == v else None, float(dv), float(sp))
            for ts, o, h, lo, c, a, v, dv, sp in zip(df.index, df["Open"], df["High"], df["Low"], df["Close"], adj, df["Volume"],
                                                    df.get("Dividends", zero), df.get("Stock Splits", zero))
            if c == c]
    conn.executemany("INSERT OR REPLACE INTO yahoo_daily VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def fetch(conn, symbol: str, interval: str, now: datetime) -> int:
    """Fetch only what the DB doesn't have yet; returns rows saved."""
    ticker = FOREX.get(symbol) or (symbol if symbol.startswith("^") else f"{symbol}.NS")
    if interval == "1d":
        last = conn.execute("SELECT MAX(date) FROM yahoo_daily WHERE symbol=?", (symbol,)).fetchone()[0]
        if last is None:
            df = history(ticker, "1d")
        else:
            df = history(ticker, "1d", datetime.fromisoformat(last).replace(tzinfo=timezone.utc) - timedelta(days=7), now + timedelta(days=1))
        with conn:
            return save_daily(conn, symbol, df)

    back, span = LIMITS[interval]
    start = now - timedelta(days=back)
    last = conn.execute("SELECT MAX(ts) FROM yahoo_intraday WHERE symbol=? AND interval=?", (symbol, interval)).fetchone()[0]
    if last is not None:
        start = max(start, datetime.fromtimestamp(last / 1000, timezone.utc) - timedelta(days=1))
    saved = 0
    while start < now:
        end = min(start + timedelta(days=span), now)
        df = history(ticker, interval, start, end)
        with conn:
            saved += save_intraday(conn, symbol, interval, df)
        start = end
        time.sleep(DELAY)
    return saved


def main(intervals: list[str]) -> int:
    """Exit codes for the data keeper (app/keeper.py): 0 done, 2 Yahoo kept refusing, 3 already running."""
    unknown = set(intervals) - set(ORDER)
    if unknown:
        raise SystemExit(f"Unknown interval(s) {sorted(unknown)} — use any of {ORDER}")
    if not single_instance("download_yahoo"):
        say("another Yahoo download is already running")
        return 3
    keep_awake()
    conn = connect()
    stocks = listed_symbols(conn) + INDICES
    today = datetime.now(IST).date().isoformat()
    say(f"{len(stocks):,} symbols and {len(FOREX)} rupee pairs, intervals {intervals}")

    refusals = 0
    for interval in [i for i in ORDER if i in intervals]:
        # The rupee pairs' intraday bars too (their 1-minute ones vanish like everyone's). Not their daily ones:
        # Yahoo's daily forex bars give the day away (see fetch.forex_daily), and trading.db builds its own.
        symbols = stocks + (list(FOREX) if interval != "1d" else [])
        done = {r[0] for r in conn.execute("SELECT symbol FROM yahoo_jobs WHERE interval=? AND run_date=?", (interval, today))}
        todo = [s for s in symbols if s not in done]
        say(f"[{interval}] {len(todo):,} to fetch ({len(done):,} already done today)")
        started, saved = time.time(), 0
        progress("Yahoo", interval, 0, len(todo), started)
        for i, symbol in enumerate(todo, 1):
            try:
                n = fetch(conn, symbol, interval, datetime.now(timezone.utc))
            except YahooDown as e:
                refusals += 1
                say(f"  gave up on {e} for now")
                if refusals >= 3:
                    say("STOPPED: Yahoo keeps refusing. Run again later — it resumes from here.")
                    return 2
                continue
            refusals = 0
            saved += n
            with conn:
                conn.execute("INSERT OR REPLACE INTO yahoo_jobs VALUES (?,?,?,?,?)", (symbol, interval, "ok" if n else "nodata", n, today))
            if i % 20 == 0 or i == len(todo):
                progress("Yahoo", interval, i, len(todo), started)
            if i % 100 == 0 or i == len(todo):
                left = (len(todo) - i) * (time.time() - started) / i / 60
                say(f"[{interval}] {i:,}/{len(todo):,}  {symbol}  rows {saved:,}  ~{left:.0f} min left")
            time.sleep(DELAY)

    intraday = dict(conn.execute("SELECT interval, COUNT(*) FROM yahoo_intraday GROUP BY interval").fetchall())
    daily = conn.execute("SELECT COUNT(*) FROM yahoo_daily").fetchone()[0]
    say(f"Done. yahoo_intraday rows: {intraday}  yahoo_daily rows: {daily:,}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ORDER))
