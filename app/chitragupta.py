"""Chitragupta, the judge: scores every call the models make against what the market actually did.

A Narad note (and Drona's answer on it, if any) is a call on each stock it names; market-wide news is a
call on NIFTY 50. A call is judged on the first session the news could reach: a trading day's own session
when published before 09:15 IST, otherwise the next one. What counts is the stock's close-to-close move
that session minus NIFTY 50's, so a falling market doesn't make every negative call right. Neutral calls
(|sentiment| < 0.2) aren't scored for direction. Sanjay's evening call (signals) is judged on the next
session's plain up/down move, the target it is trained on. Only market data decides a score, never another
model's opinion. Scores go to E:/candlecast-data/memory.db (scores).

Daily closes come from the app DB for the tracked symbols and rupee pairs (config.TICKERS) and from NSE's
bhavcopy in market.db for every other company, once app.download_nse has fetched that day; until then the
call waits. A rupee pair's call is judged on its own calendar (it trades on NSE holidays too), on the
next UTC day after the one the call used.

Usage: started by app/server.py (every hour); or once by hand, printing the track record:
python -m app.chitragupta
"""
import bisect
import json
import threading
import time
from datetime import datetime, timedelta, timezone

from .config import TICKERS, market_of
from .db import connect as connect_app
from .fetch import refresh
from .market_db import connect as connect_market
from .memory_db import connect
from .system import logger, nap

EVERY = 60 * 60    # seconds between scoring rounds
NEUTRAL = 0.2      # a call with |sentiment| below this is neutral: no direction to score
OPEN = (9, 15)     # NSE opens 09:15 IST: news before that reaches the same day's session
FINAL_AT = 16      # hour (IST) after which the day's candle is final
INDEX = "NIFTY 50"
IST = timezone(timedelta(hours=5, minutes=30))

say = logger("chitragupta")  # also appended to <market dir>/logs/chitragupta.log


def final_day(symbol: str, day: str, now: datetime) -> bool:
    """Whether the symbol's daily candle dated `day` (IST date) is final: an NSE one at 16:00 IST that day, a
    rupee pair's (one UTC day, ending 05:30 IST) at 06:00 IST the next morning."""
    if market_of(symbol) == "forex":
        return now >= datetime.fromisoformat(day).replace(tzinfo=IST) + timedelta(days=1, hours=6)
    today = now.date().isoformat()
    return day < today or (day == today and now.hour >= FINAL_AT)


def closes(app) -> dict[str, dict[str, float]]:
    """{symbol: {YYYY-MM-DD: close}} from the daily candles of the tracked symbols and NIFTY 50."""
    out = {}
    for symbol, ts, close in app.execute("SELECT symbol, ts, close FROM candles WHERE interval = '1d'"):
        out.setdefault(symbol, {})[datetime.fromtimestamp(ts / 1000, IST).date().isoformat()] = close
    return out


def nse_move(mkt, symbol: str, session: str) -> float | None:
    """The session's close-to-close change from NSE's bhavcopy (its prev_close is adjusted for splits and bonuses)."""
    row = mkt.execute("SELECT close, prev_close FROM nse_bhav WHERE symbol = ? AND date = ? AND series IN "
                      "('EQ', 'BE', 'BZ', 'SM', 'ST') ORDER BY series = 'EQ' DESC LIMIT 1", (symbol, session)).fetchone()
    return row[0] / row[1] - 1 if row and row[0] and row[1] else None


