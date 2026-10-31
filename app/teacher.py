"""The market teacher: answers any stock market question from the learned knowledge base, and reviews
the LightGBM prediction models the way a teacher checks a student's work.

Answers come from DRONA_WRITERS (Gemini through the Antigravity CLI, which searches the web for current
facts) given the best-matching lessons; when none can answer, from the local Ollama model with the same lessons. Anything the
knowledge base was missing is queued as a high-priority topic, so the learner studies it next.

As Drona it also answers the help requests the other models raise in the shared memory (help_models),
with the lessons that match each one, and learns from Chitragupta's scores (study_scores): a wrong call on
a big move becomes a study topic, and a help answer the market proved right becomes a checked lesson.
The learner loop calls both before each topic.
"""
import json
import re
import time
from datetime import datetime

import requests

from . import agy_cli, codex_cli, narad, syllabus
from .chitragupta import track_record
from .claude_cli import ClaudeError, UsageLimit, ask as ask_claude, rest_after
from .config import CODEX_WRITERS, DRONA_WRITERS, DRONA_WRITERS_2, OLLAMA_MODEL, OLLAMA_URL, SYMBOLS
from .db import connect as connect_app
from .features import FEATURES
from .knowledge_db import add_topic, connect, get_meta, search, set_meta, topic_key
from .memory_db import connect as connect_memory

CONTEXT_CHARS = 24_000  # lesson text handed to the teacher per question
GAP_PRIORITY = 10
HELP_BATCH = 10  # help requests answered per Claude call
HELP_LESSONS = 2  # best-matching lessons shown with each help request
MISS_MOVE = 0.03  # a wrong call on a tracked stock that moved at least this much (3%) gets studied
CHECKED = "Drona's checked calls on market news"  # topic holding help answers the market proved right
LIMIT_REST = 30 * 60  # a writer whose usage limit is used up is skipped this long, unless it says when it resets
_rest_until: dict[str, float] = {}  # writer -> time its usage limit should have reset
_busy: dict[str, dict] = {}  # writer -> what it is writing right now, for the API keys page
_seeded = False
ALL_WRITERS = DRONA_WRITERS + DRONA_WRITERS_2 + CODEX_WRITERS


def _seed_rests() -> None:
    """After a restart, remember the limits hit before it, so used-up writers aren't asked again."""
    global _seeded
    if _seeded:
        return
    _seeded = True
    try:
        conn = connect_memory()
        try:
            rows = conn.execute("SELECT writer, CAST(strftime('%s', at) AS INTEGER), error FROM writer_calls "
                                "WHERE limit_hit AND at >= datetime('now', '-8 hours') ORDER BY id").fetchall()
        finally:
            conn.close()
    except Exception:
        return
    for writer, at, error in rows:
        since = datetime.fromtimestamp(at)  # writer_calls keeps UTC; this is the laptop's local time of the error
        _rest_until[writer] = max(_rest_until.get(writer, 0), at + rest_after(error, LIMIT_REST, since))


def _call(writer: str, prompt: str, system: str, web: bool, timeout: int) -> tuple[str, int | None]:
    """One writer: agy:<model> / agy2:<model> (Antigravity CLI on Google account 1 / 2, searches the web on
    its own), codex:<model>@<effort> (Codex CLI on your ChatGPT plan, with web search) or claude:<model>.
    (text, tokens used when the writer reports them)."""
    kind, _, model = writer.partition(":")
    if kind in ("agy", "agy2"):
        return agy_cli.ask(prompt, system, model=model, timeout=timeout, account_no=2 if kind == "agy2" else 1)
    if kind == "codex":
        model, _, effort = model.partition("@")
        return codex_cli.ask(prompt, system, model=model, effort=effort or None, web=True, timeout=timeout)
    if kind == "claude":
        return ask_claude(prompt, system, model=model, web=web, timeout=timeout), None
    raise ClaudeError(f"unknown writer {writer!r} in CANDLECAST_DRONA_WRITERS")


