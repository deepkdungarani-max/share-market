"""Teacher knowledge base (E:/candlecast-data/knowledge.db): a growing tree of market topics,
a researched lesson + hard Q&A per topic, and every question asked in the Teacher tab."""
import re
import sqlite3

from .config import KNOWLEDGE_DB_PATH, MARKET_DIR
from .system import disk_problem

SCHEMA = """
-- Curriculum tree. Each learned topic proposes deeper subtopics, so the tree keeps growing.
CREATE TABLE IF NOT EXISTS topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER REFERENCES topics(id),
    title      TEXT    NOT NULL,
    key        TEXT    NOT NULL UNIQUE,  -- normalized title: stops the same topic being queued twice
    why        TEXT,                     -- why the parent lesson said this is worth going deeper on
    depth      INTEGER NOT NULL,         -- 0 = root subject
    priority   INTEGER NOT NULL DEFAULT 0, -- learned first when higher; gaps found while answering = 10
    status     TEXT    NOT NULL DEFAULT 'pending',  -- pending | done | failed
    attempts   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    learned_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_topics_next ON topics(status, priority DESC, depth, id);

CREATE TABLE IF NOT EXISTS lessons (
    topic_id INTEGER PRIMARY KEY REFERENCES topics(id),
    level    TEXT,                       -- beginner | intermediate | advanced | expert
    body     TEXT NOT NULL,              -- markdown
    sources  TEXT,                       -- JSON [{title, url}]
    model    TEXT
);

-- Hard questions with worked answers, written while learning each topic
CREATE TABLE IF NOT EXISTS qa (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id   INTEGER NOT NULL REFERENCES topics(id),
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    difficulty TEXT
);

-- Questions asked in the Teacher tab
CREATE TABLE IF NOT EXISTS asks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL DEFAULT 'question',  -- question | review
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    used       TEXT,                     -- JSON [{id, title}] of topics the answer drew on
    engine     TEXT,                     -- claude model name, or ollama:<model>
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

-- Full-text index over lessons and Q&A (kind = lesson | qa, ref = topic id)
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(
    title, body, kind UNINDEXED, ref UNINDEXED, tokenize = 'porter unicode61'
);
"""


def connect() -> sqlite3.Connection:
    if problem := disk_problem():
        raise RuntimeError(problem)
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(KNOWLEDGE_DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    if "syllabus" not in {c[1] for c in conn.execute("PRAGMA table_info(topics)")}:  # added with app/syllabus.py
        conn.execute("ALTER TABLE topics ADD COLUMN syllabus INTEGER")  # the syllabus level, 1-7; NULL otherwise
    return conn


def topic_key(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))


def add_topic(conn, title: str, *, parent_id: int | None = None, depth: int = 0,
              why: str | None = None, priority: int = 0) -> int | None:
    """Queue a topic; returns its id, or None if it was already known."""
    title = title.strip()[:200]
    key = topic_key(title)
    if not key:
        return None
    cur = conn.execute(
        "INSERT OR IGNORE INTO topics (parent_id, title, key, why, depth, priority) VALUES (?,?,?,?,?,?)",
        (parent_id, title, key, why, depth, priority),
    )
    return cur.lastrowid if cur.rowcount else None


def set_meta(conn, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_meta(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


# Words too common to help find the right lesson
STOP = set("""a an and are as at be by can do does for from how i if in into is it its kya ke ki ko me mein
mujhe of on or se so that the then this to was what when where which who why will with hai he hota hoti
karta karte kaise kese""".split())


def search(conn, text: str, limit: int = 8) -> list[dict]:
    """Best-matching lessons and Q&A for a question (BM25, title weighted 4x)."""
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]
    if not words:
        return []
    query = " OR ".join(f'"{w}"' for w in dict.fromkeys(words))
    rows = conn.execute(
        "SELECT kind, ref, title, body, bm25(search, 4.0, 1.0) AS score FROM search WHERE search MATCH ? "
        "ORDER BY score LIMIT ?",
        (query, limit),
    ).fetchall()
    return [{"kind": k, "topic_id": int(r), "title": t, "body": b, "score": s} for k, r, t, b, s in rows]
