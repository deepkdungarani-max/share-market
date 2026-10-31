"""Sanjay on the whole market: a one-year out-of-sample test of a daily model trained on every NSE company since 1994.

Pick a cutoff a year back. The model learns from every session before it, then calls every company's next
session, every day of the year after it, and those calls are checked against what happened. It never sees the
year it is tested on, so the result is what the model would really have done.

Data is NSE's own bhavcopy (market.db nse_bhav): every security, delisted ones too, so the test doesn't flatter
itself with only today's survivors. Prices there aren't adjusted for splits and bonuses. Returns are close /
prev_close, which NSE adjusts on most ex-dates, and every price feature is built from those returns; a day's move
beyond -35% or +80% is a split or bonus it left unadjusted, and counts as no move. A row is one company on one session (the EQ series when it traded in several). ETFs and fund units,
which trade in the EQ series too, are left out by their ISIN.

Features (all known at that session's close): returns over 1-250 sessions, RSI, MACD, moving averages and
volatility of the return-built price, the candle's shape, volume against its 20-day average, the company's
turnover rank that day, weekday, and the market that day (median return and breadth across all companies).
The label is whether the next session closes up. An unchanged close is called but not scored, and a company
that doesn't trade on the next session isn't called.

How long to train is picked on the last year before the cutoff (learning from the years before it), then the
model trains again on everything before the cutoff.

Usage: python -m app.backtest [cutoff YYYY-MM-DD]   (default: a year before the last session in market.db)
Results go to E:/candlecast-data/backtest.db (runs, days, predictions) for the website's Backtest page.
"""
import json
import math
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .config import MARKET_DB_PATH, MARKET_DIR, ROOT
from .system import keep_awake, locked, logger, single_instance

SERIES = ("EQ", "BE", "BZ", "SM", "ST")
PRICES = ("open", "high", "low", "close", "prev_close", "volume", "value")
FEATURES = ["ret_1", "ret_3", "ret_6", "ret_12", "ret_60", "ret_250", "rsi_14", "macd_hist", "ema_9_21",
            "close_ema_21", "volatility_12", "range", "body", "upper_wick", "lower_wick", "vol_ratio", "liquidity",
            "dow", "mkt_ret", "breadth", "rel_1"]
READY = ["ret_12", "rsi_14", "volatility_12", "vol_ratio"]  # a company needs about a month of history to be called
PARAMS = dict(objective="binary", metric="auc", learning_rate=0.05, num_leaves=31, min_data_in_leaf=2000,
              feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0, verbose=-1)
MAX_ROUNDS = 1000
PATIENCE = 50
CONF = 0.05      # a confident call: prob_up at least 0.55 or at most 0.45
LIQUID = 5e7     # ₹5 crore average daily turnover: companies a trader can really buy and sell
TOP = 10         # the model's top and bottom picks each day, among the liquid companies
RETRAINS = {"once": 0, "quarter": 3, "month": 1}  # months between fresh models in the test year; 0: one model
HISTORY = {"all": 0, "10y": 10, "5y": 5}  # years of sessions each model learns from; 0: everything since 1994
COST = 0.0025    # a delivery round trip in India: STT 0.1% each way, stamp duty, exchange fees, GST, DP charge
JUMP_DOWN, JUMP_UP = -0.35, 0.8  # a day's move beyond these is an unadjusted split, bonus or consolidation
CHUNK = 1_000_000
DB = MARKET_DIR / "backtest.db"
SNAPSHOT = Path(tempfile.gettempdir()) / "candlecast-market-snapshot.db"  # on the local SSD, deleted after loading
PAUSES = MARKET_DIR / "backtest-pauses.json"  # {"run": id, "pauses": [[from, to], ...]}: the website's Pause
AUTO = MARKET_DIR / "backtest-auto.json"  # the website's Auto run: on, step, runs left, settings, what it did last
STEPS = {"session": pd.DateOffset(days=1), "week": pd.DateOffset(days=7), "month": pd.DateOffset(months=1)}