def _record(writer: str, kind: str, started: float, tokens: int | None = None, error: Exception | None = None) -> None:
    """One line in memory.db writer_calls, for the API keys page. Never lets a disk problem fail the call."""
    try:
        conn = connect_memory()
        try:
            with conn:
                conn.execute("INSERT INTO writer_calls (writer, kind, ok, limit_hit, tokens, seconds, error) "
                             "VALUES (?,?,?,?,?,?,?)",
                             (writer, kind, error is None, isinstance(error, UsageLimit), tokens,
                              round(time.time() - started, 1), str(error)[:300] if error else None))
        finally:
            conn.close()
    except Exception:
        pass


def _ready(writer: str) -> bool:
    """False for account 2's writers until its worker runs (tools/agy2/setup.ps1), and for Codex until it is
    signed in (tools/codex-login.ps1)."""
    if writer.startswith("agy2:"):
        return agy_cli.available(2)
    if writer.startswith("codex:"):
        return codex_cli.available()
    return True


# Who reaches which plan, for the API keys page: (label, account)
def _plans() -> dict[str, tuple[str, str | None]]:
    return {"agy": ("Google AI Pro · account 1", agy_cli.account(1)),
            "agy2": ("Google AI Pro · account 2", agy_cli.account(2)),
            "codex": ("ChatGPT Pro", codex_cli.account()),
            "claude": ("Claude Code", None)}


def write(prompt: str, system: str, *, kind: str, web: bool = False, cloud: bool = True, timeout: int = 900,
          writers: list[str] | None = None, what: str = "") -> tuple[str, str]:
    """Drona's reply and who wrote it: each writer in turn (default: Google account 1's, account 2's, then
    ChatGPT's), else
    (cloud=True, for help answers only) Narad's Gemini/Groq/OpenRouter keys. Lessons pass cloud=False: the free keys can't
    research (see narad.cloud_write). kind (lesson | help | answer) is recorded with each call, and what (the
    topic, the question…) is shown on the API keys page while it is written. UsageLimit when no writer has
    usage left right now; ClaudeError when the writers failed otherwise."""
    _seed_rests()
    used_up, failed = [], []
    for name in writers or ALL_WRITERS:
        if not _ready(name):
            continue
        if time.time() < _rest_until.get(name, 0):
            used_up.append(name)
            continue
        started = time.time()
        _busy[name] = {"kind": kind, "what": what[:120], "since": started}
        try:
            text, tokens = _call(name, prompt, system, web, timeout)
            if not text.strip():  # the plan answered but said nothing (Gemini under load did): the next one tries
                raise ClaudeError("empty reply")
        except UsageLimit as e:
            _rest_until[name] = time.time() + rest_after(e, LIMIT_REST)
            used_up.append(name)
            _record(name, kind, started, error=e)
            continue
        except ClaudeError as e:  # too slow, unreadable reply…: the next writer tries
            failed.append(f"{name}: {e}")
            _record(name, kind, started, error=e)
            continue
        finally:
            _busy.pop(name, None)
        _record(name, kind, started, tokens)
        return text, name
    if cloud:
        try:
            return narad.cloud_write(prompt, system)
        except narad.ReaderDown as e:
            used_up.append(f"cloud keys ({e})")
    if failed:
        raise ClaudeError("; ".join(failed + [f"usage used up: {n}" for n in used_up])[:500])
    raise UsageLimit(f"usage used up: {', '.join(used_up)}")


