"""Chanakya, the macro reader: how the world's overnight moves carry into the next Indian session.

Before each session it reads the last closed bars of the US markets (S&P 500, Nasdaq), Brent crude, the
dollar-rupee rate, the US 10-year yield, gold, the dollar index and India VIX, and a LightGBM model trained
on every earlier session turns them into each tracked symbol's and rupee pair's probability of closing up.
The call goes to the shared memory (signals) like Sanjay's, where Chitragupta scores it. Fundamentals
(results, PE, FII/DII flows) aren't read yet.

A rupee pair is called on its own calendar: its day is a UTC day (05:30 to 05:30 IST), final at 06:00 IST,
and it trades on NSE holidays. Its call is made with the stocks' each weekday morning, for the pair's day
that has just begun; the overnight bars it reads all closed before that day started.

Only bars dated before the session count: the US session dated D-1 closes at 01:30-02:30 IST on D, the
rupee's day at 05:30 IST, and India VIX dated D-1 is the previous session. The model is retrained for every
call, only on sessions before the one it calls.

Usage: started by app/server.py (checks every hour; one call per weekday, from 06:00 IST until the close);
or by hand, printing a walk-forward test first: python -m app.chanakya
"""
import json
import threading
import time
from datetime import datetime

import lightgbm as lgb
import pandas as pd

from .chitragupta import INDEX, IST, closes, final_day
from .config import FOREX, SYMBOLS, TICKERS, market_of
from .db import connect as connect_app
from .fetch import download, refresh
from .memory_db import connect as connect_memory
from .system import logger, nap
from .train import PARAMS, ROUNDS, walk_forward

EVERY = 60 * 60      # seconds between checks
FROM_HOUR = 6        # IST: every overnight bar is final by then (US close 01:30-02:30, rupee day ends 05:30)
CLOSE = (15, 30)     # no call once the session it is for has closed
# Yahoo ticker of every series read, by feature name
GLOBAL = {"sp500": "^GSPC", "nasdaq": "^IXIC", "brent": "BZ=F", "usdinr": "INR=X", "us10y": "^TNX",
          "gold": "GC=F", "dollar": "DX-Y.NYB", "indiavix": "^INDIAVIX"}
FEATURES = [f"{name}_ret" for name in GLOBAL] + ["indiavix_level", "symbol"]

say = logger("chanakya")  # also appended to <market dir>/logs/chanakya.log


def cues(sessions: list[str]) -> pd.DataFrame:
    """One row per session date: each series' last change dated before it (NaN when older than a week)."""
    out = pd.DataFrame({"date": pd.to_datetime(sessions)}).sort_values("date")
    for name, ticker in GLOBAL.items():
        close = download(ticker, "1d", "max")["close"]
        g = pd.DataFrame({"date": pd.to_datetime(close.index.strftime("%Y-%m-%d")),
                          f"{name}_ret": close.pct_change().to_numpy()})
        if name == "indiavix":
            g["indiavix_level"] = close.to_numpy()
        out = pd.merge_asof(out, g.sort_values("date"), on="date", direction="backward",
                            allow_exact_matches=False, tolerance=pd.Timedelta(days=7))
    return out


def calendars(px: dict, days: list[str], now: datetime) -> dict[str, list[str]]:
    """Each symbol's finished sessions: NSE's for the stocks, its own final days for a rupee pair."""
    return {s: days if s in SYMBOLS else [d for d in sorted(px.get(s, {})) if final_day(s, d, now)]
            for s in TICKERS}


def dataset(px: dict, calendar: dict[str, list[str]], cue: pd.DataFrame) -> pd.DataFrame:
    """A row per symbol per session of its calendar: the cues before it and whether the symbol closed up."""
    rows = [(s, day, px[s][day] / px[s][prev] - 1)
            for s, days in calendar.items() for prev, day in zip(days, days[1:])
            if prev in px.get(s, {}) and day in px[s]]
    df = pd.DataFrame(rows, columns=["symbol", "date", "next_ret"])
    df = df[df["next_ret"] != 0]  # an unchanged close has no direction (see features.build)
    df["date"] = pd.to_datetime(df["date"])
    df["label"] = (df["next_ret"] > 0).astype(int)
    df["symbol"] = pd.Categorical(df["symbol"], categories=list(TICKERS))
    return df.merge(cue, on="date", how="left").dropna(subset=["sp500_ret"])


def all_dates(calendar: dict[str, list[str]], now: datetime) -> list[str]:
    """Every session date of every calendar, plus today: the dates cues() must cover."""
    return sorted({d for days in calendar.values() for d in days} | {now.date().isoformat()})


def prices(now: datetime) -> tuple[dict, list[str]]:
    """(freshly refreshed daily closes of the tracked symbols and pairs, finished NSE sessions before today)."""
    app = connect_app()
    try:
        for symbol in TICKERS:
            try:
                refresh(app, symbol, "1d", "5d")
            except Exception:
                pass  # Yahoo hiccup: work with what the DB has
        px = closes(app)
    finally:
        app.close()
    today = now.date().isoformat()
    return px, [d for d in sorted(px[INDEX]) if d < today]