say = logger("backtest")
LOG = MARKET_DIR / "logs" / "backtest.log"
LOG_LINE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (.*)$")
# A run's stages for the website: the log line each starts with (written by run's step), and how long each took
# on this laptop, for timing a run before any has finished
STAGES = [
    ("load", "Copy market.db to the SSD and read every session since 1994", r"run #\d+: loading the bhavcopy", 380),
    ("features", "Build the features", r"Building features", 100),
    ("probe", "Find how long to train, on the year before the cutoff", r"Finding how long to train", 260),
    ("train", "Train on everything before the cutoff, and again through the year if asked", r"Training on all", 210),
    ("call", "Call every company, every session after the cutoff", r"Calling every company", 10),
    ("score", "Score the calls and save them to backtest.db", r"Scoring the calls", 90),
    ("report", "Write the report: against the last run, why calls failed or worked", r"Writing the report", 15),
]
# The numbers in those lines
FACTS = {"features": (r"([\d,]+) company-sessions of ([\d,]+) companies", ("rows", "companies")),
         "probe": (r"learning ([\d,]+) rows, checking on the ([\d,]+)(?:.*?then (\d+) models?)?",
                   ("fit_rows", "check_rows", "models")),
         "train": (r"all ([\d,]+) company-sessions .*\((\d+) rounds\)", ("train_rows", "rounds")),
         "call": (r": ([\d,]+) calls", ("calls",))}


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB, timeout=60)
    # WAL: the website keeps reading while a run saves its ~750k calls, and the save is one sequential append on
    # the USB disk; a big page cache keeps the index's scattered pages in memory until the commit
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA cache_size=-200000")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, cutoff TEXT, started_at TEXT,
            finished_at TEXT, status TEXT, step TEXT, metrics TEXT, report TEXT);
        CREATE TABLE IF NOT EXISTS days (run INTEGER, date TEXT, calls INTEGER, scored INTEGER, hits INTEGER,
            ups INTEGER, auc REAL, top_ret REAL, bottom_ret REAL, liquid_ret REAL,
            PRIMARY KEY (run, date)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS predictions (run INTEGER, date TEXT, symbol TEXT, prob_up REAL, close REAL,
            next_close REAL, next_ret REAL, avg_value REAL, locked INTEGER, day_ret REAL,
            PRIMARY KEY (run, date, symbol)) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS predictions_symbol ON predictions (run, symbol, date);
        CREATE TABLE IF NOT EXISTS companies (run INTEGER, symbol TEXT, name TEXT, calls INTEGER, scored INTEGER,
            hits INTEGER, ups INTEGER, said_up INTEGER, avg_value REAL, PRIMARY KEY (run, symbol)) WITHOUT ROWID;""")
    for table, column, kind in (("predictions", "locked", "INTEGER"), ("predictions", "day_ret", "REAL"),
                                ("runs", "report", "TEXT")):  # columns added after the first runs
        if column not in {c[1] for c in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
    return db


def load() -> pd.DataFrame:
    """One row per company per session from the bhavcopy, sorted by company then day (yyyymmdd ints).

    market.db sits on a USB hard disk and the bhavcopy's rows are scattered over it (each day's rows land on
    thousands of pages), so reading the table straight costs a disk seek per page: most of an hour. Copying the
    file page by page to the local SSD is one sweep of the disk, and the scan then runs from the SSD."""
    marks = ",".join("?" * len(SERIES))
    clean = lambda: [Path(f"{SNAPSHOT}{extra}").unlink(missing_ok=True) for extra in ("", "-journal", "-wal", "-shm")]
    clean()  # a copy left by a run that was killed
    src = sqlite3.connect(f"file:{MARKET_DB_PATH.as_posix()}?mode=ro", uri=True, timeout=600)
    conn = sqlite3.connect(SNAPSHOT)
    try:
        src.backup(conn)  # one step, so the copy is consistent while the downloads keep writing
        src.close()
        symbols = [s for (s,) in conn.execute(f"SELECT DISTINCT symbol FROM nse_bhav WHERE series IN ({marks})", SERIES)]
        parts = []
        for chunk in pd.read_sql(f"SELECT CAST(replace(date, '-', '') AS INTEGER) AS day, symbol, "
                                 f"series <> 'EQ' AS other, ifnull(isin LIKE 'INE%', 0) AS share, "
                                 f"isin IS NOT NULL AS known, {', '.join(PRICES)} FROM nse_bhav "
                                 f"WHERE series IN ({marks})", conn, params=SERIES, chunksize=CHUNK):
            chunk["symbol"] = pd.Categorical(chunk["symbol"], categories=symbols)
            parts.append(chunk.astype({"day": "int32", "other": "int8", "share": "int8", "known": "int8"}
                                      | dict.fromkeys(PRICES, "float32")))
    finally:
        src.close()
        conn.close()
        clean()
    df = pd.concat(parts, ignore_index=True)
    del parts
    # Companies only: ETFs, fund units and bonds trade in the EQ series too, under ISINs that don't start INE.
    # The bhavcopy has ISINs since 2011, so a symbol that never had one is an older company, and stays.
    seen = df.groupby("symbol", observed=True)[["share", "known"]].max()
    df = df[~df["symbol"].isin(seen.index[(seen["share"] == 0) & (seen["known"] == 1)])].drop(columns=["share", "known"])
    df = df[(df["close"] > 0) & (df["prev_close"] > 0) & (df["open"] > 0) & (df["low"] > 0)]
    df = df.sort_values(["symbol", "day", "other"]).drop_duplicates(["symbol", "day"])
    return df.drop(columns="other").reset_index(drop=True)


def _rsi(r: pd.Series, n: int = 14) -> pd.Series:
    gain = r.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-r).clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Every feature and the label, from each company's own past and that day's market."""
    by = df["symbol"]
    group = lambda s: s.groupby(by, observed=True, sort=False)
    ewm = lambda s, span: group(s).transform(lambda x: x.ewm(span=span, adjust=False).mean())
    roll = lambda s, n, how: group(s).transform(lambda x: getattr(x.rolling(n), how)())

    r = df["close"] / df["prev_close"] - 1
    # A split or bonus whose previous close the bhavcopy left unadjusted looks like a crash (E2E's 1:10 split on
    # 2026-06-05 reads -90%). Price bands stop real moves well short of these, so such a day counts as no move,
    # keeping the price line whole, and the call before it isn't labelled
    jump = ((r < JUMP_DOWN) | (r > JUMP_UP)).to_numpy()
    r = r.mask(jump, 0.0)
    lpx = group(np.log1p(r.astype("float64"))).cumsum()       # log of the split-free price
    for n in (1, 3, 6, 12, 60, 250):
        df[f"ret_{n}"] = np.expm1(lpx - group(lpx).shift(n)).astype("float32")
    px = np.exp(lpx)
    del lpx
    ema21 = ewm(px, 21)
    df["ema_9_21"] = (ewm(px, 9) / ema21 - 1).astype("float32")
    df["close_ema_21"] = (px / ema21 - 1).astype("float32")
    macd = ewm(px, 12) - ewm(px, 26)
    df["macd_hist"] = ((macd - ewm(macd, 9)) / px).astype("float32")
    del px, ema21, macd
    df["rsi_14"] = group(r).transform(_rsi).astype("float32")
    df["volatility_12"] = roll(r, 12, "std").astype("float32")

    c = df["close"]
    df["range"] = ((df["high"] - df["low"]) / c).astype("float32")
    df["body"] = ((c - df["open"]) / c).astype("float32")
    df["upper_wick"] = ((df["high"] - np.maximum(df["open"], c)) / c).astype("float32")
    df["lower_wick"] = ((np.minimum(df["open"], c) - df["low"]) / c).astype("float32")
    df["vol_ratio"] = (df["volume"] / roll(df["volume"], 20, "mean")).astype("float32")
    df["avg_value"] = roll(df["value"], 20, "mean").astype("float32")

    sessions = np.unique(df["day"].to_numpy())
    sess = np.searchsorted(sessions, df["day"].to_numpy())
    df["dow"] = pd.to_datetime(sessions.astype(str), format="%Y%m%d").day_of_week.to_numpy()[sess].astype("float32")
    on_day = lambda s: s.groupby(df["day"], sort=False)
    df["mkt_ret"] = on_day(r).transform("median").astype("float32")
    df["breadth"] = on_day(r > 0).transform("mean").astype("float32")
    df["rel_1"] = (r - df["mkt_ret"]).astype("float32")
    df["liquidity"] = on_day(df["avg_value"]).rank(pct=True).astype("float32")

    # The label: the next session's move, only when the company traded on the very next session
    on_time = group(pd.Series(sess, index=df.index)).shift(-1).to_numpy() == sess + 1
    on_time &= ~group(pd.Series(jump, index=df.index)).shift(-1, fill_value=False).to_numpy()
    df["next_r"] = np.where(on_time, group(r).shift(-1), np.nan).astype("float32")
    df["next_close"] = np.where(on_time, group(c).shift(-1), np.nan).astype("float32")
    df["label"] = np.where(df["next_r"] > 0, 1.0, np.where(df["next_r"] < 0, 0.0, np.nan)).astype("float32")
    return df.drop(columns=["open", "high", "low", "prev_close", "volume", "value"])