def writers_view() -> dict:
    """For the API keys page: each of Drona's writers, what it is doing now (working on something, standing by,
    or resting until its limit resets), and its calls and tokens in the last 24 hours and 7 days. The CLIs
    don't say how much of a plan's quota is left; the plans' own settings pages do."""
    _seed_rests()
    conn = connect_memory()
    try:
        def stats(since: str) -> dict:
            return {w: {"calls": n, "ok": ok, "limits": lim, "tokens": tok or 0}
                    for w, n, ok, lim, tok in conn.execute(
                        "SELECT writer, COUNT(*), SUM(ok), SUM(limit_hit), SUM(tokens) FROM writer_calls "
                        f"WHERE at >= datetime('now', '{since}') GROUP BY writer")}
        day, week = stats("-1 day"), stats("-7 days")
        last = {w: (ok_at, err, err_at) for w, ok_at, err, err_at in conn.execute(
            "SELECT writer, MAX(CASE WHEN ok THEN at END), "
            "(SELECT error FROM writer_calls c2 WHERE c2.writer = c.writer AND NOT ok ORDER BY id DESC LIMIT 1), "
            "MAX(CASE WHEN NOT ok THEN at END) FROM writer_calls c GROUP BY writer")}
        kinds = conn.execute("SELECT writer, kind, COUNT(*) FROM writer_calls WHERE ok AND at >= datetime('now', '-1 day') "
                             "GROUP BY writer, kind").fetchall()
        # How long a job usually takes, per writer and kind (its last 10 successes), and per kind for writers
        # with no record yet: the "about N min left" on the page
        typical = {(w, k): t for w, k, t in conn.execute(
            "SELECT writer, kind, AVG(seconds) FROM (SELECT writer, kind, seconds, ROW_NUMBER() OVER "
            "(PARTITION BY writer, kind ORDER BY id DESC) AS n FROM writer_calls WHERE ok AND seconds > 0) "
            "WHERE n <= 10 GROUP BY writer, kind")}
        by_kind = dict(conn.execute("SELECT kind, AVG(seconds) FROM writer_calls WHERE ok AND seconds > 0 GROUP BY kind"))
    finally:
        conn.close()
    now = time.time()
    empty = {"calls": 0, "ok": 0, "limits": 0, "tokens": 0}
    out = []
    plans = _plans()
    for w in ALL_WRITERS:
        ok_at, err, err_at = last.get(w, (None, None, None))
        rest = _rest_until.get(w, 0) - now
        plan, account = plans.get(w.partition(":")[0], (w.partition(":")[0], None))
        busy = _busy.get(w)
        state = "off" if not _ready(w) else "working" if busy else "resting" if rest > 0 else "ready"
        out.append({"writer": w, "plan": plan, "account": account,
                    "state": state, "rests_for": max(0, int(rest)),
                    "now": busy and {"kind": busy["kind"], "what": busy["what"], "for": int(now - busy["since"]),
                                     "usual": int(typical.get((w, busy["kind"])) or by_kind.get(busy["kind"]) or 0)
                                     or None},
                    "day": day.get(w, empty), "week": week.get(w, empty),
                    "kinds": {k: n for wr, k, n in kinds if wr == w},
                    "last_ok": ok_at and ok_at.replace(" ", "T") + "Z",
                    "last_error": err, "last_error_at": err_at and err_at.replace(" ", "T") + "Z"})
    return {"writers": out}

SYSTEM = """You are an expert stock market teacher: a mix of market veteran, SEBI-registered research analyst, \
derivatives trader, quant and finance professor, focused on Indian markets (NSE/BSE) with full knowledge of \
global markets. Students ask anything, from basics to very hard questions. Answer like the best teacher would:

- Answer the actual question first, then explain the why and the mechanics. Never stop at a definition.
- Show formulas with every symbol defined, and work numeric examples step by step when numbers are involved.
- Give Indian rules with dates (they change); say when something may have changed recently.
- Point out traps, edge cases and common misconceptions.
- Be honest about uncertainty. No one can predict prices with certainty; never present a trade as guaranteed.
- Reply in the language and script the student used (English, Hindi, Gujarati or Hinglish), keeping \
technical terms in English.

You get excerpts from your own knowledge base below the question. Use them, but correct them if they are \
wrong or out of date. Use web search only for current data or facts the excerpts don't cover.

After the answer, if the knowledge base excerpts were missing something important for this question, add one \
line per missing topic in this form (it is removed before the student sees the answer):
<gap>short title of the topic the knowledge base should learn</gap>"""

REVIEW = """You are reviewing a student's work: a LightGBM model that predicts whether the next candle of an \
NSE stock or index closes up or down. Below are its walk-forward (out-of-sample) metrics, settings, features \
and the most important features. Review it as a strict quant mentor:

1. Is the accuracy meaningfully better than chance and than a naive baseline? Is it tradeable after costs \
(STT, brokerage, slippage)?
2. Likely problems: leakage, overfitting, non-stationarity, class imbalance, label noise, regime dependence.
3. Which market knowledge is the model missing (features, data, labels, horizons)? Be concrete.
4. The 3 to 5 changes most likely to help, in priority order, and how to test each honestly.

Reply in the language the student used for the request (default English)."""

