"""Bulk market-history database (data/market.db): every NSE security since 1994 + Yahoo intraday."""
import sqlite3

from .config import MARKET_DB_PATH, MARKET_DIR
from .system import disk_problem

SCHEMA = """
-- NSE bhavcopy: one row per security per trading day, exactly as NSE published it (unadjusted).
-- Includes delisted companies, SME, ETFs, bonds — filter on series (EQ, BE, SM, ST…) when training.
CREATE TABLE IF NOT EXISTS nse_bhav (
    date       TEXT    NOT NULL,     -- trading day, YYYY-MM-DD
    symbol     TEXT    NOT NULL,
    series     TEXT    NOT NULL,
    isin       TEXT,                 -- in old files only from ~2011; always in the 2024+ format
    name       TEXT,                 -- only in the 2024+ format
    open REAL, high REAL, low REAL, close REAL, last REAL,
    prev_close REAL,                 -- NSE adjusts this on split/bonus ex-dates: use it to back-adjust prices
    volume     INTEGER,              -- shares traded
    value      REAL,                 -- turnover, rupees
    trades     INTEGER,              -- number of trades (later years only)
    PRIMARY KEY (symbol, series, date)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS nse_bhav_days (
    date   TEXT PRIMARY KEY,
    status TEXT    NOT NULL,         -- ok | holiday
    rows   INTEGER NOT NULL
);

-- Currently listed companies (NSE EQUITY_L.csv + SME_EQUITY_L.csv)
CREATE TABLE IF NOT EXISTS nse_listed (
    symbol       TEXT PRIMARY KEY,
    name         TEXT,
    series       TEXT,
    listing_date TEXT,               -- YYYY-MM-DD
    isin         TEXT,
    board        TEXT                -- main | sme
);

-- Yahoo daily bars: OHLC split-adjusted by Yahoo, adj_close also dividend-adjusted
CREATE TABLE IF NOT EXISTS yahoo_daily (
    symbol    TEXT NOT NULL,         -- NSE symbol, or a Yahoo index ticker such as ^NSEI
    date      TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, adj_close REAL,
    volume    INTEGER,
    dividends REAL,
    splits    REAL,
    PRIMARY KEY (symbol, date)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS yahoo_intraday (
    symbol   TEXT    NOT NULL,
    interval TEXT    NOT NULL,       -- 1m | 15m | 1h
    ts       INTEGER NOT NULL,       -- bar open time, UTC epoch ms
    open REAL, high REAL, low REAL, close REAL,
    volume   INTEGER,
    PRIMARY KEY (symbol, interval, ts)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS yahoo_jobs (
    symbol   TEXT NOT NULL,
    interval TEXT NOT NULL,          -- 1d | 1h | 15m | 1m
    status   TEXT NOT NULL,          -- ok | nodata
    rows     INTEGER NOT NULL,
    run_date TEXT NOT NULL,          -- IST date of the run that fetched it
    PRIMARY KEY (symbol, interval)
);
"""


def connect() -> sqlite3.Connection:
    if problem := disk_problem():
        raise SystemExit(problem)
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    # The NSE downloader's final indexing holds the write lock for many minutes: the other downloader
    # waits for it (up to an hour) instead of failing with "database is locked".
    conn = sqlite3.connect(MARKET_DB_PATH, timeout=3600)
    conn.execute("PRAGMA journal_mode=WAL")
    # NORMAL with WAL: a power cut can lose the last few commits but not corrupt the file.
    # Every download is idempotent, so anything lost is simply fetched again next run.
    conn.execute("PRAGMA synchronous=NORMAL")
    # Copy the WAL back into the DB file every ~200 MB instead of every 4 MB: each copy ends with an fsync,
    # which costs seconds on the external hard disk, so fewer, bigger checkpoints are far faster.
    conn.execute("PRAGMA wal_autocheckpoint=50000")
    conn.execute("PRAGMA cache_size=-200000")  # ~200 MB page cache
    conn.executescript(SCHEMA)
    return conn
