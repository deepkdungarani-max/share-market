"""Trikal, the main predictor: one call per tracked symbol and rupee pair for the next session, made from the
other models.

Drona's call comes first (app/drona_call.py): the teacher reads the chart, the world, the news and Sanjay's and
Chanakya's calls with what it has learned, and its probability is Trikal's. Without one (Drona hasn't called the
symbol yet, or its record has fallen behind the plain average, see drona_call.trusted), the call is the plain
average of Sanjay's probability of closing up (the chart) and Chanakya's (the
overnight world). On the walk-forward test of 2022-2026 that average beat both models alone and every
learned combination tried: 53.8% right overall, and 58.9% right (+31 bps a call) on the 32% of calls it
was confident about, because it is only confident when the chart and the world agree. A LightGBM stacker
overfit (52.4%, falling every year); a tightly constrained one reached 53.2%.

The news reaching each session (how many of Narad's notes name the symbol, their average sentiment with
Drona's answer in place of Narad's reading where Narad asked for help, and market-wide news) is recorded
with every call. It moves the call only once it has proven itself: every day news_weight() tries weights
on Trikal's own scored calls that had news and keeps one only if it also lowers the error on the most
recent 30% of them (notes start on 28 Oct 2026, so this needs a few weeks). Re-run the walk-forward
comparison with: python -m app.trikal

The call is made on weekdays from 06:00 IST, once Sanjay's and Chanakya's calls exist, and refreshed every
hour with the latest news until the 09:15 open. It goes to the shared memory (signals, model trikal), where
Chitragupta scores it like every other call.

Usage: started by app/server.py; or by hand, printing the walk-forward comparison: python -m app.trikal
"""
import json
import math
import threading
import time
from datetime import datetime

import numpy as np
import pandas as pd

from . import chanakya, drona_call
from .autolearn import champion, publish
from .chitragupta import INDEX, IST, OPEN, closes, final_day, session_for, track_record
from .config import FOREX, MARKETS, SYMBOLS, TICKERS, market_of
from .db import connect as connect_app
from .memory_db import connect as connect_memory
from .system import logger, nap
from .train import PARAMS, evaluate, load_dataset, out_of_sample

EVERY = 60 * 60  # seconds between checks
NEWS = ["news_n", "news_mean", "market_news"]
FEATURES = ["sanjay", "chanakya", *NEWS, "symbol"]
# The best learned combination tried: small trees, and a stronger signal can only raise the probability
LEARNED = {**PARAMS, "num_leaves": 4, "min_data_in_leaf": 2000, "learning_rate": 0.05,
           "monotone_constraints": [1, 1, 0, 1, 1, 0]}
NEWS_MIN_CALLS = 150  # scored Trikal calls with news needed before news may get any weight
NEWS_WEIGHTS = [0.0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2]  # probability added per unit of average sentiment

say = logger("trikal")  # also appended to <market dir>/logs/trikal.log


def news_weight(mem) -> float:
    """How much the average sentiment of a stock's news moves Trikal's probability; 0 until proven.

    Chosen on Trikal's own scored calls that had news (the older 70%), and kept only if it also lowers the
    log loss on the most recent 30%. The base is always the plain average, whatever weight was used live.
    """
    rows = mem.execute("SELECT g.detail, s.move FROM signals g JOIN scores s ON s.model = 'trikal' "
                       "AND s.ref = 'signal:' || g.as_of AND s.symbol = g.symbol "
                       "WHERE g.model = 'trikal' ORDER BY s.session, s.symbol").fetchall()
    calls = []
    for detail, move in rows:
        d = json.loads(detail or "{}")
        if None not in (d.get("sanjay"), d.get("chanakya"), d.get("news_mean")):
            calls.append(((d["sanjay"] + d["chanakya"]) / 2, d["news_mean"], move > 0))
    if len(calls) < NEWS_MIN_CALLS:
        return 0.0

    def loss(part, w):
        ps = [min(max(base + w * news, 0.01), 0.99) for base, news, _ in part]
        return -sum(math.log(p if up else 1 - p) for p, (_, _, up) in zip(ps, part)) / len(part)

    cut = int(len(calls) * 0.7)
    best = min(NEWS_WEIGHTS, key=lambda w: loss(calls[:cut], w))
    return best if best > 0 and loss(calls[cut:], best) < loss(calls[cut:], 0.0) else 0.0