HELP = """You are Drona, the teacher in a team of AI models that trade Indian stocks. Narad, a small local model \
that reads market news, could not settle the news items below: each mixes good and bad facts, or Narad was unsure. \
For each item, judge its likely effect on the share price of the named stocks (or on the sector or market) over \
the next trading session, the way experienced Indian market participants would react.

Reply with only a JSON array, one object per item:
[{"id": 12, "sentiment": -0.4, "confidence": 0.8, "reason": "one short sentence"}]
sentiment: -1 very bad, 0 no effect, +1 very good. confidence: 0 to 1. reason: what decides it, written as a \
lesson Narad can reuse on similar news. Lessons from your knowledge base may follow an item: use them when they \
apply, ignore them when they don't. For tracked stocks, the latest calls of Sanjay (a price-chart model) and \
Chanakya (an overnight world-markets model) may follow too, with how often each has been right: weigh them by \
that record."""


def _context(hits: list[dict]) -> tuple[str, list[dict]]:
    parts, used, size = [], {}, 0
    for h in hits:
        text = f"### {'Lesson' if h['kind'] == 'lesson' else 'Q&A'}: {h['title']}\n{h['body']}\n"
        if size + len(text) > CONTEXT_CHARS:
            text = text[: max(0, CONTEXT_CHARS - size)]
        if not text:
            break
        parts.append(text)
        size += len(text)
        used.setdefault(h["topic_id"], h["title"] if h["kind"] == "lesson" else None)
    return "\n".join(parts), [{"id": i, "title": t} for i, t in used.items()]