def once() -> int:
    """Make today's call if it's due (weekday, 06:00 IST until the close, not made yet); returns calls saved."""
    now = datetime.now(IST)
    if now.weekday() >= 5 or now.hour < FROM_HOUR or (now.hour, now.minute) >= CLOSE:
        return 0
    mem = connect_memory()
    try:
        return call(mem, now)
    finally:
        mem.close()


def call(mem, now: datetime) -> int:
    """The call for each symbol's session after its last finished one, unless it's already made; returns
    calls saved. Stocks and rupee pairs are checked apart: after an NSE holiday the stocks' call is made
    already while the pairs, which traded that day, need a new one."""
    px, days = prices(now)
    calendar = calendars(px, days, now)
    due = {}  # symbol -> the session its call uses (the call is for the one after)
    for group in (SYMBOLS, FOREX):
        as_of = {s: calendar[s][-1] for s in group if calendar[s] and calendar[s][-1] in px.get(s, {})}
        if as_of and not mem.execute(
                f"SELECT 1 FROM signals WHERE model = 'chanakya' AND symbol IN ({','.join('?' * len(as_of))}) "
                "AND as_of = ?", (*as_of, max(as_of.values()))).fetchone():
            due.update(as_of)
    if not due:
        return 0
    cue = cues(all_dates(calendar, now))
    rows = dataset(px, calendar, cue)
    today = cue[cue["date"] == pd.Timestamp(now.date())].iloc[0]
    cues_read = {k: round(float(today[k]), 5) for k in FEATURES if k != "symbol" and today[k] == today[k]}
    probs, details = {}, {}
    # One model per market, trained on that market's rows only: stocks keep exactly the model they tested with
    # (53.5% on 2017-2026), and the pairs, which react to the overnight world in their own way, get theirs
    for group in (SYMBOLS, FOREX):
        symbols = [s for s in due if s in group]
        if not symbols:
            continue
        train = rows[rows["symbol"].isin(list(group))]
        model = lgb.train(PARAMS, lgb.Dataset(train[FEATURES], train["label"]), ROUNDS)
        x = pd.DataFrame({name: [today[name]] * len(symbols) for name in FEATURES if name != "symbol"})
        x["symbol"] = pd.Categorical(symbols, categories=list(TICKERS))
        probs.update(zip(symbols, model.predict(x[FEATURES])))
        details.update({s: json.dumps({"trained_on": len(train), "cues": cues_read}) for s in symbols})
    with mem:
        for symbol, prob_up in probs.items():
            mem.execute("INSERT OR IGNORE INTO signals (model, symbol, as_of, prob_up, detail) "
                        "VALUES ('chanakya', ?, ?, ?, ?)", (symbol, due[symbol], float(prob_up), details[symbol]))
    symbols = list(probs)
    pairs = ", ".join(f"{s} {probs[s]:.0%}" for s in FOREX if s in probs)
    say(f"call saved for {len(symbols)} symbols after {max(due.values())}"
        + (f" — NIFTY 50 {probs[INDEX]:.0%} up" if INDEX in probs else "") + (f"; pairs up: {pairs}" if pairs else ""))
    return len(symbols)


def report() -> None:
    """Walk-forward test on every past session: does the overnight world predict the Indian close?"""
    now = datetime.now(IST)
    px, days = prices(now)
    calendar = calendars(px, days, now)
    df = dataset(px, calendar, cues(all_dates(calendar, now)))
    print(f"{len(df):,} rows, {df['date'].nunique():,} sessions from {df['date'].min():%Y-%m-%d}")
    for name, group in (("stocks", SYMBOLS), ("forex", FOREX)):  # one model per market, as call() trains them
        part = df[df["symbol"].isin(list(group))]
        print(f"Out-of-sample, {name}:", json.dumps(walk_forward(part, PARAMS, features=FEATURES)))


def view() -> dict:
    """For the website: Chanakya's latest call on every tracked symbol and the overnight moves it read."""
    mem = connect_memory()
    try:
        # Each symbol's latest call (a pair's may be dated a day apart from the stocks' after an NSE holiday)
        rows = mem.execute("SELECT symbol, prob_up, detail, created_at, as_of FROM signals s WHERE model = 'chanakya' "
                           "AND as_of = (SELECT MAX(as_of) FROM signals WHERE model = 'chanakya' AND symbol = s.symbol) "
                           "ORDER BY prob_up DESC").fetchall()
        as_of = max((r[4] for r in rows), default=None)
        detail = json.loads(rows[0][2] or "{}") if rows else {}
        return {"as_of": as_of, "made_at": max((r[3] for r in rows), default=None), "cues": detail.get("cues", {}),
                "trained_on": detail.get("trained_on"), "tickers": GLOBAL,
                "calls": [{"symbol": s, "prob_up": p, "market": market_of(s)} for s, p, _, _, _ in rows]}
    finally:
        mem.close()


def run() -> None:
    while True:
        try:
            once()
        except Exception as e:  # Yahoo down, disk unplugged…: try again next hour
            say(f"error — {type(e).__name__}: {e}")
        nap(EVERY)


def start() -> None:
    threading.Thread(target=run, daemon=True, name="chanakya").start()


if __name__ == "__main__":
    report()
    print(f"{once()} calls saved (only on weekdays from 06:00 IST until the close)")
