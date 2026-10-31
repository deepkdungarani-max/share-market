"""Krishna, the guide: watches every other model, fixes what is safe to fix, and guides them once a day.

Every 10 minutes Krishna checks the whole system, the way a charioteer watches the road:
- the data disk and its free space, and that every model's background thread is alive;
- that each model did its job on time (overview.models);
- Narad's news keys and backlog, Drona's AI plans, account 2's worker and the help-request queue;
- any model whose scored calls are worse than a coin toss.

What is safe it fixes on its own, and writes down: it restarts a stopped thread, gives topics and news items
that failed another try (every 6 hours, a few times at most), rests an AI plan that keeps failing for an hour
so the next one writes, and lets help requests older than three days go (that news has moved on). The rest
it reports on the website with what to do.

Once a day after 19:00 IST (or when you press "Review now"), Krishna reads every model's scorecard, the
day's problems and Drona's progress, asks the best AI plan for a review (teacher.write: Google AI Pro or
ChatGPT, never your Anthropic login), shows the advice for each model on the website and queues up to five
study topics for Drona where the models are weakest. Problems, fixes and reviews go to memory.db
(krishna_log, krishna_reports).

Usage: started by app/server.py; or one check by hand: python -m app.krishna
"""
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import (agy_cli, autolearn, backtest, chanakya, chitragupta, codex_cli, drona_call, keeper, knowledge, narad, overview,
               teacher, trikal)
from .chitragupta import IST, track_record
from .claude_cli import ClaudeError
from .config import MARKET_DIR, MARKETS, market_of
from .db import connect as connect_app
from .knowledge_db import add_topic, connect as connect_knowledge
from .memory_db import connect as connect_memory
from .system import disk_problem, logger, nap

EVERY = 10 * 60           # seconds between checks
FIRST_DELAY = 2 * 60      # let every model start before the first check
RETRY_EVERY = 6 * 3600    # seconds between giving failed topics and news items another try
REVIEW_AT = 19            # IST hour from which the daily review is due (after the close and the scoring)
FAILING = 3               # non-quota failures in a row before an AI plan is rested
FAILING_REST = 60 * 60    # how long such a plan rests
STALE_HELP_DAYS = 3       # pending help requests older than this are let go
LOW_RIGHT = 45.0          # % right below which a model with enough scored calls is flagged
LOW_MIN_CALLS = 100
MIN_FREE_GB = {"data disk": 10, "system disk": 5}
STUDY_PRIORITY = 9        # Krishna's study topics: right after the questions Drona couldn't answer (10)
MAX_STUDY = 5

say = logger("krishna")  # also appended to <market dir>/logs/krishna.log

# Every model's background thread and how to start it again (as app/server.py starts them)
THREADS = {"autolearn": autolearn.start, "chitragupta": chitragupta.start, "chanakya": chanakya.start,
           "trikal": trikal.start, "drona_call": drona_call.start, "keeper": keeper.start,
           "backtest_auto": backtest.start_auto}
if os.environ.get("CANDLECAST_LEARN", "1") != "0":
    THREADS["knowledge"] = knowledge.start
if os.environ.get("CANDLECAST_NARAD", "1") != "0":
    THREADS["narad"] = narad.start
NAMES = {"autolearn": "Sanjay", "chitragupta": "Chitragupta", "chanakya": "Chanakya", "trikal": "Trikal",
         "drona_call": "Drona's call",
         "knowledge": "Drona", "narad": "Narad", "keeper": "Data keeper",
         "backtest_auto": "Backtest auto run"}

_state = {"checked_at": None, "findings": []}  # the last check, for the website
_last_retry = 0.0
_lock = threading.Lock()  # one check at a time (the thread, the website's "check now")
_review_lock = threading.Lock()  # one review at a time


def finding(area: str, level: str, message: str, todo: str | None = None) -> dict:
    """level: problem (something stopped), warning (working, but worse than it should), info."""
    return {"area": area, "level": level, "message": message, "todo": todo}


def log(kind: str, area: str, message: str) -> None:
    say(f"{kind} · {area}: {message}")
    try:
        mem = connect_memory()
        try:
            with mem:
                mem.execute("INSERT INTO krishna_log (kind, area, message) VALUES (?,?,?)", (kind, area, message))
        finally:
            mem.close()
    except Exception:
        pass  # the disk may be the very problem


def _free_gb(path: str) -> float:
    return shutil.disk_usage(path).free / 1e9


