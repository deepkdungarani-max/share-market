"""Keeps the models learning for as long as the server runs.

Every cycle, for each interval and market (NSE stocks, rupee pairs): download the newest candles, then
score two LightGBM settings walk-forward on the same data — the current best and one random variation of
it. The winner is trained on everything and becomes that market's active model, so the settings drift
towards what works and every model has seen the latest market. Nothing is retrained when no new candle
arrived. Stocks and pairs get separate models: a rupee rate moves nothing like a share.

After the daily model's turn, Sanjay's call for the next session of every symbol of that market goes to
the shared memory (signals), where Chitragupta scores it.

Usage: started by app/server.py; or once by hand: python -m app.autolearn
"""
import json
import random
import threading
import time
from datetime import datetime

import lightgbm as lgb
import pandas as pd

from .chitragupta import IST, final_day
from .config import INTERVALS, MARKETS, ROOT
from .db import connect
from .features import FEATURES, build
from .fetch import catch_up
from .memory_db import connect as connect_memory
from .system import nap
from .train import PARAMS, load_dataset, save, walk_forward

EVERY = 60 * 60   # seconds between learning cycles
FIRST_DELAY = 60  # let the server start and the UI load before the first cycle
WARMUP = 300      # daily candles fed to the indicators for Sanjay's call (EMA/RSI need warm-up)
# Range each tunable LightGBM setting may wander in (ints stay ints)
SEARCH = {
    "learning_rate": (0.005, 0.1),
    "num_leaves": (7, 63),
    "min_data_in_leaf": (50, 1000),
    "feature_fraction": (0.4, 1.0),
    "lambda_l2": (0.0, 30.0),
}


def say(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] autolearn: {msg}", flush=True)


def champion(conn, interval: str, market: str = "stocks") -> dict | None:
    """Metrics of the model the server uses now for this market and interval."""
    row = conn.execute(
        "SELECT metrics FROM models WHERE interval = ? AND market = ? ORDER BY active DESC, id DESC LIMIT 1",
        (interval, market)).fetchone()
    return json.loads(row[0] or "{}") if row else None


def mutate(params: dict) -> dict:
    """The same settings with one of them nudged up or down."""
    key = random.choice(list(SEARCH))
    lo, hi = SEARCH[key]
    value = min(max(params[key] * random.uniform(0.6, 1.6), lo), hi)
    return {**params, key: int(round(value)) if isinstance(lo, int) else round(value, 4)}


def learn(conn, interval: str, market: str) -> None:
    for symbol in MARKETS[market]:
        try:
            catch_up(conn, symbol, interval)  # every candle since the last one in the DB, however long the gap
        except Exception:
            pass  # Yahoo hiccup: learn from what the DB has

    df = load_dataset(conn, interval, market)
    if df.empty:
        return
    data_until = int(df["ts"].max())
    best = champion(conn, interval, market) or {}
    if best.get("data_until") == data_until:
        return  # no new candle since the active model was trained

    base = {**PARAMS, **best.get("params", {})}
    trials = [base, mutate(base)]
    scored = [(walk_forward(df, p, log=lambda *_: None), p) for p in trials]
    metrics, params = max(scored, key=lambda s: s[0]["accuracy"])
    model_id = save(conn, df, interval, params, {**metrics, "data_until": data_until}, market)
    conn.execute("UPDATE models SET active = (id = ?) WHERE interval = ? AND market = ?", (model_id, interval, market))
    conn.commit()
    tried = ", ".join(f"{m['accuracy']}%" for m, _ in scored)
    say(f"{market} {interval}: new model #{model_id} active — tried {tried}, kept {metrics['accuracy']}% "
        f"(was {best.get('accuracy', '–')}%)")


def publish(conn, market: str = "stocks") -> int:
    """Sanjay's call for the next session of every symbol of this market, from its active daily model;
    returns how many were new. Made on the latest final daily candle (an NSE one after 16:00 IST, a rupee
    pair's at 06:00 IST the next morning): the models never train on a forming candle, so it can't have
    leaked into them."""
    row = conn.execute("SELECT id, name, path FROM models WHERE interval = '1d' AND market = ? "
                       "ORDER BY active DESC, id DESC LIMIT 1", (market,)).fetchone()
    if row is None:
        return 0
    model_id, name, path = row
    booster = lgb.Booster(model_file=str(ROOT / path))
    now = datetime.now(IST)
    mem = connect_memory()
    try:
        before = mem.total_changes
        for symbol in MARKETS[market]:
            hist = pd.read_sql("SELECT ts, open, high, low, close, volume FROM candles WHERE symbol = ? AND "
                               "interval = '1d' ORDER BY ts DESC LIMIT ?", conn, params=(symbol, WARMUP + 2))
            if hist.empty:
                continue
            hist = hist.iloc[::-1].reset_index(drop=True)
            days = [datetime.fromtimestamp(int(ts) / 1000, IST).date().isoformat() for ts in hist["ts"]]
            while days and not final_day(symbol, days[-1], now):
                hist, days = hist.iloc[:-1], days[:-1]  # the forming candle: call on the last final one
            if hist.empty:
                continue
            as_of = days[-1]
            prob_up = float(booster.predict(build(hist, "1d").iloc[[-1]][FEATURES])[0])
            mem.execute("INSERT OR IGNORE INTO signals (model, symbol, as_of, prob_up, detail) "
                        "VALUES ('sanjay', ?, ?, ?, ?)",
                        (symbol, as_of, prob_up, json.dumps({"model_id": model_id, "name": name})))
        mem.commit()
        return mem.total_changes - before
    finally:
        mem.close()


def view(market: str = "stocks") -> dict:
    """For the website: Sanjay's latest call on every symbol of a market, and how its daily model tested."""
    symbols = list(MARKETS[market])
    marks = ",".join("?" * len(symbols))
    mem = connect_memory()
    try:
        as_of = mem.execute(f"SELECT MAX(as_of) FROM signals WHERE model = 'sanjay' AND symbol IN ({marks})",
                            symbols).fetchone()[0]
        rows = mem.execute(f"SELECT symbol, prob_up, created_at FROM signals WHERE model = 'sanjay' AND as_of = ? "
                           f"AND symbol IN ({marks}) ORDER BY prob_up DESC", (as_of, *symbols)).fetchall()
    finally:
        mem.close()
    conn = connect()
    try:
        tested = champion(conn, "1d", market) or {}
    finally:
        conn.close()
    return {"market": market, "as_of": as_of, "made_at": max((r[2] for r in rows), default=None),
            "calls": [{"symbol": s, "prob_up": p} for s, p, _ in rows],
            "accuracy": tested.get("accuracy"), "confident_accuracy": tested.get("confident_accuracy"),
            "confident_share": tested.get("confident_share")}


def cycle() -> None:
    for interval in INTERVALS:
        for market in MARKETS:
            conn = connect()
            try:
                learn(conn, interval, market)
                if interval == "1d" and (made := publish(conn, market)):
                    say(f"{market} 1d: Sanjay's call for the next session saved for {made} symbols")
            except Exception as e:  # one interval or market failing must not stop the others
                say(f"{market} {interval}: failed — {type(e).__name__}: {e}")
            finally:
                conn.close()


def run() -> None:
    time.sleep(FIRST_DELAY)
    while True:
        cycle()
        nap(EVERY)


def start() -> None:
    threading.Thread(target=run, daemon=True, name="autolearn").start()
    say(f"started — learns every {EVERY // 60} min while the server runs")


if __name__ == "__main__":
    cycle()
