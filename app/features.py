import numpy as np
import pandas as pd

FEATURES = [
    "ret_1", "ret_3", "ret_6", "ret_12",
    "rsi_14", "macd_hist", "ema_9_21", "close_ema_21",
    "vol_ratio", "range", "body", "upper_wick", "lower_wick",
    "volatility_12", "minute_of_day", "dow",
]


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
    gain = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def build(candles: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Candles for ONE symbol + interval, sorted by ts. Adds scale-free features and the label.

    label = 1 if the NEXT candle closes above this candle's close (intraday: same trading day only).
    """
    df = candles.copy()
    c = df["close"]
    ist = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert("Asia/Kolkata")

    for n in (1, 3, 6, 12):
        df[f"ret_{n}"] = c.pct_change(n)
    df["rsi_14"] = _rsi(c)
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    df["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / c
    ema9, ema21 = c.ewm(span=9, adjust=False).mean(), c.ewm(span=21, adjust=False).mean()
    df["ema_9_21"] = ema9 / ema21 - 1
    df["close_ema_21"] = c / ema21 - 1
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    df["range"] = (df["high"] - df["low"]) / c
    df["body"] = (c - df["open"]) / c
    df["upper_wick"] = (df["high"] - df[["open", "close"]].max(axis=1)) / c
    df["lower_wick"] = (df[["open", "close"]].min(axis=1) - df["low"]) / c
    df["volatility_12"] = df["ret_1"].rolling(12).std()
    df["minute_of_day"] = ist.dt.hour * 60 + ist.dt.minute
    df["dow"] = ist.dt.dayofweek

    next_close = c.shift(-1)
    # Daily bars: the next candle is always the next session
    same_day = next_close.notna() if interval == "1d" else ist.dt.date == ist.shift(-1).dt.date
    # An unchanged next close has no direction: left unlabelled, it is neither trained on nor scored. Counted
    # as "down" it handed out free points, most of all on the rupee pairs' flat night hours (8% of 15m bars).
    direction = np.where(next_close > c, 1.0, np.where(next_close < c, 0.0, np.nan))
    df["label"] = np.where(same_day & next_close.notna(), direction, np.nan)
    df["next_ret"] = np.where(same_day, next_close / c - 1, np.nan)
    df["date"] = ist.dt.date

    # Index has no volume -> vol_ratio is meaningless there.
    df["vol_ratio"] = df["vol_ratio"].replace([np.inf, -np.inf], np.nan)
    return df