def check(fix: bool = True) -> list[dict]:
    """Every check; with fix, also the safe fixes. Returns what is still wrong."""
    if problem := disk_problem():
        return [finding("Disk", "problem", problem, "Unlock (BitLocker) or reconnect the data disk")]
    found = []
    found += _threads(fix)
    mem, kb, app = connect_memory(), connect_knowledge(), connect_app()
    try:
        found += _models(mem, kb, app)
        found += _plans(mem, fix)
        found += _narad(mem)
        found += _drona(mem, kb, fix)
        if fix:
            _retry(mem, kb)
        found += _scores(mem)
    finally:
        mem.close()
        kb.close()
        app.close()
    for label, path, minimum in (("data disk", MARKET_DIR.anchor, MIN_FREE_GB["data disk"]),
                                 ("system disk", Path.home().anchor, MIN_FREE_GB["system disk"])):
        if (free := _free_gb(path)) < minimum:
            found.append(finding("Disk", "warning", f"The {label} ({path}) has only {free:.1f} GB free",
                                 "Free some space: the databases and the AI tools' histories keep growing"))
    return found


def _threads(fix: bool) -> list[dict]:
    alive = {t.name for t in threading.enumerate() if t.is_alive()}
    found = []
    for name, start in THREADS.items():
        if name in alive:
            continue
        if fix:
            start()
            log("fixed", NAMES[name], f"its background thread had stopped; started it again")
        else:
            found.append(finding(NAMES[name], "problem", "Its background thread has stopped",
                                 "Krishna restarts it at its next check"))
    return found


def _models(mem, kb, app) -> list[dict]:
    """Each model's own health, as the Overview shows it, and the data keeper's: late or down is a finding."""
    return [finding(m["name"], "problem" if m["state"] == "down" else "warning", f"{m['state'].title()}: {m['detail']}")
            for m in overview.models(mem, kb, app) + [keeper.health()] if m["state"] in ("down", "late")]


def _plans(mem, fix: bool) -> list[dict]:
    """Drona's AI plans: all used up, one that keeps failing (rested so the next writes), account 2's worker,
    ChatGPT's sign-in."""
    found = []
    writers = teacher.writers_view()["writers"]
    if writers and not any(w["state"] in ("ready", "working") for w in writers):
        soonest = min((w["rests_for"] for w in writers if w["state"] == "resting"), default=0)
        found.append(finding("Drona", "warning", "Every AI plan is out of quota or not set up, so Drona waits"
                             + (f": the first resets in about {max(1, soonest // 60)} min" if soonest else ""),
                             "Nothing to do: Drona carries on when a quota resets"))
    now = time.time()
    for w in writers:
        last = mem.execute("SELECT ok, limit_hit, error FROM writer_calls WHERE writer = ? ORDER BY id DESC LIMIT ?",
                           (w["writer"], FAILING)).fetchall()
        failing = len(last) == FAILING and all(not ok and not lim for ok, lim, _ in last)
        if failing and teacher._rest_until.get(w["writer"], 0) < now:
            if fix:
                teacher._rest_until[w["writer"]] = now + FAILING_REST
                log("fixed", "Drona", f"{w['writer']} failed {FAILING} times in a row ({(last[0][2] or '')[:120]}); "
                                      "rested it for an hour so the next model writes")
            else:
                found.append(finding("Drona", "warning", f"{w['writer']} failed {FAILING} times in a row",
                                     "Krishna rests it for an hour at its next check"))
    if agy_cli.QUEUE.exists() and not agy_cli.available(2):
        found.append(finding("Drona", "problem", "Google AI Pro account 2's worker isn't answering",
                             r"Run tools\agy2\diag.ps1 in an Administrator PowerShell"))
    elif agy_cli.available(2) and agy_cli.parallel(2) < 2:
        found.append(finding("Narad", "warning", "Account 2's worker is the old one that runs one job at a time, so "
                             "Narad can't read news with account 2 (it would wait behind Drona's lessons)",
                             "Restart its task once in an Administrator PowerShell: Stop-ScheduledTask 'CandleCast "
                             "agy2 worker'; Start-ScheduledTask 'CandleCast agy2 worker' (or restart the laptop)"))
    if Path(codex_cli.CODEX).exists() and not codex_cli.available():
        found.append(finding("Drona", "info", "ChatGPT Pro isn't signed in, so its learner waits",
                             r"Run tools\codex-login.ps1 and sign in"))
    if fix and (agy_cli.QUEUE / "out").exists():
        # Replies nobody came for: their caller stopped waiting (a server restart, the laptop's sleep)
        stale = [f for f in (agy_cli.QUEUE / "out").glob("*.json")
                 if f.name != "heartbeat.json" and time.time() - f.stat().st_mtime > 3600]
        for f in stale:
            f.unlink(missing_ok=True)
        if stale:
            log("fixed", "Drona", f"removed {len(stale)} replies of account 2's worker that nobody collected "
                                  "(their callers had stopped, at a restart or while the laptop slept)")
    return found


