"""The website's Data tab: what market history market.db holds, how many trading days are missing, and every bar.

Four lists, one per bar size (1 day, 1 hour, 15 minutes, 1 minute), 20 symbols a page; a symbol opens its bars,
20 a page, newest first. A list is every symbol the data keeper downloads: each listed NSE company, the indices
and (intraday only) the rupee pairs. "Days missing" counts the weekdays after a symbol's last bar up to the last
finished session; NSE holidays aren't known ahead, so a holiday can count as a missing day until the next one.
Reads market.db read-only, so it never waits on a download in progress.
"""
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone

from .chitragupta import IST
from .config import FOREX, MARKET_DB_PATH
from .download_yahoo import INDICES

PAGE = 20
INTERVALS = {"1d": "1 day", "1h": "1 hour", "15m": "15 minutes", "1m": "1 minute"}
KEPT_DAYS = {"1m": 30, "15m": 60, "1h": 730, "1d": None}  # how far back Yahoo serves each, for the Sync advice
REFERENCE = "^NSEI"  # NIFTY 50: trades every session, so its last bar is the market's last downloaded session


def _db() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{MARKET_DB_PATH.as_posix()}?mode=ro", uri=True, timeout=30)


def _ist(ts: int) -> datetime:
    return datetime.fromtimestamp(ts / 1000, timezone.utc).astimezone(IST)


def last_session(now: datetime | None = None) -> date:
    """The last NSE session that has finished (weekdays; holidays aren't known ahead)."""
    now = now or datetime.now(IST)
    day = now.date() if (now.hour, now.minute) >= (15, 30) else now.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def weekdays_after(day: date | None, until: date) -> int | None:
    """Weekdays after `day` up to and including `until`: the sessions missing since that day."""
    if day is None:
        return None
    n, d = 0, day + timedelta(days=1)
    while d <= until:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def _range(db, interval: str, symbol: str) -> tuple[int, str | None, str | None]:
    """(bars, first day, last day) of one symbol at one bar size."""
    if interval == "1d":
        n, first, last = db.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM yahoo_daily WHERE symbol = ?",
                                    (symbol,)).fetchone()
        return n, first, last
    n, first, last = db.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM yahoo_intraday WHERE symbol = ? AND interval = ?",
                                (symbol, interval)).fetchone()
    return n, first and _ist(first).date().isoformat(), last and _ist(last).date().isoformat()


def summary() -> dict:
    """Per bar size: the market's last downloaded session (NIFTY 50's last bar), the sessions missing since,
    and whether Yahoo still has them; and NSE's bhavcopy."""
    until = last_session()
    db = _db()
    try:
        rows = []
        for interval, label in INTERVALS.items():
            _, first, last = _range(db, interval, REFERENCE)
            missing = weekdays_after(date.fromisoformat(last), until) if last else None
            kept = KEPT_DAYS[interval]
            rows.append({"interval": interval, "label": label, "first": first, "last": last, "missing": missing,
                         "kept_days": kept,
                         # sessions older than Yahoo's window are gone for good: a sync can't bring them back
                         "recoverable": None if missing is None or kept is None
                         else (until - date.fromisoformat(last)).days <= kept})
        bhav = db.execute("SELECT MAX(date) FROM nse_bhav_days WHERE status = 'ok'").fetchone()[0]
        listed = db.execute("SELECT COUNT(*) FROM nse_listed").fetchone()[0]
    finally:
        db.close()
    return {"last_session": until.isoformat(), "intervals": rows, "listed": listed,
            "bhavcopy": {"last": bhav, "missing": weekdays_after(date.fromisoformat(bhav), until) if bhav else None}}


def _symbols(db, interval: str) -> list[str]:
    """Every symbol the data keeper downloads at this bar size, in the order of the list."""
    listed = [s for (s,) in db.execute("SELECT symbol FROM nse_listed ORDER BY symbol")]
    return INDICES + listed + (list(FOREX) if interval != "1d" else [])


def symbols(interval: str, page: int = 1, q: str = "") -> dict:
    """One page of the list for a bar size: each symbol's bars, first and last day, and days missing."""
    until = last_session()
    db = _db()
    try:
        names = dict(db.execute("SELECT symbol, name FROM nse_listed"))
        allsyms = [s for s in _symbols(db, interval) if q.upper() in s.upper() or q.lower() in (names.get(s) or "").lower()]
        pages = max(1, math.ceil(len(allsyms) / PAGE))
        page = min(max(1, page), pages)
        out = []
        for s in allsyms[(page - 1) * PAGE:page * PAGE]:
            n, first, last = _range(db, interval, s)
            out.append({"symbol": s, "name": names.get(s) or ("Index" if s.startswith("^") else "Rupee pair" if s in FOREX else None),
                        "bars": n, "first": first, "last": last,
                        "missing": weekdays_after(date.fromisoformat(last), until) if last else None})
    finally:
        db.close()
    return {"interval": interval, "page": page, "pages": pages, "total": len(allsyms), "rows": out}


def bars(interval: str, symbol: str, page: int = 1) -> dict:
    """One page of a symbol's bars at a bar size, newest first (times in IST)."""
    db = _db()
    try:
        if interval == "1d":
            total = db.execute("SELECT COUNT(*) FROM yahoo_daily WHERE symbol = ?", (symbol,)).fetchone()[0]
            pages = max(1, math.ceil(total / PAGE))
            page = min(max(1, page), pages)
            rows = [{"time": d, "open": o, "high": h, "low": lo, "close": c, "volume": v}
                    for d, o, h, lo, c, v in db.execute(
                        "SELECT date, open, high, low, close, volume FROM yahoo_daily WHERE symbol = ? "
                        "ORDER BY date DESC LIMIT ? OFFSET ?", (symbol, PAGE, (page - 1) * PAGE))]
        else:
            total = db.execute("SELECT COUNT(*) FROM yahoo_intraday WHERE symbol = ? AND interval = ?",
                               (symbol, interval)).fetchone()[0]
            pages = max(1, math.ceil(total / PAGE))
            page = min(max(1, page), pages)
            rows = [{"time": _ist(ts).strftime("%Y-%m-%d %H:%M"), "open": o, "high": h, "low": lo, "close": c, "volume": v}
                    for ts, o, h, lo, c, v in db.execute(
                        "SELECT ts, open, high, low, close, volume FROM yahoo_intraday WHERE symbol = ? AND interval = ? "
                        "ORDER BY ts DESC LIMIT ? OFFSET ?", (symbol, interval, PAGE, (page - 1) * PAGE))]
    finally:
        db.close()
    return {"interval": interval, "symbol": symbol, "page": page, "pages": pages, "total": total, "rows": rows}