def _matrix(df: pd.DataFrame, rows: np.ndarray) -> np.ndarray:
    """The feature columns of the chosen rows as one float32 matrix, filled column by column to spare memory."""
    X = np.empty((int(rows.sum()), len(FEATURES)), dtype=np.float32)
    for i, f in enumerate(FEATURES):
        X[:, i] = df[f].to_numpy()[rows]
    return X


def _dataset(df: pd.DataFrame, rows: np.ndarray, reference: lgb.Dataset | None = None) -> lgb.Dataset:
    data = lgb.Dataset(_matrix(df, rows), df["label"].to_numpy()[rows], feature_name=FEATURES, reference=reference)
    return data.construct()  # binned now, so the float matrix is freed right away


def _starts(days: np.ndarray, cutoff: date, months: int) -> np.ndarray:
    """The first session of each stretch the test year is cut into, one model per stretch: the whole year when
    months is 0, else a new stretch every `months` calendar months counted from the cutoff's month."""
    days = np.unique(days)
    if not months:
        return days[:1]
    stretch = ((days // 10000 - cutoff.year) * 12 + days // 100 % 100 - cutoff.month) // months
    return days[np.r_[True, stretch[1:] != stretch[:-1]]]


def _pct(mask: np.ndarray) -> float | None:
    """The share of True in mask, as a percent, or None when mask is empty."""
    return round(100 * float(np.mean(mask)), 2) if len(mask) else None


def _avg(values: pd.Series, scale: float = 100, digits: int = 3) -> float | None:
    v = values.dropna()
    return round(scale * float(v.mean()), digits) if len(v) else None


def _auc(up: np.ndarray, prob: np.ndarray) -> float | None:
    """How well the calls rank the companies: 0.5 is a coin toss, 1.0 puts every riser above every faller."""
    n_up = int(up.sum())
    n_down = len(up) - n_up
    if not n_up or not n_down:
        return None
    ranks = pd.Series(prob).rank().to_numpy()
    return round(float((ranks[up].sum() - n_up * (n_up + 1) / 2) / (n_up * n_down)), 4)


def metrics(calls: pd.DataFrame, train_up: float) -> tuple[dict, pd.DataFrame]:
    """How the calls did: overall, confident, liquid, by month, by probability and turnover, and each day's picks."""
    s = calls[calls["label"].notna()]
    up, prob = s["label"].to_numpy() == 1, s["prob_up"].to_numpy()
    hit = (prob >= 0.5) == up
    conf = np.abs(prob - 0.5) >= CONF
    liq = s["avg_value"].to_numpy() >= LIQUID
    out = {"calls": len(s), "flat": len(calls) - len(s), "companies": int(s["symbol"].nunique()),
           "sessions": int(s["day"].nunique()), "right_pct": _pct(hit), "up_pct": _pct(up),
           "always_pct": _pct(up == (train_up >= 0.5)), "said_up_pct": _pct(prob >= 0.5), "auc": _auc(up, prob),
           "confident": {"calls": int(conf.sum()), "right_pct": _pct(hit[conf])},
           "liquid": {"calls": int(liq.sum()), "right_pct": _pct(hit[liq]), "auc": _auc(up[liq], prob[liq]),
                      "up_pct": _pct(up[liq]), "confident_calls": int((liq & conf).sum()),
                      "confident_right_pct": _pct(hit[liq & conf])}}

    edges = [0.0, 0.4, 0.45, 0.5, 0.55, 0.6, 1.0]
    band = np.clip(np.searchsorted(edges, prob, side="right") - 1, 0, len(edges) - 2)
    out["bands"] = [{"from": edges[i], "to": edges[i + 1], "calls": int((band == i).sum()),
                     "up_pct": _pct(up[band == i])} for i in range(len(edges) - 1)]
    value = s["avg_value"].to_numpy()
    out["by_turnover"] = []
    for label, lo, hi in (("Under ₹1 crore a day", 0, 1e7), ("₹1–5 crore", 1e7, 5e7), ("₹5–50 crore", 5e7, 5e8),
                          ("Over ₹50 crore", 5e8, np.inf)):
        m = (value >= lo) & (value < hi)
        out["by_turnover"].append({"label": label, "calls": int(m.sum()), "right_pct": _pct(hit[m]),
                                   "up_pct": _pct(up[m]), "auc": _auc(up[m], prob[m])})
    month = s["day"].to_numpy() // 100
    out["months"] = [{"month": f"{m // 100}-{m % 100:02d}", "calls": int((month == m).sum()),
                      "right_pct": _pct(hit[month == m]), "auc": _auc(up[month == m], prob[month == m])}
                     for m in np.unique(month)]

    # The daily picks skip stocks locked at a price band: those can't be bought (or sold) at the close
    days, skipped = [], []
    for day, d in calls.groupby("day", sort=True):
        known = d["label"].notna().to_numpy()
        d_up, d_prob = d["label"].to_numpy()[known] == 1, d["prob_up"].to_numpy()[known]
        liquid = d[d["avg_value"] >= LIQUID].sort_values("prob_up")
        top, bottom = liquid[liquid["locked"] != 1].tail(TOP), liquid[liquid["locked"] != -1].head(TOP)
        picks = len(liquid) >= 2 * TOP
        if picks:
            skipped.append(int((liquid["locked"].tail(TOP) == 1).sum()))
        days.append({"day": int(day), "calls": len(d), "scored": int(known.sum()),
                     "hits": int(((d_prob >= 0.5) == d_up).sum()), "ups": int(d_up.sum()), "auc": _auc(d_up, d_prob),
                     "top_ret": float(top["next_r"].mean()) if picks else None,
                     "bottom_ret": float(bottom["next_r"].mean()) if picks else None,
                     "liquid_ret": float(liquid["next_r"].mean()) if len(liquid) else None})
    days = pd.DataFrame(days)
    p = days.dropna(subset=["top_ret", "liquid_ret"])
    grow = lambda col, cost=0.0: round(100 * float(np.prod(1 + p[col] - cost) - 1), 1)
    out["picks"] = {"days": len(p), "top": TOP, "top_avg_pct": _avg(p["top_ret"]),
                    "bottom_avg_pct": _avg(p["bottom_ret"]), "liquid_avg_pct": _avg(p["liquid_ret"]),
                    "top_beat_days_pct": _pct((p["top_ret"] > p["liquid_ret"]).to_numpy()),
                    "top_year_pct": grow("top_ret"), "bottom_year_pct": grow("bottom_ret"),
                    "liquid_year_pct": grow("liquid_ret"), "cost_pct": round(100 * COST, 2),
                    "top_year_after_cost_pct": grow("top_ret", COST),
                    "skipped_locked_pct": round(10 * float(np.mean(skipped)), 1) if skipped else None,
                    } if len(p) else None
    out["daily_auc"] = _avg(days["auc"], 1, 4)
    return out, days


def _locked(calls: pd.DataFrame) -> np.ndarray:
    """1 for a stock that closed at its high after a 2%+ rise: usually locked at its upper price band, where
    everyone buys and nobody sells, so it can't be bought at the close. -1 for one locked at its lower band
    (it can't be sold), else 0."""
    up = (calls["body"] >= 0) & (calls["upper_wick"] <= 1e-4) & (calls["ret_1"] >= 0.019)
    down = (calls["body"] <= 0) & (calls["lower_wick"] <= 1e-4) & (calls["ret_1"] <= -0.019)
    return np.where(up, 1, np.where(down, -1, 0)).astype("int8")


def _names() -> dict[str, str]:
    """Today's listed companies' names (a delisted one has none)."""
    conn = sqlite3.connect(f"file:{MARKET_DB_PATH.as_posix()}?mode=ro", uri=True, timeout=600)
    try:
        return dict(conn.execute("SELECT symbol, name FROM nse_listed"))
    finally:
        conn.close()


def save(db: sqlite3.Connection, run_id: int, calls: pd.DataFrame, days: pd.DataFrame) -> None:
    """Every call, each day's score and each company's, in key order so each table is written in one sweep."""
    calls = calls.sort_values(["day", "symbol"])
    iso = lambda col: [f"{d // 10000}-{d // 100 % 100:02d}-{d % 100:02d}" for d in col.tolist()]
    floats = lambda col: col.astype("float64").tolist()
    known, said_up, went_up = calls["label"].notna(), calls["prob_up"] >= 0.5, calls["label"] == 1
    per = (calls.assign(scored=known, hits=known & (said_up == went_up), ups=went_up, said_up=said_up)
           .groupby("symbol", observed=True)
           .agg(calls=("day", "size"), scored=("scored", "sum"), hits=("hits", "sum"), ups=("ups", "sum"),
                said_up=("said_up", "sum"), avg_value=("avg_value", "mean")))
    names = _names()
    db.executemany("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?)",
                   ((run_id, str(r.Index), names.get(str(r.Index)), int(r.calls), int(r.scored), int(r.hits),
                     int(r.ups), int(r.said_up), float(r.avg_value)) for r in per.itertuples()))
    db.executemany("INSERT INTO predictions (run, date, symbol, prob_up, close, next_close, next_ret, avg_value, "
                   "locked, day_ret) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   zip([run_id] * len(calls), iso(calls["day"]), calls["symbol"].astype(str).tolist(),
                       floats(calls["prob_up"]), floats(calls["close"]), floats(calls["next_close"]),
                       floats(calls["next_r"]), floats(calls["avg_value"]), calls["locked"].astype(int).tolist(),
                       floats(calls["ret_1"])))
    db.executemany("INSERT INTO days VALUES (?,?,?,?,?,?,?,?,?,?)",
                   zip([run_id] * len(days), iso(days["day"]), days["calls"].tolist(), days["scored"].tolist(),
                       days["hits"].tolist(), days["ups"].tolist(), floats(days["auc"]), floats(days["top_ret"]),
                       floats(days["bottom_ret"]), floats(days["liquid_ret"])))


def run(cutoff: date | None = None, retrain: str = "once", history: str = "all") -> dict | None:
    """Train before the cutoff, call every company every session after it, and store how the calls did. With
    retrain "quarter" or "month", a fresh model learns everything before each quarter or month of the test year
    and calls only that stretch, the way the live model keeps learning. With history "10y" or "5y", each model
    learns only that many years of sessions before its stretch."""
    if not single_instance("backtest"):
        say("a backtest is already running")
        return None
    keep_awake()
    t0 = time.time()
    db = connect()
    db.execute("UPDATE runs SET status = 'stopped' WHERE status = 'running'")  # we hold the lock: those were killed
    run_id = db.execute("INSERT INTO runs (cutoff, started_at, status, step) VALUES (?, ?, 'running', ?)",
                        (cutoff and cutoff.isoformat(), datetime.now().isoformat(timespec="seconds"),
                         "Copying market.db to the SSD and loading every NSE session since 1994")).lastrowid
    db.commit()

    def step(text: str) -> None:
        say(text)
        db.execute("UPDATE runs SET step = ? WHERE id = ?", (text, run_id))
        db.commit()

    try:
        say(f"run #{run_id}: loading the bhavcopy")
        df = load()
        last = pd.Timestamp(str(df["day"].max()))
        cutoff = cutoff or (last - pd.DateOffset(years=1)).date()
        db.execute("UPDATE runs SET cutoff = ? WHERE id = ?", (cutoff.isoformat(), run_id))
        step(f"Building features for {len(df):,} company-sessions of {df['symbol'].nunique():,} companies")
        df = features(df)

        day = df["day"].to_numpy()
        cut = int(cutoff.strftime("%Y%m%d"))
        ready = df[READY].notna().all(axis=1).to_numpy() & df["next_r"].notna().to_numpy()
        years = HISTORY[history]
        since = cut - years * 10000 if years else 0  # yyyymmdd: the same day `years` years earlier
        train = ready & df["label"].notna().to_numpy() & (day < cut) & (day >= since)
        test = ready & (day >= cut)
        val_cut = int((pd.Timestamp(cutoff) - pd.DateOffset(years=1)).strftime("%Y%m%d"))
        fit, val = train & (day < val_cut), train & (day >= val_cut)
        starts = _starts(day[test], cutoff, RETRAINS[retrain])
        step(f"Finding how long to train: learning {fit.sum():,} rows, checking on the {val.sum():,} of the year"
             f" before {cutoff}; then {len(starts)} model{'s' if len(starts) > 1 else ''}"
             + (f", retrained every {retrain}" if len(starts) > 1 else ""))
        fit_data = _dataset(df, fit)
        probe = lgb.train(PARAMS, fit_data, MAX_ROUNDS, valid_sets=[_dataset(df, val, fit_data)],
                          callbacks=[lgb.early_stopping(PATIENCE, verbose=False)])
        rounds, val_auc = max(probe.best_iteration, 50), probe.best_score["valid_0"]["auc"]
        del fit_data, probe

        step(f"Training on all {train.sum():,} company-sessions before {cutoff}"
             f"{f' (the last {years} years)' if years else ''} ({rounds} rounds)")
        base = _dataset(df, train)
        models = [lgb.train(PARAMS, base, rounds)]
        if len(starts) > 1:
            # Each later model learns every session before its stretch. One binned pool, cut per model, keeps the
            # first model's bins, so nothing after the cutoff shapes how the features are bucketed
            pool = ready & df["label"].notna().to_numpy() & (day < starts[-1]) & (day >= since)
            pool_data, pool_day = _dataset(df, pool, base), day[pool]
            for n, first in enumerate(starts[1:], 2):
                first = int(first)
                step(f"Retraining, model {n} of {len(starts)}: learning "
                     f"{f'the {years} years' if years else 'every session'} before "
                     f"{first // 10000}-{first // 100 % 100:02d}-{first % 100:02d}")
                rows = (pool_day < first) & (pool_day >= (first - years * 10000 if years else 0))
                models.append(lgb.train(PARAMS, pool_data.subset(np.flatnonzero(rows)), rounds))
            del pool_data, pool_day
        del base
        step(f"Calling every company, every session from {cutoff}: {test.sum():,} calls")
        calls = df.loc[test, ["day", "symbol", "close", "next_close", "next_r", "label", "avg_value", "ret_1", "body",
                              "upper_wick", "lower_wick"]].copy()
        X, which = _matrix(df, test), np.searchsorted(starts, day[test], side="right") - 1  # each call's model
        prob = np.empty(len(X), dtype="float32")
        for n, model in enumerate(models):
            prob[which == n] = model.predict(X[which == n])
        calls["prob_up"] = prob
        del X
        calls["locked"] = _locked(calls)
        train_up = float(df["label"].to_numpy()[train].mean())
        train_from = int(day[train].min())
        del df

        step("Scoring the calls")
        result, days = metrics(calls, train_up)
        gain = sum(m.feature_importance("gain") for m in models)
        result.update({"train_rows": int(train.sum()), "train_from": f"{train_from // 10000}-{train_from // 100 % 100:02d}"
                                                                     f"-{train_from % 100:02d}",
                       "train_up_pct": round(100 * train_up, 2), "rounds": rounds, "val_auc": round(val_auc, 4),
                       "retrain": retrain, "models": len(models), "history": history,
                       "features": {f: round(100 * float(g) / float(gain.sum()), 1) for f, g in
                                    sorted(zip(FEATURES, gain), key=lambda kv: -kv[1])},
                       "minutes": round((time.time() - t0) / 60, 1)})
        save(db, run_id, calls, days)
        db.execute("UPDATE runs SET metrics = ? WHERE id = ?", (json.dumps(result), run_id))
        step("Writing the report")
        from . import backtest_report
        try:
            report = backtest_report.build(db, run_id)
        except Exception as e:  # the calls are saved either way; a report that can't be written says why
            say(f"report failed: {type(e).__name__}: {e}")
            report = {"error": f"{type(e).__name__}: {e}"}
        db.execute("UPDATE runs SET status = 'done', finished_at = ?, step = NULL, report = ? WHERE id = ?",
                   (datetime.now().isoformat(timespec="seconds"), json.dumps(report), run_id))
        db.commit()
        say(f"run #{run_id} done in {result['minutes']} min: right {result['right_pct']}% (always "
            f"{result['always_pct']}%), AUC {result['auc']}, liquid {result['liquid']['right_pct']}%")
        return result
    except BaseException as e:
        db.rollback()
        db.execute("UPDATE runs SET status = 'failed', finished_at = ?, step = ? WHERE id = ?",
                   (datetime.now().isoformat(timespec="seconds"), f"{type(e).__name__}: {e}"[:500], run_id))
        db.commit()
        raise
    finally:
        db.close()


def _processes() -> list:
    """The running backtest's processes: the venv's python.exe launcher and the interpreter it starts."""
    import psutil
    return [p for p in psutil.process_iter(["cmdline"]) if {"-m", "app.backtest"} <= set(p.info["cmdline"] or [])]


def _pauses(run_id: int) -> list[list]:
    """A run's pauses as [from, to] ISO times, `to` None while it is paused."""
    try:
        state = json.loads(PAUSES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return state["pauses"] if state.get("run") == run_id else []


def _running_run() -> int | None:
    if not locked("backtest") or not DB.exists():
        return None
    db = _read()
    try:
        row = db.execute("SELECT id FROM runs WHERE status = 'running' ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        db.close()
    return row[0] if row else None


def pause() -> bool:
    """Freeze the running backtest where it stands (the website's Pause); False if none runs or it is paused.

    Windows suspends its threads, so it holds its memory, and keeps the laptop awake, until Continue."""
    import psutil
    run_id = _running_run()
    pauses = _pauses(run_id) if run_id else []
    if not run_id or (pauses and pauses[-1][1] is None) or not (procs := _processes()):
        return False
    for p in procs:
        try:
            p.suspend()
        except psutil.Error:
            pass
    pauses.append([datetime.now().isoformat(timespec="seconds"), None])
    PAUSES.write_text(json.dumps({"run": run_id, "pauses": pauses}), encoding="utf-8")
    return True


def resume() -> bool:
    """Let a paused backtest go on from where it stopped (the website's Continue); False if nothing was paused."""
    import psutil
    procs = _processes()
    for p in procs:
        try:
            p.resume()
        except psutil.Error:
            pass
    run_id = _running_run()
    pauses = _pauses(run_id) if run_id else []
    if pauses and pauses[-1][1] is None:
        pauses[-1][1] = datetime.now().isoformat(timespec="seconds")
        PAUSES.write_text(json.dumps({"run": run_id, "pauses": pauses}), encoding="utf-8")
        return True
    return False


def start(cutoff: date | None = None, retrain: str = "once", history: str = "all") -> bool:
    """Start a run in the background (the website's Run button); False if one is already running."""
    if locked("backtest"):
        return False
    subprocess.Popen([sys.executable, "-X", "utf8", "-u", "-m", "app.backtest", *([cutoff.isoformat()] if cutoff else []),
                      *(["--retrain", retrain] if retrain != "once" else []),
                      *(["--history", history] if history != "all" else [])],
                     cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def next_cutoff(step: str = "session") -> date | None:
    """The first session at least a step after the latest run's cutoff, among the sessions runs were tested on;
    None before any run, or when no session that late is known yet."""
    if not DB.exists():
        return None
    db = _read()
    try:
        row = db.execute("SELECT cutoff FROM runs WHERE cutoff IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
        found = row and db.execute("SELECT MIN(date) FROM days WHERE date >= ?",
                                   ((pd.Timestamp(row["cutoff"]) + STEPS[step]).strftime("%Y-%m-%d"),)).fetchone()[0]
    finally:
        db.close()
    return date.fromisoformat(found) if found else None


def auto_state() -> dict:
    """The Auto run's settings and what it did last; off when it was never turned on."""
    try:
        return json.loads(AUTO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"on": False}


def set_auto(on: bool, step: str = "session", runs: int = 10, retrain: str = "once", history: str = "all") -> None:
    """Turn the Auto run on, with how far each next cutoff moves, how many runs and their settings, or off."""
    if on:
        state = {"on": True, "step": step, "left": runs, "retrain": retrain, "history": history, "started": None,
                 "note": "Waiting for the current run to finish" if locked("backtest") else "Starting the next run"}
    else:
        state = auto_state() | {"on": False, "note": "Turned off"}
    AUTO.write_text(json.dumps(state), encoding="utf-8")


def auto_tick() -> None:
    """While the Auto run is on and no run is going, start the next one a step after the last run's cutoff, with
    the same Retrain and Learn-from choices, until its runs are used up or no later cutoff leaves a month to test."""
    state = auto_state()
    if not state.get("on") or locked("backtest"):
        return
    if state.get("started") and datetime.now() - datetime.fromisoformat(state["started"]) < timedelta(minutes=2):
        return  # the run it just started is still taking its lock
    last = None
    if DB.exists():
        db = _read()
        try:
            last = db.execute("SELECT id, cutoff, status, step FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            db.close()
    cutoff, note = None, None
    if last and last["status"] == "failed":
        note = f"Stopped: run #{last['id']} failed ({last['step']})"
    elif state.get("left", 0) <= 0:
        note = "Done: all its runs have finished"
    elif last and last["status"] in ("running", "stopped"):  # cut off (laptop shut down, server restarted): again
        cutoff = date.fromisoformat(last["cutoff"]) if last["cutoff"] else None
    elif last:
        cutoff = next_cutoff(state.get("step", "session"))
        if cutoff is None or cutoff > date.today() - timedelta(days=30):
            note = "Stopped: no later cutoff leaves a month to test on"
    if note:
        state.update(on=False, note=note)
        say(f"auto run: {note}")
    elif start(cutoff, state.get("retrain", "once"), state.get("history", "all")):
        state.update(left=state["left"] - 1, started=datetime.now().isoformat(timespec="seconds"),
                     note=f"Started a run with cutoff {cutoff.isoformat() if cutoff else 'a year back'}")
        say(f"auto run: {state['note']}; {state['left']} more to go")
    AUTO.write_text(json.dumps(state), encoding="utf-8")


def _auto_loop() -> None:
    while True:
        try:
            auto_tick()
        except Exception as e:  # E: unplugged, backtest.db busy: the next check tries again
            say(f"auto run check failed: {type(e).__name__}: {e}")
        time.sleep(60)


def start_auto() -> None:
    """The thread that starts each next run by itself while the Auto run is on (the server starts it)."""
    threading.Thread(target=_auto_loop, daemon=True, name="backtest_auto").start()


# The website's Backtest page
PAGE = 20
SORTS = {"confidence": "ABS(p.prob_up - 0.5) DESC, p.symbol", "move": "p.next_ret DESC, p.symbol",
         "symbol": "p.symbol", "turnover": "p.avg_value DESC"}
SHOWS = {"all": "", "right": "AND p.next_ret <> 0 AND (p.prob_up >= 0.5) = (p.next_ret > 0)",
         "wrong": "AND p.next_ret <> 0 AND (p.prob_up >= 0.5) <> (p.next_ret > 0)",
         "confident": f"AND ABS(p.prob_up - 0.5) >= {CONF}", "liquid": f"AND p.avg_value >= {LIQUID:.0f}"}
# Companies with at least 50 scored calls first, so three lucky calls don't top the list
COMPANY_SORTS = {"right": "scored >= 50 DESC, hits * 1.0 / MAX(scored, 1) DESC, scored DESC", "worst":
                 "scored >= 50 DESC, hits * 1.0 / MAX(scored, 1), scored DESC", "symbol": "symbol",
                 "turnover": "avg_value DESC"}


def _read() -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def _log() -> dict[int, list[tuple[datetime, str]]]:
    """Each run's log lines (time, message) by run number, from the end of logs/backtest.log."""
    try:
        with open(LOG, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 262_144))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return {}
    runs, current = {}, None
    for line in text.splitlines():
        if not (m := LOG_LINE.match(line)):
            continue
        if start := re.match(r"run #(\d+): loading", m[2]):
            current = int(start[1])
            runs[current] = []
        if current is not None:
            runs[current].append((datetime.fromisoformat(m[1]), m[2]))
    return runs


def _paused(a: datetime, b: datetime, pauses: list[list]) -> float:
    """Seconds of a..b that the run spent paused."""
    now = datetime.now()
    return sum(max(0.0, (min(b, datetime.fromisoformat(t) if t else now) - max(a, datetime.fromisoformat(f)))
                   .total_seconds()) for f, t in pauses)


def _timeline(lines: list[tuple[datetime, str]], running: bool, usual: dict[str, float], pauses: list[list]) -> dict:
    """A run's stages from its log lines: done (and how long each worked), running, paused, stopped or still to
    come; the numbers they reported; and while it runs, the time left, each stage still to come taking what it
    took last time."""
    starts = {}
    for when, msg in lines:
        for key, _, pattern, _ in STAGES:
            if key not in starts and re.match(pattern, msg):
                starts[key] = (when, msg)
    finished = next((when for when, msg in lines if re.match(r"run #\d+ done in", msg)), None)
    paused = running and bool(pauses) and pauses[-1][1] is None
    now, left, stages, facts = datetime.now(), 0.0, [], {}
    for i, (key, label, _, default) in enumerate(STAGES):
        usually = usual.get(key, default)
        if key == "train":  # one training per model: scaled by this run's models against the run it's timed by
            usually *= facts.get("models", 1) / usual.get("train_models", 1)
        stage = {"key": key, "label": label, "status": "waiting", "detail": None, "seconds": None,
                 "usually": round(usually)}
        if key in starts:
            began, msg = starts[key]
            ended = next((starts[k][0] for k, *_ in STAGES[i + 1:] if k in starts), finished)
            stage["detail"] = None if key == "load" else msg
            stage["status"] = "done" if ended else ("paused" if paused else "running") if running else "stopped"
            if stage["status"] != "stopped":
                end = ended or now
                stage["seconds"] = round((end - began).total_seconds() - _paused(began, end, pauses))
            if stage["status"] in ("running", "paused"):
                left += max(usually - stage["seconds"], 0.1 * usually)  # past its usual time: a little more
            if key in FACTS and (m := re.search(FACTS[key][0], msg)):
                facts.update({name: int(v.replace(",", "")) for name, v in zip(FACTS[key][1], m.groups()) if v})
        elif running:
            left += usually
        stages.append(stage)
    return {"stages": stages, "facts": facts, "seconds_left": round(left) if running else None,
            "paused_since": pauses[-1][0] if paused else None}


def _usual(log: dict[int, list[tuple[datetime, str]]]) -> dict[str, float]:
    """How long each stage took in the latest run that finished, and how many models it trained."""
    for run_id in sorted(log, reverse=True):
        timeline = _timeline(log[run_id], False, {}, [])
        if all(s["status"] == "done" for s in timeline["stages"]):
            return {s["key"]: s["seconds"] for s in timeline["stages"]} | {"train_models": timeline["facts"].get("models", 1)}
    return {}


def _size(path: Path) -> int | None:
    """A database's bytes on disk, with its WAL; None if it isn't there."""
    sizes = [p.stat().st_size for p in (path, Path(f"{path}-wal")) if p.exists()]
    return sum(sizes) if sizes else None


def view(run_id: int | None = None) -> dict:
    """Every run (newest first), and one finished run's results and days: the latest one unless run_id says."""
    busy = locked("backtest")
    if not DB.exists():
        return {"running": busy, "runs": [], "run": None, "days": [], "progress": None,
                "files": {"market_db": _size(MARKET_DB_PATH), "snapshot": None, "backtest_db": None},
                "auto": auto_state(), "next_cutoff": None}
    try:
        return _view(busy, run_id)
    except sqlite3.OperationalError as e:  # a run saving into a backtest.db made before WAL
        raise RuntimeError(f"backtest.db is busy ({e}): a run is saving its results, so this page updates in a "
                           f"minute or two") from e


def _view(busy: bool, run_id: int | None) -> dict:
    db = _read()
    try:
        runs = []
        for r in map(dict, db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 20")):
            if r["status"] == "running" and not busy:
                r["status"] = "stopped"  # its process was killed (the laptop shut down, say)
            r["metrics"] = json.loads(r["metrics"]) if r["metrics"] else None
            runs.append(r)
        chosen = next((r for r in runs if r["status"] == "done" and run_id in (None, r["id"])), None)
        days = [dict(d) for d in db.execute("SELECT date, calls, scored, hits, ups, auc, top_ret, bottom_ret, liquid_ret "
                                            "FROM days WHERE run = ? ORDER BY date DESC", (chosen["id"],))] if chosen else []
        if chosen:
            chosen["report"] = json.loads(chosen["report"]) if chosen.get("report") else None
            m = chosen["metrics"]
            chosen["saved"] = {"predictions": m["calls"] + m["flat"], "days": len(days), "companies": db.execute(
                "SELECT COUNT(*) FROM companies WHERE run = ?", (chosen["id"],)).fetchone()[0]}
    finally:
        db.close()

    log = _log()
    usual = _usual(log)
    latest = runs[0] if runs else None
    pauses = _pauses(latest["id"]) if latest else []

    def took(r: dict) -> int | None:
        """How long a run worked, leaving out its pauses."""
        end = r["finished_at"] and datetime.fromisoformat(r["finished_at"])
        if not end:  # still running, or stopped: up to now, or to its last log line
            end = datetime.now() if r["status"] == "running" else log[r["id"]][-1][0] if r["id"] in log else None
        start = datetime.fromisoformat(r["started_at"])
        return end and round((end - start).total_seconds() - (_paused(start, end, pauses) if r is latest else 0))

    brief = lambda r: {k: r[k] for k in ("id", "cutoff", "started_at", "finished_at", "status", "step")} | {
        k: (r["metrics"] or {}).get(k) for k in ("right_pct", "auc", "calls", "minutes", "retrain", "models", "history")} | {
        "seconds": took(r)}
    # the latest run's stages, how long each took and the numbers they reported, and its time left
    progress = _timeline(log[latest["id"]], latest["status"] == "running", usual, pauses) \
        if latest and latest["id"] in log else None
    if progress and latest["status"] == "done" and latest.get("report"):  # a report written after the run
        for stage in progress["stages"]:
            if stage["key"] == "report" and stage["status"] == "waiting":
                stage["status"] = "done"
    auto, suggest = auto_state(), next_cutoff()
    if auto.get("on"):  # the cutoff its next run takes: a step after the latest run's, the running one included
        upcoming = next_cutoff(auto.get("step", "session"))
        auto["next"] = upcoming.isoformat() if upcoming else None
    return {"running": busy, "runs": [brief(r) for r in runs], "run": chosen, "days": days, "progress": progress,
            "files": {"market_db": _size(MARKET_DB_PATH), "snapshot": _size(SNAPSHOT), "backtest_db": _size(DB)},
            "auto": auto, "next_cutoff": suggest.isoformat() if suggest else None}


def _call(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["hit"] = None if not d["next_ret"] else int((d["prob_up"] >= 0.5) == (d["next_ret"] > 0))
    return d


def _page(total: int, page: int) -> tuple[int, int]:
    pages = max(1, math.ceil(total / PAGE))
    return min(max(1, page), pages), pages


def day_calls(run_id: int, day: str, page: int = 1, q: str = "", show: str = "all", sort: str = "confidence") -> dict:
    """One page of a session's calls (every company called that day) and how each turned out."""
    where, params = f"p.run = ? AND p.date = ? {SHOWS[show]}", [run_id, day]
    if q:
        where += " AND (p.symbol LIKE ? OR c.name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    rows = f"FROM predictions p LEFT JOIN companies c ON c.run = p.run AND c.symbol = p.symbol WHERE {where}"
    db = _read()
    try:
        total = db.execute(f"SELECT COUNT(*) {rows}", params).fetchone()[0]
        page, pages = _page(total, page)
        calls = db.execute(f"SELECT p.symbol, c.name, p.prob_up, p.close, p.next_close, p.next_ret, p.avg_value, "
                           f"p.locked {rows} "
                           f"ORDER BY {SORTS[sort]} LIMIT ? OFFSET ?", params + [PAGE, (page - 1) * PAGE]).fetchall()
    finally:
        db.close()
    return {"page": page, "pages": pages, "total": total, "rows": [_call(r) for r in calls]}


def companies(run_id: int, page: int = 1, q: str = "", sort: str = "right") -> dict:
    """One page of every company's year: its calls, how many came out right, and its usual turnover."""
    where, params = "run = ?", [run_id]
    if q:
        where += " AND (symbol LIKE ? OR name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    db = _read()
    try:
        total = db.execute(f"SELECT COUNT(*) FROM companies WHERE {where}", params).fetchone()[0]
        page, pages = _page(total, page)
        rows = db.execute(f"SELECT symbol, name, calls, scored, hits, ups, said_up, avg_value FROM companies "
                          f"WHERE {where} ORDER BY {COMPANY_SORTS[sort]} LIMIT ? OFFSET ?",
                          params + [PAGE, (page - 1) * PAGE]).fetchall()
    finally:
        db.close()
    return {"page": page, "pages": pages, "total": total, "rows": [dict(r) for r in rows]}


def company(run_id: int, symbol: str) -> dict | None:
    """A company's totals and every call it got in the run, newest first; None if it got none."""
    db = _read()
    try:
        head = db.execute("SELECT symbol, name, calls, scored, hits, ups, said_up, avg_value FROM companies "
                          "WHERE run = ? AND symbol = ?", (run_id, symbol)).fetchone()
        calls = db.execute("SELECT date, prob_up, close, next_close, next_ret, avg_value, locked FROM predictions "
                           "WHERE run = ? AND symbol = ? ORDER BY date DESC", (run_id, symbol)).fetchall()
    finally:
        db.close()
    return {"company": dict(head), "calls": [_call(r) for r in calls]} if head else None


if __name__ == "__main__":
    if sys.platform == "win32":  # stay out of the way of the website and the downloads
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    args, flags = sys.argv[1:], {}
    for flag, default in (("--retrain", "once"), ("--history", "all")):
        flags[flag] = args.pop(args.index(flag) + 1) if flag in args else default
        args = [a for a in args if a != flag]
    sys.exit(0 if run(date.fromisoformat(args[0]) if args else None, flags["--retrain"], flags["--history"])
             is not None else 3)