def _narad(mem) -> list[dict]:
    found = []
    readers = list(narad.READERS.values())
    now = time.time()
    if readers and all(r.get("paused") or narad._resting.get(r["key"], 0) > now for r in readers):
        found.append(finding("Narad", "warning", "Every news reader (AI plans and keys) is paused or out of quota, "
                             "so news waits to be read" + (" by the slow local model" if narad.ollama_reads() else ""),
                             "Resume a reader on the API keys tab, or wait for a plan's quota to reset"))
    unread = mem.execute("SELECT COUNT(*) FROM news WHERE status = 'new' AND priority > 0").fetchone()[0]
    if unread > 500:
        found.append(finding("Narad", "warning", f"{unread:,} news items of tracked companies wait to be read",
                             "More news keys read faster: add one on the API keys tab"))
    return found


def _retry(mem, kb) -> None:
    """Every RETRY_EVERY: news items Narad couldn't read and topics Drona couldn't learn get one more try each,
    up to twice their usual tries (a reader or AI plan may simply have been down)."""
    global _last_retry
    if time.time() - _last_retry < RETRY_EVERY:
        return
    _last_retry = time.time()
    with mem:
        news = mem.execute("UPDATE news SET status = 'new' WHERE status = 'failed' AND attempts < ?",
                           (2 * narad.MAX_ATTEMPTS,)).rowcount
    if news:
        log("fixed", "Narad", f"gave {news} news items it couldn't read another try")
    with kb:
        topics = kb.execute("UPDATE topics SET status = 'pending' WHERE status = 'failed' AND attempts < ?",
                            (2 * knowledge.MAX_ATTEMPTS,)).rowcount
    if topics:
        log("fixed", "Drona", f"gave {topics} topics it couldn't learn another try")


def _drona(mem, kb, fix: bool) -> list[dict]:
    found = []
    if fix:
        with mem:
            stale = mem.execute("UPDATE help_requests SET status = 'skipped', answered_by = 'krishna:stale', "
                                "answered_at = datetime('now') WHERE status = 'pending' AND created_at < ?",
                                ((datetime.now(timezone.utc) - timedelta(days=STALE_HELP_DAYS)).strftime("%Y-%m-%d %H:%M:%S"),)
                                ).rowcount
        if stale:
            log("fixed", "Drona", f"let {stale} help requests older than {STALE_HELP_DAYS} days go: that news has "
                                  "moved on, and newer ones need the time")
    pending = mem.execute("SELECT COUNT(*) FROM help_requests WHERE status = 'pending'").fetchone()[0]
    if pending > 500:
        found.append(finding("Drona", "warning", f"{pending:,} help requests wait for Drona",
                             "Drona answers 10 per round between lessons; more AI plans would help"))
    failed = kb.execute("SELECT COUNT(*) FROM topics WHERE status = 'failed'").fetchone()[0]
    if failed >= 10:
        found.append(finding("Drona", "info", f"{failed} topics failed every try and were set aside"))
    return found


def _scores(mem) -> list[dict]:
    """Models doing worse than a coin, overall and (for the daily calls) per market."""
    found = []
    for model, event, n, right, _ in track_record(mem):
        if not event and n >= LOW_MIN_CALLS and right is not None and right < LOW_RIGHT:
            found.append(finding(model.title(), "warning", f"Right only {right}% on {n:,} scored calls: worse than "
                                 "a coin toss", "Krishna's daily review looks at why and queues study topics"))
    per_market: dict[tuple[str, str], list[int]] = {}
    for model, symbol, hit in mem.execute("SELECT model, symbol, hit FROM scores WHERE ref LIKE 'signal:%' "
                                          "AND hit IS NOT NULL"):
        per_market.setdefault((model, market_of(symbol)), []).append(hit)
    for (model, market), hits in sorted(per_market.items()):
        right = 100 * sum(hits) / len(hits)
        if market == "forex" and len(hits) >= 40 and right < LOW_RIGHT:
            found.append(finding(model.title(), "warning", f"Right only {right:.1f}% on {len(hits)} rupee-pair calls"))
    return found


