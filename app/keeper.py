"""The data keeper: downloads the market's history into market.db every day, on its own, so no day goes missing.

Yahoo keeps 1-minute bars for only about 30 days (15-minute for 60, hourly for 2 years), and NSE publishes each
day's bhavcopy in the evening: whatever isn't fetched in time is gone for good. While the server runs, the
keeper starts both downloaders once every weekday after 19:00 IST (after the close and the bhavcopy), and right
away when a weekday was missed because the server was off or the laptop asleep:
- app.download_nse: every NSE security's daily prices since 1994, only the days market.db doesn't have yet;
- app.download_yahoo: 1-minute, 15-minute, hourly and daily bars of every listed company, the indices and the
  rupee pairs (no daily for the pairs), only what market.db doesn't have yet.
They run one after the other as background processes at low priority, writing their own logs (nse.log,
yahoo.log), and resume where they stopped. A run that NSE or Yahoo cut short is tried again an hour later.

The app's own candles (trading.db: the tracked stocks and pairs) don't wait for this: Sanjay catches them up
every hour (fetch.catch_up).
"""
import json
import re
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta

from .chitragupta import IST
from .config import MARKET_DIR, ROOT
from .system import PROGRESS, locked, logger, nap

STATE = MARKET_DIR / "keeper.json"  # {"done": "YYYY-MM-DD", "last": {...the last run}}
RUN_AT = 19                         # IST hour from which a weekday's downloads are due
CHECK_EVERY = 10 * 60
RETRY_AFTER = 60 * 60               # after a run NSE or Yahoo cut short
FIRST_DELAY = 3 * 60                # let the models start first
JOBS = [("NSE bhavcopy", "app.download_nse"), ("Yahoo 1m/15m/1h/daily", "app.download_yahoo")]
CODES = {0: "done", 2: "cut short: the site kept refusing", 3: "already running in another window"}

say = logger("keeper")
_running: str | None = None  # the job in progress, for the website
_run_lock = threading.Lock()  # one run at a time: the daily schedule, or "Sync now" on the website


def _state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _last_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def due(now: datetime, done: str | None) -> bool:
    """Today's run once it's 19:00 on a weekday; any missed weekday's right away."""
    today = now.date()
    last = _last_weekday(today)
    if last == today and now.hour < RUN_AT:
        last = _last_weekday(today - timedelta(days=1))  # today's isn't due yet, but yesterday's must be done
    return done is None or date.fromisoformat(done) < last


def run_once() -> bool:
    """Both downloads, one after the other; True when both finished. False at once if a run is going on."""
    if not _run_lock.acquire(blocking=False):
        return False
    try:
        return _run_both()
    finally:
        _run_lock.release()


def _locked_elsewhere() -> str | None:
    """A downloader running in another process (one started before a server restart, or download_market_data.bat):
    each holds its lock file while it runs (see system.single_instance)."""
    return next((name for name, lock in (("Yahoo", "download_yahoo"), ("NSE bhavcopy", "download_nse")) if locked(lock)),
                None)


YAHOO_STEPS = ["1m", "15m", "1h", "1d"]  # the order app.download_yahoo fetches in
_STEP_LINE = re.compile(r"^\[(\S+ \S+)\] \[(1m|15m|1h|1d)\] ([\d,]+)/([\d,]+) .*~(\d+) min left")
_STEP_START = re.compile(r"^\[(\S+ \S+)\] \[(1m|15m|1h|1d)\] [\d,]+ to fetch")
_DONE = re.compile(r"^\[(\S+ \S+)\] Done\.")


