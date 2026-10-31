import sqlite3

from .config import DB_PATH, MARKET_DIR
from .system import disk_problem

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol   TEXT    NOT NULL,
    interval TEXT    NOT NULL,
    ts       INTEGER NOT NULL,          -- candle open time, UTC epoch ms
    open     REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, interval, ts)
);

CREATE TABLE IF NOT EXISTS models (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    interval   TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    path       TEXT    NOT NULL,         -- relative to project root
    metrics    TEXT,                     -- JSON
    active     INTEGER NOT NULL DEFAULT 0,  -- the one model per (market, interval) the app uses
    market     TEXT    NOT NULL DEFAULT 'stocks'  -- stocks | forex (config.MARKETS)
);

CREATE TABLE IF NOT EXISTS predictions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id   INTEGER REFERENCES models(id),
    symbol     TEXT    NOT NULL,
    interval   TEXT    NOT NULL,
    ts         INTEGER NOT NULL,         -- candle being predicted
    prob_up    REAL    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mode          TEXT    NOT NULL CHECK (mode IN ('backtest', 'paper', 'live')),
    symbol        TEXT    NOT NULL,
    side          TEXT    NOT NULL CHECK (side IN ('BUY', 'SELL')),
    qty           INTEGER NOT NULL,
    entry_ts      INTEGER NOT NULL,
    entry_price   REAL    NOT NULL,
    exit_ts       INTEGER,
    exit_price    REAL,
    charges       REAL    DEFAULT 0,
    pnl           REAL,
    prediction_id INTEGER REFERENCES predictions(id),
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_predictions_symbol_ts ON predictions(symbol, ts);
CREATE UNIQUE INDEX IF NOT EXISTS uq_predictions ON predictions(model_id, symbol, interval, ts);
CREATE INDEX IF NOT EXISTS idx_trades_entry ON trades(entry_ts);
"""


def connect() -> sqlite3.Connection:
    if problem := disk_problem():  # the data disk is unplugged or locked (BitLocker)
        raise RuntimeError(problem)
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    # timeout: the server writes from several threads; wait for the lock instead of failing.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    # FULL sync: slower, but a pulled pendrive is far less likely to leave a broken DB.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    if "market" not in {row[1] for row in conn.execute("PRAGMA table_info(models)")}:
        # DBs made before forex: every model so far was a stocks model
        conn.execute("ALTER TABLE models ADD COLUMN market TEXT NOT NULL DEFAULT 'stocks'")
        conn.commit()
    return conn
