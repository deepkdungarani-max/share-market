"""Lessons written outside the learner (by Claude Code, at the user's request) go into knowledge.db exactly as
Drona's do: claim the topics first so the learners skip them, then store the lessons from a file in Drona's
format (knowledge.FORMAT), each wrapped in <topic id="N">…</topic>.

Usage:
  python -m app.lesson_import claim LEVEL [N]    claim N pending syllabus topics of a level; prints id, title, why
  python -m app.lesson_import claim-last LEVEL [N]   the same from the level's end (meets the learners midway)
  python -m app.lesson_import store FILE [MODEL]  store every <topic id="N"> block in FILE
  python -m app.lesson_import release            give claimed topics not yet written back to the learners
"""
import re
import sys

from .knowledge import parse, store
from .knowledge_db import connect

CLAIMED = "writing"  # a topic's status while it is written outside the learner (the learners take 'pending' only)


def claim(level: int, n: int = 100, last: bool = False) -> list[tuple[int, str, str]]:
    """Claim n pending topics of a syllabus level: the first ones, or with last the last ones (the learners go
    first to last, so claiming from the end meets them in the middle instead of holding up the syllabus)."""
    conn = connect()
    try:
        rows = conn.execute("SELECT id, title, why FROM topics WHERE syllabus = ? AND status = 'pending' "
                            f"ORDER BY id {'DESC' if last else ''} LIMIT ?", (level, n)).fetchall()
        conn.executemany("UPDATE topics SET status = ? WHERE id = ?", [(CLAIMED, i) for i, _, _ in rows])
        conn.commit()
        return rows
    finally:
        conn.close()


def store_file(path: str, model: str = "claude-code:opus-5.5") -> list[str]:
    text = open(path, encoding="utf-8").read()
    conn, out = connect(), []
    try:
        for topic_id, block in re.findall(r'<topic id="(\d+)">(.*?)</topic>', text, re.S):
            row = conn.execute("SELECT title, depth, status FROM topics WHERE id = ?", (int(topic_id),)).fetchone()
            if row is None:
                out.append(f"{topic_id}: no such topic")
                continue
            got = parse(block)
            if len(got["lesson"]) < 400:
                out.append(f"{topic_id}: lesson too short, not stored")
                continue
            store(conn, int(topic_id), row[0], row[1], got, model, "[claude code] ")
            out.append(f"{topic_id}: {row[0][:70]} — {len(got['lesson'].split())} words, {len(got['qa'])} Q&A, "
                       f"{len(got['subtopics'])} subtopics, {len(got['sources'])} sources")
        return out
    finally:
        conn.close()


def release() -> int:
    conn = connect()
    try:
        n = conn.execute("UPDATE topics SET status = 'pending' WHERE status = ?", (CLAIMED,)).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd in ("claim", "claim-last"):
        for i, title, why in claim(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 100, cmd == "claim-last"):
            print(f"{i} | {title} | {why}")
    elif cmd == "store":
        print("\n".join(store_file(sys.argv[2], *sys.argv[3:4])))
    elif cmd == "release":
        print(f"{release()} topics given back to the learners")