def _yahoo_log() -> list[str]:
    try:
        with open(MARKET_DIR / "logs" / "yahoo.log", "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200_000))
            return f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []


def _log_progress(lines: list[str]) -> dict | None:
    """A Yahoo download's progress from its log (every 100 symbols), for one that doesn't write progress.json
    (started by an older version)."""
    for line in reversed(lines):
        if m := _STEP_LINE.match(line):
            at = datetime.fromisoformat(m.group(1))
            if (datetime.now() - at).total_seconds() > 10 * 60:
                return None
            return {"job": "Yahoo", "step": m.group(2), "done": int(m.group(3).replace(",", "")),
                    "total": int(m.group(4).replace(",", "")), "seconds_left": int(m.group(5)) * 60,
                    "at": at.isoformat(timespec="seconds")}
    return None


def _step_seconds(lines: list[str]) -> dict[str, float]:
    """How long each Yahoo step took in the last run that finished: what the steps still to come will take."""
    starts: list[tuple[str, datetime]] = []
    last: dict[str, float] = {}
    for line in lines:
        if m := _STEP_START.match(line):
            starts.append((m.group(2), datetime.fromisoformat(m.group(1))))
        elif m := _DONE.match(line):
            done_at = datetime.fromisoformat(m.group(1))
            run = starts[-4:]
            if [step for step, _ in run] == YAHOO_STEPS:  # a full run (1m, 15m, 1h, 1d), not a partial one
                ends = [t for _, t in run[1:]] + [done_at]
                last = {step: (end - t).total_seconds() for (step, t), end in zip(run, ends)}
            starts = []
    return last


def _with_total(progress: dict, lines: list[str]) -> dict:
    """Adds the whole run's time left to a Yahoo step's: the steps still to come take what they took last time
    (or, never timed, as long per symbol as the step in progress)."""
    if progress.get("job") != "Yahoo" or progress.get("step") not in YAHOO_STEPS or progress.get("seconds_left") is None:
        return progress
    later = YAHOO_STEPS[YAHOO_STEPS.index(progress["step"]) + 1:]
    timed = _step_seconds(lines)
    per_symbol = progress["seconds_left"] / max(1, progress["total"] - progress["done"])
    rest = sum(timed.get(step, per_symbol * progress["total"]) for step in later)
    return {**progress, "all_seconds_left": round(progress["seconds_left"] + rest), "steps_left": later}


def _fresh_progress() -> dict | None:
    """The progress a download wrote in the last 3 minutes: one is running, maybe started before a server restart."""
    try:
        p = json.loads(PROGRESS.read_text(encoding="utf-8"))
        return p if time.time() - datetime.fromisoformat(p["at"]).timestamp() < 3 * 60 else None
    except (OSError, ValueError, KeyError):
        return None


def sync_now() -> bool:
    """Start both downloads now, in the background (the website's Sync button); False if they are running."""
    if _run_lock.locked() or _fresh_progress() or _locked_elsewhere():
        return False
    threading.Thread(target=run_once, daemon=True, name="keeper sync").start()
    return True


def _run_both() -> bool:
    global _running
    results = {}
    for name, module in JOBS:
        _running = name
        say(f"{name}: started")
        started = time.time()
        try:
            code = subprocess.run(
                [sys.executable, "-X", "utf8", "-u", "-m", module], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
        except OSError as e:
            code = -1
            say(f"{name}: couldn't start ({e})")
        results[name] = {"code": code, "minutes": round((time.time() - started) / 60, 1)}
        say(f"{name}: {CODES.get(code, f'failed (exit code {code})')} after {results[name]['minutes']} min")
    _running = None
    ok = all(r["code"] == 0 for r in results.values())
    state = _state()
    state["last"] = {"at": datetime.now(IST).isoformat(timespec="seconds"), "results": results, "ok": ok}
    if ok:
        state["done"] = datetime.now(IST).date().isoformat()
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return ok


def run() -> None:
    nap(FIRST_DELAY)
    while True:
        try:
            if due(datetime.now(IST), _state().get("done")) and not _locked_elsewhere():
                if not run_once():
                    nap(RETRY_AFTER)
                    continue
        except Exception as e:  # the disk, a full disk…: try again at the next check
            say(f"error — {type(e).__name__}: {e}")
        nap(CHECK_EVERY)


def view() -> dict:
    """For Krishna, the Overview and the Data tab: when the downloads last finished, what the last run did, what
    runs now and how far it got (the downloaders write their progress every few symbols or days)."""
    state = _state()
    lines = _yahoo_log()
    now_progress = _fresh_progress()
    running = _running or (now_progress and now_progress["job"]) or _locked_elsewhere()
    if running and now_progress is None:
        now_progress = _log_progress(lines)
    if now_progress:
        now_progress = _with_total(now_progress, lines)
    return {"done": state.get("done"), "last": state.get("last"), "running": running, "progress": now_progress,
            "due": due(datetime.now(IST), state.get("done"))}


def health() -> dict:
    """The keeper's line on the Overview, like the models'."""
    v = view()
    last = v["last"] or {}
    if v["running"]:
        state, detail = "ok", f"Downloading now: {v['running']}"
    elif v["done"] and not v["due"]:
        state, detail = "ok", f"Market history complete up to {v['done']}"
    elif v["done"] is None and not last:
        state, detail = "waiting", "First download starts within 3 minutes of the server starting"
    else:
        state, detail = "late", (f"Last full download {v['done'] or 'never'}"
                                 + (f"; last try: {', '.join(f'{k} {CODES.get(r['code'], r['code'])}' for k, r in last.get('results', {}).items())}"
                                    if last else ""))
    return {"key": "keeper", "name": "Data keeper", "role": "Daily downloads (1m, 15m, 1h, daily)",
            "last": last.get("at"), "state": state, "detail": detail}


def start() -> None:
    threading.Thread(target=run, daemon=True, name="keeper").start()
