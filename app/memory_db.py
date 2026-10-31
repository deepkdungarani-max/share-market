"""Shared memory of the models (E:/candlecast-data/memory.db): the news Narad collects, Narad's note on each
item, the help requests a confused model raises for Drona, Sanjay's calls, and Chitragupta's scores."""
import sqlite3

from .config import MARKET_DIR, MEMORY_DB_PATH
from .system import disk_problem

SCHEMA = """
-- Every news item and NSE filing collected, exactly once per link
CREATE TABLE IF NOT EXISTS news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT    NOT NULL,           -- "ET Markets", "NSE announcements", "Google News: Upstox"…
    title        TEXT    NOT NULL,
    summary      TEXT,                       -- the feed's description, plain text
    url          TEXT    NOT NULL UNIQUE,
    published_at TEXT,                       -- UTC, YYYY-MM-DD HH:MM:SS
    priority     INTEGER NOT NULL DEFAULT 1, -- read first when higher: NSE filings of untracked companies = 0
    status       TEXT    NOT NULL DEFAULT 'new',  -- new | read | failed | duplicate (same story read already)
    attempts     INTEGER NOT NULL DEFAULT 0,
    fetched_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_next ON news(status, priority DESC, published_at DESC);

-- Narad's reading of one news item
CREATE TABLE IF NOT EXISTS news_notes (
    news_id    INTEGER PRIMARY KEY REFERENCES news(id),
    about      TEXT NOT NULL,                -- company | sector | market
    companies  TEXT NOT NULL,                -- JSON list of company names as the model read them
    symbols    TEXT NOT NULL,                -- JSON list of the NSE symbols those names matched
    event      TEXT NOT NULL,                -- results | guidance | order_or_contract | … (see narad.EVENTS)
    positives  TEXT NOT NULL,                -- JSON list: points good for the share price
    negatives  TEXT NOT NULL,                -- JSON list: points bad for the share price
    sentiment  REAL NOT NULL,                -- -1 very bad .. 0 neutral .. +1 very good
    confidence REAL NOT NULL,                -- 0..1 as the model rates itself; small models overrate it
    model      TEXT NOT NULL,                -- ollama:<model>
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A model that is unsure asks here; Drona picks a helper and writes the answer back
CREATE TABLE IF NOT EXISTS help_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asker       TEXT NOT NULL,               -- narad | sanjay | …
    ref         TEXT NOT NULL,               -- what it is about, e.g. news:123
    question    TEXT NOT NULL,
    reason      TEXT NOT NULL,               -- mixed (good and bad points together) | unsure (low confidence)
                                             -- | unreliable (Narad's scored record on this kind of news is poor)
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | answered | skipped
    answer      TEXT,
    answered_by TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    answered_at TEXT,
    UNIQUE (asker, ref)
);

-- A model's call on each tracked stock for the next session: Sanjay from the chart, Chanakya from the world,
-- Trikal (the main prediction) from both plus the news
CREATE TABLE IF NOT EXISTS signals (
    model      TEXT NOT NULL,                -- sanjay | chanakya | trikal
    symbol     TEXT NOT NULL,
    as_of      TEXT NOT NULL,                -- last closed session the call used (IST date); it is for the next one
    prob_up    REAL NOT NULL,                -- probability the next session closes above as_of's close
    detail     TEXT,                         -- JSON: which model file made the call
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (model, symbol, as_of)
);

-- Chitragupta's ledger: each model's call on a stock, scored against what the market actually did
CREATE TABLE IF NOT EXISTS scores (
    model      TEXT NOT NULL,                -- narad | drona | sanjay | …
    ref        TEXT NOT NULL,                -- what was called: news:123, or signal:<as_of> for Sanjay
    symbol     TEXT NOT NULL,                -- NIFTY 50 for market-wide news
    session    TEXT NOT NULL,                -- trading day the call was about, YYYY-MM-DD (IST)
    said       REAL NOT NULL,                -- the call, -1..+1 (Sanjay: 2 x prob_up - 1)
    confidence REAL,
    move       REAL NOT NULL,                -- the stock's close-to-close change that session (0.01 = 1%)
    market     REAL NOT NULL,                -- NIFTY 50's change that session
    outcome    REAL NOT NULL,                -- what the call is judged on: news, move minus market (just move
                                             -- for NIFTY 50 itself); Sanjay, move (its up/down target)
    hit        INTEGER,                      -- 1 the call's sign matched the outcome, 0 not, NULL for a neutral call
    scored_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (model, ref, symbol)
);

-- Every call Drona makes to a writer (agy on the Google AI Pro quota…), for the API keys page
CREATE TABLE IF NOT EXISTS writer_calls (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    writer     TEXT    NOT NULL,             -- agy:claude-sonnet-4-6 | agy:gemini-3.8-flash-high | …
    kind       TEXT    NOT NULL,             -- lesson | help | answer
    ok         INTEGER NOT NULL,             -- 1 answered, 0 failed
    limit_hit  INTEGER NOT NULL DEFAULT 0,   -- 1 the writer said its usage limit is used up
    tokens     INTEGER,                      -- input + output + thinking, as the writer reported
    seconds    REAL,
    error      TEXT,
    at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_writer_calls ON writer_calls(writer, at);

-- Krishna's diary: problems it found, what it fixed on its own, problems that went away, its reviews
CREATE TABLE IF NOT EXISTS krishna_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind    TEXT NOT NULL,                   -- problem | warning | fixed | resolved | review
    area    TEXT NOT NULL,                   -- the model or part it is about: Narad, Drona, Disk…
    message TEXT NOT NULL,
    at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Krishna's daily review: how each model is doing, advice for each, and the topics it queued for Drona
CREATE TABLE IF NOT EXISTS krishna_reports (
    day        TEXT PRIMARY KEY,             -- IST date
    report     TEXT NOT NULL,                -- JSON: summary, advice [{model, advice}], study [{title, why}]
    writer     TEXT NOT NULL,                -- the AI that wrote it
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    if problem := disk_problem():
        raise RuntimeError(problem)
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