def run_check() -> dict:
    """One check with fixes; logs problems that appeared or went away. Returns the state for the website."""
    with _lock:
        findings = check(fix=True)
        before = {(f["area"], f["message"]) for f in _state["findings"]}
        now_set = {(f["area"], f["message"]) for f in findings}
        for f in findings:
            if (f["area"], f["message"]) not in before and f["level"] != "info":
                log(f["level"], f["area"], f["message"])
        for area, message in before - now_set:
            log("resolved", area, message)
        _state.update(checked_at=datetime.now(IST).isoformat(timespec="seconds"), findings=findings)
        return dict(_state)


# The daily review

GUIDE = """You are Krishna, the guide of a team of AI models that predict Indian stocks (NSE) and rupee currency \
pairs for the next session: Narad reads the news, Sanjay reads the chart (LightGBM on candles), Chanakya reads \
the overnight world markets, Trikal averages Sanjay and Chanakya into the main call, Drona is the teacher who \
studies the market and answers Narad's doubts, and Chitragupta scores every call against what the market did.

Below are today's facts as JSON. Review the team like a strict, kind coach: what works, what doesn't, and the \
next concrete step for each model. Be honest: a model near 50% right has no edge, say so. Use only these facts; \
never invent numbers. Then pick up to 5 study topics for Drona that would fix the weakest spots you see (for \
example a kind of news Narad keeps misreading, or what moves the rupee pairs). Each topic must be narrow enough \
for one lesson.

Reply with only a JSON object, no other text:
{"summary": "4 to 8 plain English sentences on how the team is doing",
 "advice": [{"model": "Narad|Sanjay|Chanakya|Trikal|Drona|Chitragupta", "advice": "one or two sentences"}],
 "study": [{"title": "topic for Drona", "why": "one line: which weakness it fixes"}]}"""


def facts() -> dict:
    """What the review is based on: every scorecard, the models' tested accuracy, Drona's progress, problems."""
    mem, app = connect_memory(), connect_app()
    try:
        record = track_record(mem)
        per_market: dict[str, dict] = {}
        for model, symbol, hit, outcome, said in mem.execute(
                "SELECT model, symbol, hit, outcome, said FROM scores WHERE ref LIKE 'signal:%' AND hit IS NOT NULL"):
            m = per_market.setdefault(f"{model} {market_of(symbol)}", {"calls": 0, "right": 0})
            m["calls"] += 1
            m["right"] += hit
        tested = {f"{market} {interval}": {k: v for k, v in json.loads(metrics or "{}").items()
                                           if k in ("accuracy", "baseline_up_rate", "confident_accuracy", "n")}
                  for market, interval, metrics in app.execute(
                      "SELECT market, interval, metrics FROM models WHERE active = 1")}
        log_24h = [f"{kind} · {area}: {message}" for kind, area, message in mem.execute(
            "SELECT kind, area, message FROM krishna_log WHERE at >= datetime('now', '-1 day') ORDER BY id DESC LIMIT 30")]
        pipeline = trikal.view()["pipeline"]
    finally:
        mem.close()
        app.close()
    status = teacher.status()
    return {
        "date": datetime.now(IST).date().isoformat(),
        "scorecard": [{"model": m, "calls": n, "right_pct": r, "gain_pct": g} for m, e, n, r, g in record if not e],
        "by_kind_of_news": [{"model": m, "event": e, "calls": n, "right_pct": r} for m, e, n, r, g in record
                            if e and n >= 15][:40],
        "daily_calls_by_market": {k: {"calls": v["calls"], "right_pct": round(100 * v["right"] / v["calls"], 1)}
                                  for k, v in per_market.items()},
        "chart_models_walk_forward_tested": tested,
        "chanakya_tested": "stocks 53.5% right on 2017-2026 (base rate 50.8%); rupee pairs 47% on 2025-2026",
        "news_pipeline_24h": pipeline,
        "drona": {"lessons": status["learned"], "queued": status["queued"], "levels": status.get("levels"),
                  "hard_qa": status["qa"]},
        "problems_now": [f"{f['area']}: {f['message']}" for f in _state["findings"]],
        "krishna_log_24h": log_24h,
    }