def session_for(published: str, days: list[str]) -> tuple[str, str] | None:
    """(session, previous session) that news published at this UTC time first reached; None if not traded yet."""
    t = datetime.strptime(published, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(IST)
    day = t.date().isoformat()
    i = bisect.bisect_left(days, day)  # first trading day on or after the news day
    if i < len(days) and days[i] == day and (t.hour, t.minute) >= OPEN:
        i += 1  # out during or after that day's session: the next session is the first to get all of it
    return (days[i], days[i - 1]) if 0 < i < len(days) else None


def score(conn, app, mkt) -> int:
    """Score every call whose session is over and isn't scored yet; returns how many new scores."""
    px = closes(app)
    days = sorted(px.get(INDEX, {}))
    now = datetime.now(IST)
    if days and days[-1] == now.date().isoformat() and now.hour < FINAL_AT:
        days.pop()  # today's candle is still forming
    before = conn.total_changes

    def add(model, ref, symbol, session, said, conf, move, market, outcome, neutral):
        # A neutral call, or a price that didn't move, has no direction to be right or wrong about
        hit = None if said == 0 or abs(said) < neutral or outcome == 0 else int((said > 0) == (outcome > 0))
        conn.execute("INSERT OR IGNORE INTO scores (model, ref, symbol, session, said, confidence, move, market, "
                     "outcome, hit) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (model, ref, symbol, session, said, conf, move, market, outcome, hit))

    # News: Narad's note and Drona's answer, judged on the move beyond the market
    rows = conn.execute(
        "SELECT n.news_id, n.about, n.symbols, n.sentiment, n.confidence, COALESCE(w.published_at, w.fetched_at), "
        "h.answer FROM news_notes n JOIN news w ON w.id = n.news_id "
        "LEFT JOIN help_requests h ON h.asker = 'narad' AND h.ref = 'news:' || n.news_id AND h.status = 'answered'"
    ).fetchall()
    for news_id, about, symbols, sentiment, confidence, published, answer in rows:
        sess = session_for(published, days)
        targets = json.loads(symbols) or ([INDEX] if about == "market" else [])
        if not sess or not targets:
            continue
        session, prev = sess
        market = px[INDEX][session] / px[INDEX][prev] - 1
        calls = [("narad", sentiment, confidence)]
        if answer:
            drona = json.loads(answer)
            calls.append(("drona", drona["sentiment"], drona["confidence"]))
        for symbol in targets:
            c = px.get(symbol, {})
            move = c[session] / c[prev] - 1 if session in c and prev in c else nse_move(mkt, symbol, session)
            if move is None:
                continue  # no price for this symbol and session yet
            for model, said, conf in calls:
                add(model, f"news:{news_id}", symbol, session, said, conf, move, market,
                    move if symbol == INDEX else move - market, NEUTRAL)

    # Sanjay, Chanakya, Trikal: probability of closing up next session, judged on the plain up/down move
    index = px.get(INDEX, {})
    for model, symbol, as_of, prob_up in conn.execute("SELECT model, symbol, as_of, prob_up FROM signals").fetchall():
        c = px.get(symbol, {})
        calendar = days if market_of(symbol) == "stocks" else [d for d in sorted(c) if final_day(symbol, d, now)]
        i = bisect.bisect_right(calendar, as_of)  # the first session after the one the call used
        if i >= len(calendar) or as_of not in c or calendar[i] not in c:
            continue
        session, prev = calendar[i], calendar[i - 1]
        move = c[session] / c[as_of] - 1
        said = round(2 * prob_up - 1, 4)
        market = index[session] / index[prev] - 1 if session in index and prev in index else 0.0
        add(model, f"signal:{as_of}", symbol, session, said, abs(said), move, market, move, 0)
    conn.commit()
    return conn.total_changes - before


def track_record(conn) -> list[tuple]:
    """(model, event, calls, % right, average outcome in the called direction %): per model (event ''), then
    per model and kind of news."""
    stats = ("COUNT(*), ROUND(100.0 * AVG(s.hit), 1), "
             "ROUND(100 * AVG(CASE WHEN s.said > 0 THEN s.outcome ELSE -s.outcome END), 2)")
    return (conn.execute(f"SELECT s.model, '', {stats} FROM scores s WHERE s.hit IS NOT NULL "
                         "GROUP BY s.model ORDER BY s.model").fetchall()
            + conn.execute(f"SELECT s.model, n.event, {stats} FROM scores s JOIN news_notes n "
                           "ON n.news_id = CAST(substr(s.ref, 6) AS INTEGER) WHERE s.ref LIKE 'news:%' AND s.hit IS NOT NULL "
                           "GROUP BY s.model, n.event ORDER BY s.model, COUNT(*) DESC").fetchall())


def view() -> dict:
    """For the website: every model's track record, Narad's by kind of news and by its own confidence, and
    the latest scored calls."""
    conn = connect()
    try:
        record = track_record(conn)
        bands = conn.execute(
            "SELECT CASE WHEN confidence >= 0.9 THEN '0.9 and up' WHEN confidence >= 0.75 THEN '0.75 to 0.9' "
            "WHEN confidence >= 0.6 THEN '0.6 to 0.75' ELSE 'below 0.6' END AS band, COUNT(*), "
            "ROUND(100.0 * AVG(hit), 1) FROM scores WHERE model = 'narad' AND hit IS NOT NULL "
            "GROUP BY band ORDER BY MIN(confidence) DESC").fetchall()
        recent = conn.execute(
            "SELECT s.model, s.symbol, s.session, s.said, s.move, s.outcome, s.hit, w.title FROM scores s "
            "LEFT JOIN news w ON s.ref LIKE 'news:%' AND w.id = CAST(substr(s.ref, 6) AS INTEGER) ORDER BY s.session DESC, s.scored_at DESC LIMIT 500").fetchall()
        return {
            "total": conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0],
            "models": [{"model": m, "calls": n, "right_pct": r, "gain_pct": g} for m, e, n, r, g in record if not e],
            "events": [{"model": m, "event": e, "calls": n, "right_pct": r, "gain_pct": g} for m, e, n, r, g in record if e],
            "calibration": [{"band": b, "calls": n, "right_pct": r} for b, n, r in bands],
            "recent": [{"model": m, "symbol": s, "session": d, "said": said, "move": move, "outcome": o, "hit": h,
                        "title": t} for m, s, d, said, move, o, h, t in recent],
        }
    finally:
        conn.close()


def once() -> int:
    """One scoring round with fresh daily closes; returns how many new scores."""
    app, conn, mkt = connect_app(), connect(), connect_market()
    try:
        for symbol in TICKERS:
            try:
                refresh(app, symbol, "1d", "5d")
            except Exception:
                pass  # Yahoo hiccup: score with what the DB has
        new = score(conn, app, mkt)
        if new:
            say(f"scored {new} new calls — " + "; ".join(
                f"{m}: {right}% right on {n}" for m, event, n, right, _ in track_record(conn) if not event))
        return new
    finally:
        app.close()
        conn.close()
        mkt.close()


def run() -> None:
    while True:
        try:
            once()
        except Exception as e:  # disk unplugged, DB locked…: try again next round
            say(f"error — {type(e).__name__}: {e}")
        nap(EVERY)


def start() -> None:
    threading.Thread(target=run, daemon=True, name="chitragupta").start()


if __name__ == "__main__":
    print(f"{once()} new scores")
    for model, event, n, right, gain in track_record(connect()):
        print(f"{model:<6} {event or 'all calls':<22} {n:>5} calls  {right:>5}% right  {gain:+.2f}% in the called direction")
