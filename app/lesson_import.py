"""Lessons written outside the learner (by Claude Code, at the user's request) go into knowledge.db exactly as
Drona's do: claim the topics first so the learners skip them, then store the lessons from a file in Drona's
format (knowledge.FORMAT), each wrapped in <topic id="N">…</topic>.

Usage:
  python -m app.lesson_import claim LEVEL [N]    claim N pending syllabus topics of a level; prints id, title, why
  python -m app.lesson_import claim-last LEVEL [N]   the same from the level's end (meets the learners midway)
  python -m app.lesson_import claim-queue [N] [DEPTH]  claim N pending non-syllabus topics from the end of the
                                                     learners' queue (deepest and newest first), or of DEPTH only
  python -m app.lesson_import export DEPTH DIR [PER_FILE]  write every pending topic of DEPTH outside the syllabus
                                                     into DIR/topics_001.md… (PER_FILE, 50, a file) and DIR/index.md,
                                                     for answering outside the app (lessons/README.md)
  python -m app.lesson_import store PATH [MODEL] [--replace]  store every <topic id="N"> block in PATH, a file or
                                                     a folder of .txt/.md files; topics already learned are kept
                                                     unless --replace
  python -m app.lesson_import release            give claimed topics not yet written back to the learners
"""
import re
import sys
from datetime import datetime
from pathlib import Path

from .knowledge import parse, path_of, store
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


def claim_queue(n: int = 10, depth: int | None = None) -> list[tuple[int, str, str]]:
    """Claim n pending topics outside the syllabus from the end of the learners' queue: they take the highest
    priority, shallowest, oldest topic first, so the lowest priority, deepest, newest ones are the last they'd
    reach. With depth, only topics of that depth."""
    conn = connect()
    try:
        rows = conn.execute("SELECT id, title, why FROM topics WHERE syllabus IS NULL AND status = 'pending' "
                            + ("AND depth = ? " if depth is not None else "")
                            + "ORDER BY priority, depth DESC, id DESC LIMIT ?",
                            (depth, n) if depth is not None else (n,)).fetchall()
        conn.executemany("UPDATE topics SET status = ? WHERE id = ? AND status = 'pending'",
                         [(CLAIMED, i) for i, _, _ in rows])
        conn.commit()
        return rows
    finally:
        conn.close()


def export(depth: int, folder: str, per_file: int = 50) -> list[str]:
    """Write every pending topic of a depth outside the syllabus, in the learners' order, into numbered Markdown
    files of per_file topics: id, title, why, and the subjects it sits under. They are answered outside the app
    into folder/answers/ (format: lessons/README.md) and come back through store."""
    conn = connect()
    try:
        rows = conn.execute("SELECT id, title, why FROM topics WHERE syllabus IS NULL AND status = 'pending' "
                            "AND depth = ? ORDER BY priority DESC, id", (depth,)).fetchall()
        under = {i: path_of(conn, i)[:-1] for i, _, _ in rows}
    finally:
        conn.close()
    out = Path(folder)
    (out / "answers").mkdir(parents=True, exist_ok=True)
    (out / "answers" / ".gitkeep").touch()  # git keeps the empty folder the answers go into
    parts = [rows[k:k + per_file] for k in range(0, len(rows), per_file)]
    for n, part in enumerate(parts, 1):
        lines = [f"# Depth {depth} topics, part {n} of {len(parts)}", "",
                 f"Answer every topic below into `answers/answers_{n:03d}.txt`: one `<topic id=\"N\">…</topic>` block "
                 "each, in the format of `lessons/README.md`.", ""]
        for i, title, why in part:
            lines += [f"## {i} · {title}", f"- Why: {why or '(none given)'}", f"- Under: {' › '.join(under[i])}", ""]
        (out / f"topics_{n:03d}.md").write_text("\n".join(lines), encoding="utf-8")
    index = [f"# Pending depth {depth} topics: {len(rows)}, as of {datetime.now():%Y-%m-%d %H:%M}", "",
             f"{len(parts)} files of up to {per_file}. Answers are matched by id, so their file names don't matter.", ""]
    index += [f"- {i} · {title} (`topics_{k // per_file + 1:03d}.md`)" for k, (i, title, _) in enumerate(rows)]
    (out / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return [f"topics_{n:03d}.md" for n in range(1, len(parts) + 1)]


def store_file(path: str, model: str = "claude-code:opus-5.5", replace: bool = False) -> list[str]:
    text = open(path, encoding="utf-8").read()
    conn, out = connect(), []
    try:
        for topic_id, block in re.findall(r'<topic id="(\d+)">(.*?)</topic>', text, re.S):
            row = conn.execute("SELECT title, depth, status FROM topics WHERE id = ?", (int(topic_id),)).fetchone()
            if row is None:
                out.append(f"{topic_id}: no such topic")
                continue
            if row[2] == "done" and not replace:
                out.append(f"{topic_id}: already learned, kept (--replace stores this one over it)")
                continue
            got = parse(block)
            if len(got["lesson"]) < 400:
                out.append(f"{topic_id}: lesson too short, not stored")
                continue
            store(conn, int(topic_id), row[0], row[1], got, model,
                  "[claude code] " if model.startswith("claude-code") else f"[{model}] ")
            out.append(f"{topic_id}: {row[0][:70]} — {len(got['lesson'].split())} words, {len(got['qa'])} Q&A, "
                       f"{len(got['subtopics'])} subtopics, {len(got['sources'])} sources")
        return out
    finally:
        conn.close()


def store_path(path: str, model: str = "claude-code:opus-5.5", replace: bool = False) -> list[str]:
    """Store a file of lessons, or every .txt and .md file in a folder, in name order."""
    files = sorted(f for f in Path(path).iterdir() if f.suffix in (".txt", ".md")) if Path(path).is_dir() \
        else [Path(path)]
    return [line for f in files for line in [f"== {f.name}", *store_file(str(f), model, replace)]]


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
    elif cmd == "claim-queue":
        for i, title, why in claim_queue(int(sys.argv[2]) if len(sys.argv) > 2 else 10,
                                         int(sys.argv[3]) if len(sys.argv) > 3 else None):
            print(f"{i} | {title} | {why}")
    elif cmd == "export":
        made = export(int(sys.argv[2]), sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 50)
        print(f"{len(made)} topic files and index.md written to {sys.argv[3]}")
    elif cmd == "store":
        args = [a for a in sys.argv[2:] if a != "--replace"]
        print("\n".join(store_path(args[0], *args[1:2], replace="--replace" in sys.argv)))
    elif cmd == "release":
        print(f"{release()} topics given back to the learners")