def review(force: bool = False) -> dict | None:
    """Today's review, if it's due (after REVIEW_AT, not made yet) or forced; None when not due."""
    now = datetime.now(IST)
    day = now.date().isoformat()
    mem = connect_memory()
    try:
        done = mem.execute("SELECT 1 FROM krishna_reports WHERE day = ?", (day,)).fetchone()
    finally:
        mem.close()
    if not force and (done or now.hour < REVIEW_AT):
        return None
    with _review_lock:
        text, writer = teacher.write(json.dumps(facts(), ensure_ascii=False, indent=1), GUIDE, kind="guide",
                                     cloud=False, timeout=900, what="Krishna's daily review of every model")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        report = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        report = None
    if not isinstance(report, dict) or not report.get("summary"):
        raise ClaudeError(f"the review came back unreadable: {text[:200]}")
    study = [s for s in report.get("study") or [] if isinstance(s, dict) and s.get("title")][:MAX_STUDY]
    kb = connect_knowledge()
    try:
        queued = [s["title"] for s in study
                  if add_topic(kb, s["title"], depth=1, why=f"Krishna: {s.get('why') or 'a weak spot of the team'}",
                               priority=STUDY_PRIORITY) is not None]
        kb.commit()
    finally:
        kb.close()
    report = {"summary": str(report["summary"]),
              "advice": [a for a in report.get("advice") or [] if isinstance(a, dict) and a.get("advice")],
              "study": study, "queued": queued}
    mem = connect_memory()
    try:
        with mem:
            mem.execute("INSERT OR REPLACE INTO krishna_reports (day, report, writer) VALUES (?,?,?)",
                        (day, json.dumps(report, ensure_ascii=False), writer))
    finally:
        mem.close()
    log("review", "Krishna", f"daily review written by {writer}; {len(queued)} study topics queued for Drona")
    return report


def view() -> dict:
    """For the website: what is wrong now, what Krishna fixed or found lately, and the latest review."""
    if _state["checked_at"] is None:
        with _lock:
            _state.update(checked_at=datetime.now(IST).isoformat(timespec="seconds"), findings=check(fix=False))
    mem = connect_memory()
    try:
        entries = mem.execute("SELECT kind, area, message, at FROM krishna_log ORDER BY id DESC LIMIT 60").fetchall()
        row = mem.execute("SELECT day, report, writer, created_at FROM krishna_reports ORDER BY day DESC LIMIT 1").fetchone()
    finally:
        mem.close()
    return {
        "checked_at": _state["checked_at"],
        "findings": _state["findings"],
        "log": [{"kind": k, "area": a, "message": msg, "at": at.replace(" ", "T") + "Z"} for k, a, msg, at in entries],
        "review": row and {"day": row[0], **json.loads(row[1]), "writer": row[2],
                           "at": row[3].replace(" ", "T") + "Z"},
        "markets": list(MARKETS),
    }


def health() -> dict:
    """Krishna's own line on the Overview, like the other models'."""
    checked = _state["checked_at"]
    problems = [f for f in _state["findings"] if f["level"] == "problem"]
    warnings = [f for f in _state["findings"] if f["level"] == "warning"]
    late = checked is None or datetime.now(IST) - datetime.fromisoformat(checked) > timedelta(seconds=3 * EVERY)
    return {"key": "krishna", "name": "Krishna", "role": "Guide", "last": checked,
            "state": "waiting" if checked is None else "late" if late else "ok",
            "detail": ("First check within 2 minutes of the server starting" if checked is None else
                       f"{len(problems)} problems, {len(warnings)} warnings" if problems or warnings
                       else "Everything is running")}


def run() -> None:
    time.sleep(FIRST_DELAY)
    while True:
        try:
            run_check()
        except Exception as e:  # the disk, a DB lock…: try again next round
            say(f"check failed — {type(e).__name__}: {e}")
        try:
            review()
        except Exception as e:  # out of quota, unreadable reply: retried at the next check
            say(f"review not made — {type(e).__name__}: {e}")
        nap(EVERY)


def start() -> None:
    threading.Thread(target=run, daemon=True, name="krishna").start()


if __name__ == "__main__":
    for f in check(fix=False):
        print(f"{f['level']:<8} {f['area']:<12} {f['message']}" + (f"  → {f['todo']}" if f["todo"] else ""))
