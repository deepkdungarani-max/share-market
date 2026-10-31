"""For the website's home page: whether every model is doing its job on schedule, Trikal's strongest calls,
the scorecard and the latest news on tracked stocks.

Each model gets a state: ok (did its job on schedule), waiting (its next run isn't due yet), late (overdue:
usually the server or learner isn't running), down (something it needs is off, e.g. Ollama) or off (never ran).
"""
import json
from datetime import datetime, timezone

import requests

from . import narad, trikal
from .chanakya import CLOSE, FROM_HOUR
from .chitragupta import FINAL_AT, INDEX, IST, closes
from .config import OLLAMA_URL, SYMBOLS
from .db import connect as connect_app
from .knowledge_db import connect as connect_knowledge, get_meta
from .memory_db import connect as connect_memory

PULL_LATE = 40   # minutes without a news pull before Narad counts as late (it pulls every 15)
LEARN_LATE = 30  # minutes without the learner reporting before Drona counts as late


def _utc(sqlite_time: str | None) -> str | None:
    """SQLite's datetime('now') text (UTC, no zone) as ISO 8601 with Z, for the browser."""
    return sqlite_time.replace(" ", "T") + "Z" if sqlite_time else None


def _minutes_ago(sqlite_time: str | None) -> float | None:
    if not sqlite_time:
        return None
    then = datetime.strptime(sqlite_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 60


def _ollama_up() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


def models(mem, kb, app) -> list[dict]:
    now = datetime.now(IST)
    today = now.date().isoformat()
    days = sorted(closes(app).get(INDEX, {}))
    final = [d for d in days if d < today or (d == today and now.hour >= FINAL_AT)]
    last_final = final[-1] if final else None  # Sanjay calls after this session's close
    before_today = [d for d in days if d < today]
    last_before = before_today[-1] if before_today else None  # Chanakya and Trikal call on the session after it
    # Chanakya and Trikal call only between 06:00 and the 15:30 close; outside that a missing call isn't late yet
    morning_due = now.weekday() < 5 and (FROM_HOUR, 30) <= (now.hour, now.minute) < CLOSE
    one = lambda sql, *args: mem.execute(sql, args).fetchone()[0]

    stocks = ",".join(f"'{s}'" for s in SYMBOLS)  # the rupee pairs keep their own calendar (chanakya.calendars)

    def signal_model(key: str) -> tuple[str | None, str | None]:
        return mem.execute(f"SELECT as_of, MAX(created_at) FROM signals WHERE model = ? AND symbol IN ({stocks}) AND "
                           f"as_of = (SELECT MAX(as_of) FROM signals WHERE model = ? AND symbol IN ({stocks}))",
                           (key, key)).fetchone()

    out = []

    pulled = one("SELECT MAX(fetched_at) FROM news")
    read_24h = one("SELECT COUNT(*) FROM news_notes WHERE created_at >= datetime('now', '-1 day')")
    unread = one("SELECT COUNT(*) FROM news WHERE status = 'new' AND priority > 0")
    ollama = bool(narad.READERS) or _ollama_up()  # with cloud keys, Ollama is only the backup
    ago = _minutes_ago(pulled)
    out.append({"key": "narad", "name": "Narad", "role": "News reader", "last": _utc(pulled),
                "state": "off" if ago is None else "down" if not ollama else "ok" if ago <= PULL_LATE else "late",
                "detail": (f"{read_24h:,} read in 24 h, {unread:,} waiting" if ollama
                           else "Ollama isn't running, so news is collected but not read")})

    learner = json.loads(get_meta(kb, "learner") or "null")
    pending = one("SELECT COUNT(*) FROM help_requests WHERE status = 'pending'")
    learned_at = learner and datetime.fromisoformat(learner["at"]).replace(tzinfo=IST).astimezone(timezone.utc)
    learn_ago = learned_at and (datetime.now(timezone.utc) - learned_at).total_seconds() / 60
    out.append({"key": "drona", "name": "Drona", "role": "Teacher and helper",
                "last": learned_at.strftime("%Y-%m-%dT%H:%M:%SZ") if learned_at else None,
                "state": "off" if learner is None else "ok" if learn_ago <= LEARN_LATE else "late",
                "detail": f"{learner['state'] if learner else 'Never ran'} · {pending} help {'request' if pending == 1 else 'requests'} waiting"})

    as_of, made = signal_model("sanjay")
    out.append({"key": "sanjay", "name": "Sanjay", "role": "Chart", "last": _utc(made),
                "state": "off" if as_of is None else "ok" if as_of == last_final else "late",
                "detail": f"Call for the session after {as_of}" if as_of else "No call yet: it calls after each 4 PM close"})

    for key, name, role in (("chanakya", "Chanakya", "World markets"), ("trikal", "Trikal", "Main prediction")):
        as_of, made = signal_model(key)
        state = ("ok" if as_of is not None and as_of == last_before else "late" if morning_due
                 else "waiting" if as_of is None or as_of < (last_before or "") else "ok")
        out.append({"key": key, "name": name, "role": role, "last": _utc(made), "state": state,
                    "detail": (f"Call for the session after {as_of}" if as_of else "No call yet")
                    + ("" if morning_due else " · next call from 06:00 IST on weekdays")})

    scored = one("SELECT MAX(scored_at) FROM scores")
    overdue = one(f"SELECT COUNT(*) FROM signals g WHERE g.as_of < ? AND g.symbol IN ({stocks}) AND NOT EXISTS "
                  "(SELECT 1 FROM scores s WHERE s.model = g.model AND s.ref = 'signal:' || g.as_of "
                  "AND s.symbol = g.symbol)", last_final or "")
    total = one("SELECT COUNT(*) FROM scores")
    out.append({"key": "chitragupta", "name": "Chitragupta", "role": "Judge", "last": _utc(scored),
                "state": "late" if overdue else "ok" if total else "waiting",
                "detail": f"{total:,} calls scored" + (f", {overdue} overdue" if overdue else "")
                          + ("" if total else " · scores come after each 4 PM close")})
    return out


def view() -> dict:
    mem, kb, app = connect_memory(), connect_knowledge(), connect_app()
    try:
        health = models(mem, kb, app)
    finally:
        mem.close()
        kb.close()
        app.close()
    calls = trikal.view()
    strongest = sorted(calls["calls"], key=lambda c: -abs(c["prob_up"] - 0.5))[:5]
    return {"models": health, "as_of": calls["as_of"], "made_at": calls["made_at"], "strongest": strongest,
            "scorecard": calls["scorecard"], "pipeline": calls["pipeline"],
            "headlines": narad.feed("tracked", limit=6)["notes"]}