def _ollama(system: str, prompt: str) -> str:
    r = requests.post(f"{OLLAMA_URL}/api/chat", timeout=600, json={
        "model": OLLAMA_MODEL, "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    })
    r.raise_for_status()
    return r.json()["message"]["content"]


def _respond(system: str, prompt: str, web: bool) -> tuple[str, str]:
    """(answer, engine). DRONA_WRITERS first, local Ollama if none can answer."""
    try:
        return write(prompt, system, kind="answer", web=web, cloud=False, timeout=600,
                     what="your question on the Teacher page")
    except ClaudeError as writer_err:
        try:
            return _ollama(system, prompt), f"ollama:{OLLAMA_MODEL}"
        except Exception as e:
            raise ClaudeError(f"{writer_err} · Ollama: {e}")


def _save(conn, kind: str, question: str, answer: str, used: list[dict], engine: str) -> dict:
    cur = conn.execute("INSERT INTO asks (kind, question, answer, used, engine) VALUES (?,?,?,?,?)",
                       (kind, question, answer, json.dumps(used), engine))
    conn.commit()
    row = conn.execute("SELECT created_at FROM asks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"id": cur.lastrowid, "kind": kind, "question": question, "answer": answer,
            "used": used, "engine": engine, "created_at": row[0]}


def answer(question: str) -> dict:
    conn = connect()
    try:
        hits = search(conn, question, 10)
        context, used = _context(hits)
        # Titles for Q&A-only hits
        for u in used:
            if u["title"] is None:
                u["title"] = conn.execute("SELECT title FROM topics WHERE id = ?", (u["id"],)).fetchone()[0]
        prompt = (f"Student's question:\n{question}\n\n"
                  f"Knowledge base excerpts ({len(hits)} found):\n{context or '(nothing on this yet)'}")
        text, engine = _respond(SYSTEM, prompt, web=True)

        gaps = [g.strip() for g in re.findall(r"<gap>(.*?)</gap>", text, re.S) if g.strip()]
        for g in gaps[:3]:
            add_topic(conn, g, depth=1, why=f"a student asked: {question[:150]}", priority=GAP_PRIORITY)
        text = re.sub(r"\s*<gap>.*?</gap>", "", text, flags=re.S).strip()
        return {**_save(conn, "question", question, text, used, engine), "queued": gaps[:3]}
    finally:
        conn.close()


def review(note: str = "") -> dict:
    """Teacher's critique of the active prediction model for every interval."""
    app = connect_app()
    try:
        models = {}
        for (interval,) in app.execute("SELECT DISTINCT interval FROM models").fetchall():
            name, created, metrics = app.execute(
                "SELECT name, created_at, metrics FROM models WHERE interval = ? ORDER BY active DESC, id DESC LIMIT 1",
                (interval,),
            ).fetchone()
            count = app.execute("SELECT COUNT(*) FROM models WHERE interval = ?", (interval,)).fetchone()[0]
            models[interval] = {"name": name, "trained": created, "models_trained_so_far": count,
                                "metrics": json.loads(metrics or "{}")}
    finally:
        app.close()

    question = note.strip() or "Review my prediction models."
    prompt = (f"{question}\n\nTarget: next candle closes above the current close (up) or not (down).\n"
              f"Features: {', '.join(FEATURES)}\n\nActive models (walk-forward metrics):\n"
              f"{json.dumps(models, indent=1)}")
    conn = connect()
    try:
        text, engine = _respond(REVIEW, prompt, web=False)
        return _save(conn, "review", question, text, [], engine)
    finally:
        conn.close()


def status() -> dict:
    conn = connect()
    try:
        counts = dict(conn.execute("SELECT status, COUNT(*) FROM topics GROUP BY status").fetchall())
        learner = conn.execute("SELECT value FROM meta WHERE key = 'learner'").fetchone()
        recent = conn.execute(
            "SELECT t.id, t.title, t.depth, t.learned_at, l.level, l.model FROM topics t JOIN lessons l ON l.topic_id = t.id "
            "WHERE t.status = 'done' ORDER BY t.learned_at DESC LIMIT 12"
        ).fetchall()
        return {
            "learned": counts.get("done", 0),
            "queued": counts.get("pending", 0),
            "failed": counts.get("failed", 0),
            "qa": conn.execute("SELECT COUNT(*) FROM qa").fetchone()[0],
            "words": conn.execute("SELECT COALESCE(SUM(LENGTH(body) - LENGTH(REPLACE(body, ' ', '')) + 1), 0) "
                                  "FROM lessons").fetchone()[0],
            "deepest": conn.execute("SELECT COALESCE(MAX(depth), 0) FROM topics WHERE status = 'done'").fetchone()[0],
            # Every lesson queues 3-6 deeper topics, so the queue grows faster than it is learned; progress
            # per level (basics first) says more than the queue's length.
            "levels": [{"depth": d, "done": done, "total": total} for d, done, total in conn.execute(
                "SELECT depth, SUM(status = 'done'), COUNT(*) FROM topics WHERE syllabus IS NULL "
                "GROUP BY depth ORDER BY depth")],  # the syllabus has its own progress, below
            "learner": json.loads(learner[0]) if learner else None,
            "recent": [{"id": i, "title": t, "depth": d, "learned_at": a, "level": lv, "model": m}
                       for i, t, d, a, lv, m in recent],
            "syllabus": syllabus.view(conn),  # beginner to expert, level by level (app/syllabus.py)
        }
    finally:
        conn.close()


def history(limit: int = 30) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT id, kind, question, answer, used, engine, created_at FROM asks "
                            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": i, "kind": k, "question": q, "answer": a, "used": json.loads(u or "[]"), "engine": e,
                 "created_at": c} for i, k, q, a, u, e, c in rows]
    finally:
        conn.close()


def lesson(topic_id: int) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT t.title, t.depth, t.learned_at, l.level, l.body, l.sources FROM topics t "
            "JOIN lessons l ON l.topic_id = t.id WHERE t.id = ?", (topic_id,)
        ).fetchone()
        if row is None:
            return None
        title, depth, learned_at, level, body, sources = row
        qa = conn.execute("SELECT question, answer, difficulty FROM qa WHERE topic_id = ? ORDER BY id",
                          (topic_id,)).fetchall()
        children = conn.execute("SELECT id, title, status FROM topics WHERE parent_id = ? ORDER BY id",
                                (topic_id,)).fetchall()
        return {"id": topic_id, "title": title, "depth": depth, "learned_at": learned_at, "level": level,
                "body": body, "sources": json.loads(sources or "[]"),
                "qa": [{"question": q, "answer": a, "difficulty": d} for q, a, d in qa],
                "subtopics": [{"id": i, "title": t, "status": s} for i, t, s in children]}
    finally:
        conn.close()