def news(mem, days: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    """News reaching each session: per (symbol, session) how many notes name a tracked symbol and their
    average sentiment, per session the average of market-wide news, and the first session with any news."""
    rows = mem.execute(
        "SELECT n.about, n.symbols, n.sentiment, COALESCE(w.published_at, w.fetched_at), h.answer "
        "FROM news_notes n JOIN news w ON w.id = n.news_id LEFT JOIN help_requests h ON h.asker = 'narad' "
        "AND h.ref = 'news:' || n.news_id AND h.status = 'answered'").fetchall()
    stock, market, first = [], [], None
    for about, symbols, sentiment, published, answer in rows:
        sess = session_for(published, days)
        if sess is None:
            continue
        session = sess[0]
        first = min(first or session, session)
        said = json.loads(answer)["sentiment"] if answer else sentiment
        stock += [(s, session, said) for s in json.loads(symbols) if s in SYMBOLS]
        if about == "market":
            market.append((session, said))
    per_stock = (pd.DataFrame(stock, columns=["symbol", "session", "said"])
                 .groupby(["symbol", "session"])["said"].agg(news_n="size", news_mean="mean").reset_index())
    per_market = (pd.DataFrame(market, columns=["session", "said"])
                  .groupby("session")["said"].mean().rename("market_news").reset_index())
    return per_stock, per_market, first


def with_news(df: pd.DataFrame, stock: pd.DataFrame, market: pd.DataFrame, first: str | None) -> pd.DataFrame:
    """Rows plus their news. A session after news collection began with no note on the symbol gets news_n 0;
    older sessions stay NaN (unknown)."""
    df = df.merge(stock, on=["symbol", "session"], how="left").merge(market, on="session", how="left")
    df[NEWS] = df[NEWS].astype(float)  # all empty (object) while no session with news is finished
    if first:
        since = df["session"] >= first
        df.loc[since, "news_n"] = df.loc[since, "news_n"].fillna(0)
    df["symbol"] = pd.Categorical(df["symbol"], categories=list(TICKERS))
    return df


def past(mem, now: datetime) -> pd.DataFrame:
    """One row per tracked symbol and finished session: Sanjay's and Chanakya's walk-forward calls (each
    block predicted by a model trained only on earlier days), the news, and whether the symbol closed up."""
    px, days = chanakya.prices(now)
    following = dict(zip(days, days[1:]))  # session -> the next one, which Sanjay's call on it is for
    app = connect_app()
    try:
        chart = load_dataset(app, "1d")
        params = {**PARAMS, **(champion(app, "1d") or {}).get("params", {})}
    finally:
        app.close()
    quiet = lambda *_: None
    s = out_of_sample(chart, params, quiet)
    sanjay = pd.DataFrame({"symbol": s["symbol"].astype(str), "sanjay": s["prob_up"],
                           "session": [following.get(str(d)) for d in s["date"]]}).dropna(subset=["session"])
    calendar = {s: days for s in SYMBOLS}  # the comparison is on the stocks
    world = chanakya.dataset(px, calendar, chanakya.cues(chanakya.all_dates(calendar, now)))
    c = out_of_sample(world, PARAMS, quiet, chanakya.FEATURES)
    df = pd.DataFrame({"symbol": c["symbol"].astype(str), "session": c["date"].dt.strftime("%Y-%m-%d"),
                       "chanakya": c["prob_up"], "label": c["label"], "next_ret": c["next_ret"]})
    df = df.merge(sanjay, on=["symbol", "session"])
    df["date"] = df["session"]  # what out_of_sample splits on
    return with_news(df, *news(mem, days))


def call(mem, now: datetime) -> int:
    """Trikal's call for each symbol's session after its last finished one; returns how many symbols it
    covers. Before the 09:15 open each call replaces the last (fresher news); after it, nothing changes.
    A rupee pair's last finished day is its own (see chanakya.calendars)."""
    chanakya.call(mem, now)  # refreshes the daily candles; Chanakya's call if it isn't made yet
    today = now.date().isoformat()
    app = connect_app()
    try:
        for market in MARKETS:
            publish(app, market)  # Sanjay's call, if it wasn't made already
        px = closes(app)
    finally:
        app.close()
    days = [d for d in sorted(px[INDEX]) if d < today]
    calendar = chanakya.calendars(px, days, now)
    as_of = {s: calendar[s][-1] for s in TICKERS if calendar[s]}  # symbol -> the session its call uses
    before_open = (now.hour, now.minute) < OPEN
    made = {sym for sym, d in mem.execute("SELECT symbol, as_of FROM signals WHERE model = 'trikal'")
            if as_of.get(sym) == d}
    wanted = [s for s in as_of if before_open or s not in made]
    if not wanted:
        return 0
    live = pd.read_sql(f"SELECT model, symbol, as_of, prob_up FROM signals WHERE model IN ('sanjay', 'chanakya') "
                       f"AND symbol IN ({','.join('?' * len(wanted))})", mem, params=wanted)
    live = live[[as_of[sym] == d for sym, d in zip(live["symbol"], live["as_of"])]]
    live = live.pivot(index="symbol", columns="model", values="prob_up").reset_index()
    if not {"sanjay", "chanakya"} <= set(live.columns):
        return 0  # one of them hasn't called yet
    live = live.dropna(subset=["sanjay", "chanakya"]).assign(session=today)
    if live.empty:
        return 0
    rows = with_news(live, *news(mem, days + [today]))
    weight = news_weight(mem)
    drona = {sym: p for sym, d, p in mem.execute("SELECT symbol, as_of, prob_up FROM signals WHERE model = ?",
                                                  (drona_call.MODEL,)) if as_of.get(sym) == d}
    rows["drona"] = rows["symbol"].astype(str).map(drona).astype(float)
    first, _ = drona_call.trusted(mem)
    average = (rows["sanjay"] + rows["chanakya"]) / 2 + weight * rows["news_mean"].fillna(0)
    # Drona's call first: it has already weighed Sanjay, Chanakya and the news with its lessons
    rows["prob_up"] = (rows["drona"] if first else pd.Series(np.nan, index=rows.index)).fillna(average).clip(0.01, 0.99)
    verb = "INSERT OR REPLACE" if before_open else "INSERT OR IGNORE"
    with mem:
        for _, r in rows.iterrows():
            inputs = {k: None if pd.isna(r[k]) else round(float(r[k]), 4) for k in FEATURES if k != "symbol"}
            inputs["news_weight"] = weight
            inputs["drona"] = None if pd.isna(r["drona"]) else round(float(r["drona"]), 4)
            inputs["drona_first"] = bool(first and pd.notna(r["drona"]))
            mem.execute(f"{verb} INTO signals (model, symbol, as_of, prob_up, detail) VALUES ('trikal', ?, ?, ?, ?)",
                        (str(r["symbol"]), as_of[str(r["symbol"])], float(r["prob_up"]), json.dumps(inputs)))
    said = dict(zip(rows["symbol"].astype(str), rows["prob_up"]))
    stocks = {k: v for k, v in said.items() if k in SYMBOLS}
    pairs = ", ".join(f"{k} {v:.0%}" for k, v in said.items() if k in FOREX)
    say(f"call on {len(rows)} symbols"
        + (f" — NIFTY 50 {stocks.get(INDEX, float('nan')):.0%} up; most up {max(stocks, key=stocks.get)} "
           f"{max(stocks.values()):.0%}, most down {min(stocks, key=stocks.get)} {min(stocks.values()):.0%}"
           if stocks else "")
        + (f"; pairs up: {pairs}" if pairs else ""))
    return len(rows)


def once() -> int:
    """Make or refresh today's call when it's due (weekday, 06:00 IST until the close); returns symbols called."""
    now = datetime.now(IST)
    if now.weekday() >= 5 or now.hour < chanakya.FROM_HOUR or (now.hour, now.minute) >= chanakya.CLOSE:
        return 0
    mem = connect_memory()
    try:
        return call(mem, now)
    finally:
        mem.close()


TYPICAL_DAYS = 60  # sessions whose moves set a symbol's typical day's move


def prices_now(app) -> dict[str, dict]:
    """Per symbol: its last closes (final days only, newest last) and its latest 15-minute price, for the
    'now' and 'if up / if down' columns. Only the last ~120 days are read: enough for TYPICAL_DAYS sessions."""
    now = datetime.now(IST)
    since = int((now.timestamp() - 120 * 86400) * 1000)
    daily: dict[str, list[tuple[str, float]]] = {}
    for symbol, ts, close in app.execute("SELECT symbol, ts, close FROM candles WHERE interval = '1d' AND ts >= ? "
                                         "ORDER BY ts", (since,)):
        day = datetime.fromtimestamp(ts / 1000, IST).date().isoformat()
        if final_day(symbol, day, now):
            daily.setdefault(symbol, []).append((day, close))
    latest = dict(app.execute("SELECT c.symbol, c.close FROM candles c JOIN (SELECT symbol, MAX(ts) AS ts FROM candles "
                              "WHERE interval = '15m' GROUP BY symbol) m ON c.symbol = m.symbol AND c.ts = m.ts "
                              "WHERE c.interval = '15m'").fetchall())
    return {s: {"daily": d, "now": latest.get(s)} for s, d in daily.items()}


def levels(call: dict, prices: dict) -> dict:
    """What the call means in price: the close it was made on, the price now, and where a typical day's move
    (the median size of the last TYPICAL_DAYS moves) would take it up or down. The models call the direction
    only, never the size: these are a typical day's reach, not a target."""
    p = prices.get(call["symbol"])
    if not p:
        return {}
    closes_by_day = dict(p["daily"])
    close = closes_by_day.get(call["as_of"])
    series = [c for _, c in p["daily"]]
    moves = sorted(abs(b / a - 1) for a, b in list(zip(series, series[1:]))[-TYPICAL_DAYS:] if a)
    typical = moves[len(moves) // 2] if moves else None
    if close is None or typical is None:
        return {"price": p["now"]}
    return {"last_close": close, "price": p["now"], "typical_move": typical,
            "up_to": close * (1 + typical), "down_to": close * (1 - typical)}


def view() -> dict:
    """For the UI: the latest call on every tracked symbol with its inputs, every model's scorecard,
    Trikal's scored past calls and what Narad and Drona are doing."""
    mem = connect_memory()
    try:
        one = lambda sql, *args: mem.execute(sql, args).fetchone()[0]
        # Each symbol's latest call (a pair's may be dated a day apart from the stocks' after an NSE holiday)
        latest = ("FROM signals s WHERE model = 'trikal' AND as_of = "
                  "(SELECT MAX(as_of) FROM signals WHERE model = 'trikal' AND symbol = s.symbol)")
        calls = [{"symbol": s, "prob_up": p, "as_of": a, "market": market_of(s), **json.loads(d or "{}")}
                 for s, p, a, d in mem.execute(f"SELECT symbol, prob_up, as_of, detail {latest} ORDER BY prob_up DESC")]
        app = connect_app()
        try:
            prices = prices_now(app)
        finally:
            app.close()
        for c in calls:
            c.update(levels(c, prices))
            row = mem.execute("SELECT prob_up, detail, created_at FROM signals WHERE model = ? AND symbol = ? AND as_of = ?",
                              (drona_call.MODEL, c["symbol"], c["as_of"])).fetchone()
            c["drona_call"] = {"prob_up": row[0], "made_at": row[2], **json.loads(row[1] or "{}")} if row else None
        first, why = drona_call.trusted(mem)
        return {
            "as_of": one(f"SELECT MAX(as_of) {latest}"),
            "made_at": one(f"SELECT MAX(created_at) {latest}"),
            "news_weight": news_weight(mem),
            "drona": {"first": first, "why": why},
            "calls": calls,
            "scorecard": [{"model": m, "calls": n, "right_pct": right, "gain_pct": gain}
                          for m, event, n, right, gain in track_record(mem) if not event],
            "past": [{"session": s, "symbol": sym, "market": market_of(sym), "prob_up": (said + 1) / 2, "move": move,
                      "hit": hit}
                     for s, sym, said, move, hit in mem.execute(
                         "SELECT session, symbol, said, move, hit FROM scores WHERE model = 'trikal' "
                         "ORDER BY session DESC, said DESC LIMIT 300")],
            "pipeline": {
                "news_24h": one("SELECT COUNT(*) FROM news WHERE fetched_at >= datetime('now', '-1 day')"),
                "read_24h": one("SELECT COUNT(*) FROM news_notes WHERE created_at >= datetime('now', '-1 day')"),
                "unread": one("SELECT COUNT(*) FROM news WHERE status = 'new' AND priority > 0"),
                "help_pending": one("SELECT COUNT(*) FROM help_requests WHERE status = 'pending'"),
                "help_answered_24h": one("SELECT COUNT(*) FROM help_requests WHERE status = 'answered' "
                                         "AND answered_at >= datetime('now', '-1 day')"),
            },
        }
    finally:
        mem.close()


def report() -> None:
    """Walk-forward on the same unseen days: the average Trikal uses, each model alone, and the best learned
    combination (which can also weigh the news)."""
    mem = connect_memory()
    try:
        df = past(mem, datetime.now(IST))
    finally:
        mem.close()
    print(f"{len(df):,} rows, {df['session'].nunique():,} sessions from {df['session'].min()}")
    oos = out_of_sample(df, LEARNED, print, FEATURES)
    y, move = oos["label"].to_numpy(), oos["next_ret"].to_numpy()
    for name, p in [("Average (Trikal)", (oos["sanjay"] + oos["chanakya"]) / 2), ("Sanjay alone", oos["sanjay"]),
                    ("Chanakya alone", oos["chanakya"]), ("Learned", oos["prob_up"])]:
        m = evaluate(y, p.to_numpy(), move)
        print(f"{name:<17} {m['accuracy']:>5}% right; confident on {m['confident_share']:>5}% of calls: "
              f"{m['confident_accuracy']}% right, {m['confident_avg_move_bps']:+} bps a call")


def run() -> None:
    while True:
        try:
            once()
        except Exception as e:  # Yahoo down, disk unplugged…: try again next hour
            say(f"error — {type(e).__name__}: {e}")
        nap(EVERY)


def start() -> None:
    threading.Thread(target=run, daemon=True, name="trikal").start()


if __name__ == "__main__":
    report()
    print(f"{once()} symbols called (weekdays from 06:00 IST until the close)")