def _help_answers(reply: str, ids: set[int]) -> dict[int, dict]:
    """{request id: {sentiment, confidence, reason}} from Drona's JSON reply; unusable entries are left out."""
    m = re.search(r"\[.*\]", reply, re.S)
    try:
        items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        items = []
    out = {}
    for it in items if isinstance(items, list) else []:
        try:
            i, sentiment, confidence = int(it["id"]), float(it["sentiment"]), float(it["confidence"])
        except (KeyError, TypeError, ValueError):
            continue
        if i in ids:
            out[i] = {"sentiment": min(max(sentiment, -1.0), 1.0), "confidence": min(max(confidence, 0.0), 1.0),
                      "reason": str(it.get("reason") or "")[:300]}
    return out


def help_models() -> int:
    """Answer the newest waiting help requests of the other models in one Claude call; returns how many.

    No Ollama fallback: the small local model is the one asking. The answer sits next to the asker's own
    reading, so Chitragupta can later score both.
    """
    conn, kb = connect_memory(), connect()
    try:
        batch = conn.execute("SELECT id, ref, question FROM help_requests WHERE status = 'pending' "
                             "ORDER BY id DESC LIMIT ?", (HELP_BATCH,)).fetchall()
        if not batch:
            return 0
        reply, used = write("\n\n".join(_help_item(kb, conn, i, ref, q) for i, ref, q in batch), HELP,
                            kind="help", timeout=600, what=f"{len(batch)} news items Narad wasn't sure about")
        answers = _help_answers(reply, {i for i, _, _ in batch})
        with conn:
            for i, _, _ in batch:
                if i in answers:
                    conn.execute("UPDATE help_requests SET status = 'answered', answer = ?, answered_by = ?, "
                                 "answered_at = datetime('now') WHERE id = ?",
                                 (json.dumps(answers[i]), f"drona:{used}", i))
                elif not answers:  # unreadable reply: skip the batch rather than spend Claude on it again
                    conn.execute("UPDATE help_requests SET status = 'skipped', answered_by = ?, "
                                 "answered_at = datetime('now') WHERE id = ?", (f"drona:{used}", i))
        if not answers:
            raise ClaudeError(f"help reply had no usable answers: {reply[:200]}")
        return len(answers)
    finally:
        conn.close()
        kb.close()


def _help_item(kb, mem, request_id: int, ref: str, question: str) -> str:
    """One help request as Drona sees it: the best-matching lessons and checked calls, and what the other
    models say about the tracked stocks it names."""
    lessons = "".join(f"\n- {h['title']}: {' '.join(h['body'].split())[:500]}" for h in search(kb, question, HELP_LESSONS))
    return (f"[id {request_id}]\n{question}" + (f"\nFrom your knowledge base:{lessons}" if lessons else "")
            + _other_models(mem, ref))


def _other_models(mem, ref: str) -> str:
    """Sanjay's and Chanakya's latest call on each tracked stock a news note names, with Chitragupta's record."""
    note = mem.execute("SELECT symbols FROM news_notes WHERE news_id = ?",
                       (int(ref.split(":")[1]),)).fetchone() if ref.startswith("news:") else None
    symbols = [s for s in json.loads(note[0]) if s in SYMBOLS] if note else []
    if not symbols:
        return ""
    record = {model: (n, right) for model, event, n, right, _ in track_record(mem) if not event}
    lines = []
    for symbol in symbols:
        said = []
        for model, what in (("sanjay", "Sanjay, chart"), ("chanakya", "Chanakya, world")):
            row = mem.execute("SELECT prob_up FROM signals WHERE model = ? AND symbol = ? ORDER BY as_of DESC LIMIT 1",
                              (model, symbol)).fetchone()
            if row:
                n, right = record.get(model, (0, None))
                said.append(f"{what}: {row[0]:.0%} chance up "
                            + (f"(right {right}% of {n} scored calls)" if n else "(not scored yet)"))
        if said:
            lines.append(f"\n- {symbol}: " + "; ".join(said))
    return f"\nOther models:{''.join(lines)}" if lines else ""


def _checked_topic(kb) -> int:
    """Id of the topic holding Drona's checked calls; made on first use, already done so the learner skips it."""
    row = kb.execute("SELECT id FROM topics WHERE key = ?", (topic_key(CHECKED),)).fetchone()
    if row:
        return row[0]
    topic_id = add_topic(kb, CHECKED, depth=1, why="kept automatically from help answers the market proved right")
    kb.execute("UPDATE topics SET status = 'done', learned_at = datetime('now') WHERE id = ?", (topic_id,))
    kb.execute("INSERT INTO lessons (topic_id, level, body, sources, model) VALUES (?, 'intermediate', ?, '[]', 'drona')",
               (topic_id, "News calls Drona made when Narad was unsure, kept once the market proved them right. "
                          "Each Q&A is one checked call: the news, Drona's reading, and what the stock did."))
    return topic_id


def learn_from_scores(mem, kb) -> tuple[int, int]:
    """Drona's side of the learning loop, over every call Chitragupta scored since the last look.

    A wrong call on a tracked stock that moved 3% or more becomes a high-priority study topic, so the learner
    researches what really moved it. A help answer of Drona's that the market proved right is kept as a
    checked lesson, which later answers find through the knowledge base search. Returns (queued, kept).
    """
    rows = mem.execute(
        "SELECT s.model, s.symbol, s.session, s.said, s.move, s.market, s.outcome, s.hit, s.scored_at, w.title, "
        "h.answer FROM scores s LEFT JOIN news w ON s.ref LIKE 'news:%' AND w.id = CAST(substr(s.ref, 6) AS INTEGER) "
        "LEFT JOIN help_requests h ON h.asker = 'narad' AND h.ref = s.ref AND h.status = 'answered' "
        "WHERE s.scored_at > ? ORDER BY s.scored_at", (get_meta(kb, "scores_seen") or "",)).fetchall()
    queued = kept = 0
    for model, symbol, session, said, move, market, outcome, hit, _, title, answer in rows:
        moved = "rose" if move > 0 else "fell"
        if hit == 0 and symbol in SYMBOLS and abs(move) >= MISS_MOVE:
            why = (f"{model.capitalize()} called {symbol} {'up' if said > 0 else 'down'} ({said:+.2f})"
                   + (f" after the news '{title}'" if title else "")
                   + f", but it {moved} {abs(move):.1%} that session (NIFTY 50 {market:+.1%}). Find what actually "
                     "moved it, and the general lesson for reading similar news or signals.")
            queued += add_topic(kb, f"Why {symbol} {moved} {abs(move):.1%} on {session}", depth=1, why=why,
                                priority=GAP_PRIORITY) is not None
        if model == "drona" and hit == 1 and answer and title:
            drona = json.loads(answer)
            question = f"{title}: good or bad for {symbol}?"
            reply = (f"Drona read it as {drona['sentiment']:+.2f}: {drona['reason']} The market agreed: {symbol} "
                     f"{moved} {abs(move):.1%} on {session}, {outcome:+.1%} against NIFTY 50.")
            topic_id = _checked_topic(kb)
            kb.execute("INSERT INTO qa (topic_id, question, answer, difficulty) VALUES (?, ?, ?, 'checked')",
                       (topic_id, question, reply))
            kb.execute("INSERT INTO search (title, body, kind, ref) VALUES (?, ?, 'qa', ?)", (question, reply, topic_id))
            kept += 1
    kb.commit()
    if rows:
        set_meta(kb, "scores_seen", rows[-1][8])
    return queued, kept


def mistakes() -> dict:
    """For the website: what Drona studies because a call went wrong, and the help answers it kept as checked."""
    kb = connect()
    try:
        studying = kb.execute("SELECT id, title, why, status, learned_at FROM topics WHERE priority = ? "
                              "AND title LIKE 'Why % on 20%' ORDER BY id DESC LIMIT 30", (GAP_PRIORITY,)).fetchall()
        checked = kb.execute("SELECT q.question, q.answer FROM qa q JOIN topics t ON t.id = q.topic_id "
                             "WHERE t.key = ? ORDER BY q.id DESC LIMIT 30", (topic_key(CHECKED),)).fetchall()
        return {"studying": [{"id": i, "title": t, "why": w, "status": s, "learned_at": a} for i, t, w, s, a in studying],
                "checked": [{"question": q, "answer": a} for q, a in checked]}
    finally:
        kb.close()


def study_scores() -> tuple[int, int]:
    """learn_from_scores on the shared memory and the knowledge base; returns (topics queued, lessons kept)."""
    mem, kb = connect_memory(), connect()
    try:
        return learn_from_scores(mem, kb)
    finally:
        mem.close()
        kb.close()
