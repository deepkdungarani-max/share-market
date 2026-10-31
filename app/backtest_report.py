"""The report written after every backtest run, for the Backtest page.

It compares the run with the finished run before it. Then it looks for why the calls failed and why they worked:
- by what the market did the next day;
- by what the stock itself did on the day of the call;
- month by month;
- on the worst and best days;
- in the worst confident misses.

Then it explains why the run didn't do better: how much of a stock's day is the market's, how sure the model was,
which stocks could really be traded, and what trading costs. It ends with what to try next.

Every number comes from backtest.db, and every sentence is built from those numbers.

Usage: python -m app.backtest_report RUN   (writes that run's report again)
"""
import json
import sqlite3
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from .backtest import JUMP_DOWN, JUMP_UP, LIQUID, connect

BUSY_DAY = 300  # a session needs this many scored calls to rank among the best and worst days
SURE = 0.6      # a miss counts as confident when it said up at 60%+ or down at 40% or less
BIG_GROUP = 5000  # a condition needs this many calls before the report draws a lesson from it
MARKET_MOVES = [("fell more than 1%", -np.inf, -0.01), ("fell 0.3–1%", -0.01, -0.003),
                ("moved less than 0.3%", -0.003, 0.003), ("rose 0.3–1%", 0.003, 0.01),
                ("rose more than 1%", 0.01, np.inf)]
OWN_MOVES = [("Fell 5% or more that day", -np.inf, -0.05), ("Fell 2–5% that day", -0.05, -0.02),
             ("Moved less than 2% that day", -0.02, 0.02), ("Rose 2–5% that day", 0.02, 0.05),
             ("Rose 5% or more that day", 0.05, np.inf)]
INPUTS = {"mkt_ret": "the market's move that day", "breadth": "the share of stocks up that day",
          "ret_1": "the stock's own move that day", "rel_1": "its move against the market", "dow": "the weekday",
          "rsi_14": "RSI", "liquidity": "its turnover rank", "vol_ratio": "volume against usual",
          "upper_wick": "the candle's upper wick", "range": "the day's high-low range"}
# What the two runs' metrics are compared on: label, path in the metrics, unit
COMPARE = [("Right", ("right_pct",), "%"), ("Always one way", ("always_pct",), "%"), ("AUC", ("auc",), ""),
           ("Right on ₹5 cr+ stocks", ("liquid", "right_pct"), "%"), ("AUC on ₹5 cr+ stocks", ("liquid", "auc"), ""),
           ("Top picks, a day", ("picks", "top_avg_pct"), "%"),
           ("Top picks' year after costs", ("picks", "top_year_after_cost_pct"), "%"),
           ("Bottom picks, a day", ("picks", "bottom_avg_pct"), "%"), ("Companies", ("companies",), ""),
           ("Scored calls", ("calls",), ""), ("Training rows", ("train_rows",), ""), ("Rounds", ("rounds",), "")]


def _pct(x) -> float | None:
    x = np.asarray(x, dtype=float)
    return round(100 * float(x.mean()), 1) if x.size else None


def _move(x) -> float | None:
    """The average of a set of moves, in % with 2 decimals."""
    x = np.asarray(x, dtype=float)
    return round(100 * float(np.nanmean(x)), 2) if x.size else None


def _group(s: pd.DataFrame, label: str, **extra) -> dict:
    return {"label": label, "calls": len(s), "right_pct": _pct(s["right"]), "said_up_pct": _pct(s["said_up"]),
            "went_up_pct": _pct(s["went_up"]), **extra}


def _dig(m: dict | None, path: tuple) -> float | None:
    for key in path:
        m = m.get(key) if isinstance(m, dict) else None
    return m


def _calls(db: sqlite3.Connection, run_id: int) -> pd.DataFrame:
    df = pd.read_sql("SELECT p.date, p.symbol, c.name, p.prob_up, p.next_ret, p.avg_value, p.locked, p.day_ret "
                     "FROM predictions p LEFT JOIN companies c ON c.run = p.run AND c.symbol = p.symbol "
                     "WHERE p.run = ?", db, params=(run_id,))
    df["said_up"], df["went_up"] = df["prob_up"] >= 0.5, df["next_ret"] > 0
    df["market"] = df.groupby("date")["next_ret"].transform("median")  # what the typical stock did the next day
    s = df[df["next_ret"] != 0].copy()  # the scored calls: an unchanged close is neither right nor wrong
    s["right"] = s["said_up"] == s["went_up"]
    return s


def _day_reason(d: pd.Series, good: bool) -> str:
    said, went = 100 * d["said_up"], 100 * d["went_up"]
    if good:
        return (f"It called {said:.0f}% of stocks up and {went:.0f}% rose: its read of the market was right, "
                f"and the typical stock moved {100 * d['market']:+.2f}%.")
    if went - said >= 20:
        return f"The market turned up: {went:.0f}% of stocks rose, but it called only {said:.0f}% up."
    if said - went >= 20:
        return f"It expected a rise ({said:.0f}% up calls), but {100 - went:.0f}% of stocks fell."
    return f"A split day ({went:.0f}% of stocks rose): its calls didn't match which ones."


def _miss(r: pd.Series) -> dict:
    return {"date": r["date"], "symbol": r["symbol"], "name": r["name"], "prob_up": round(float(r["prob_up"]), 3),
            "next_ret": round(float(r["next_ret"]), 4),
            "day_ret": None if pd.isna(r["day_ret"]) else round(float(r["day_ret"]), 4),
            "locked": None if pd.isna(r["locked"]) else int(r["locked"])}


def _compare(db: sqlite3.Connection, run_id: int, cutoff: str, m: dict) -> dict | None:
    """Against the latest finished run before this one: the same numbers side by side, and what changed."""
    row = db.execute("SELECT id, cutoff, metrics FROM runs WHERE status = 'done' AND id < ? AND metrics IS NOT NULL "
                     "ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
    if not row:
        return None
    prev_id, prev_cutoff, prev = row[0], row[1], json.loads(row[2])
    rows = [{"label": label, "now": _dig(m, path), "before": _dig(prev, path), "unit": unit}
            for label, path, unit in COMPARE]
    notes = []
    if prev_cutoff != cutoff:
        notes.append(f"Run #{prev_id} was tested on the year from {prev_cutoff}, this one on the year from {cutoff}: "
                     f"part of any difference is the market of a different year.")
    now_auc, old_auc = m.get("auc"), prev.get("auc")
    if now_auc is not None and old_auc is not None:
        change = now_auc - old_auc
        word = "better" if change > 0.002 else "worse" if change < -0.002 else "about the same"
        notes.append(f"Ranking skill (AUC) went from {old_auc:.3f} to {now_auc:.3f}: {word}.")
    now_l, old_l = _dig(m, ("liquid", "auc")), _dig(prev, ("liquid", "auc"))
    if now_l is not None and old_l is not None:
        notes.append(f"On stocks trading ₹5 crore+ a day, AUC went from {old_l:.3f} to {now_l:.3f}.")
    now_p, old_p = _dig(m, ("picks", "top_year_after_cost_pct")), _dig(prev, ("picks", "top_year_after_cost_pct"))
    if now_p is not None and old_p is not None:
        notes.append(f"Buying its top picks daily for the year, after costs: {old_p:+.1f}% then, {now_p:+.1f}% now.")
    if set(m.get("features", {})) != set(prev.get("features", {})):
        added = sorted(set(m.get("features", {})) - set(prev.get("features", {})))
        dropped = sorted(set(prev.get("features", {})) - set(m.get("features", {})))
        notes.append(f"Inputs changed: {', '.join(added) or 'none'} added, {', '.join(dropped) or 'none'} dropped.")
    if bool(m.get("excluded")) != bool(prev.get("excluded")) or m.get("companies") != prev.get("companies"):
        notes.append(f"Companies scored: {prev.get('companies'):,} then, {m.get('companies'):,} now.")
    return {"run": prev_id, "cutoff": prev_cutoff, "rows": rows, "notes": notes}


def build(db: sqlite3.Connection, run_id: int) -> dict:
    """The report for one finished run (its calls must be saved and its metrics stored)."""
    cutoff, metrics = db.execute("SELECT cutoff, metrics FROM runs WHERE id = ?", (run_id,)).fetchone()
    m = json.loads(metrics)
    s = _calls(db, run_id)
    s["month"] = s["date"].str[:7]

    market_moves = []
    for name, lo, hi in MARKET_MOVES:
        g = s[(s["market"] >= lo) & (s["market"] < hi)]
        market_moves.append(_group(g, f"The typical stock {name} the next day", sessions=int(g["date"].nunique())))
    own_moves = []
    for name, lo, hi in OWN_MOVES:
        g = s[(s["day_ret"] >= lo) & (s["day_ret"] < hi)]
        own_moves.append(_group(g, name, next_move_pct=_move(g["next_ret"])))
    for name, flag in (("Locked at its upper price band", 1), ("Locked at its lower price band", -1)):
        g = s[s["locked"] == flag]
        own_moves.append(_group(g, name, next_move_pct=_move(g["next_ret"])))
    days = s.groupby("date").agg(calls=("right", "size"), right=("right", "mean"), said_up=("said_up", "mean"),
                                 went_up=("went_up", "mean"), market=("market", "first"))
    days["read_market"] = (days["said_up"] > 0.5) == (days["went_up"] > 0.5)  # its call for the market as a whole
    read = days.groupby(days.index.str[:7])["read_market"].mean()
    months = [_group(g, month, market_call_pct=round(100 * float(read[month]), 1)) for month, g in s.groupby("month")]
    busy = days[days["calls"] >= BUSY_DAY]
    day_row = lambda date, d, good: {"date": date, "calls": int(d["calls"]), "right_pct": round(100 * d["right"], 1),
                                     "said_up_pct": round(100 * d["said_up"], 1),
                                     "went_up_pct": round(100 * d["went_up"], 1),
                                     "market_pct": round(100 * d["market"], 2), "why": _day_reason(d, good)}
    worst = [day_row(date, d, False) for date, d in busy.nsmallest(5, "right").iterrows()]
    best = [day_row(date, d, True) for date, d in busy.nlargest(5, "right").iterrows()]

    # Splits and bonuses the bhavcopy left unadjusted look like crashes: not real moves, so never real misses
    jump = (s["next_ret"] <= JUMP_DOWN) | (s["next_ret"] >= JUMP_UP)
    liquid = s[(s["avg_value"] >= LIQUID) & ~jump]
    misses = {"said_up": [_miss(r) for _, r in liquid[(liquid["prob_up"] >= SURE) & ~liquid["went_up"]]
                          .nsmallest(8, "next_ret").iterrows()],
              "said_down": [_miss(r) for _, r in liquid[(liquid["prob_up"] <= 1 - SURE) & liquid["went_up"]]
                            .nlargest(8, "next_ret").iterrows()]}
    example = s[jump].sort_values("next_ret").head(1)
    checks = {"jumps": int(jump.sum()), "jump_example": _miss(example.iloc[0]) if len(example) else None,
              "locked_up": int((s["locked"] == 1).sum()), "locked_down": int((s["locked"] == -1).sum()),
              "excluded": m.get("excluded")}

    # How much was there to win: the market's share of a stock's day, and how sure the model itself was
    majority = s.groupby("date")["went_up"].transform("mean") > 0.5
    own_call = s.groupby("date")["said_up"].transform("mean") > 0.5
    ceiling = {"got_pct": m["right_pct"], "always_pct": m["always_pct"],
               "expected_pct": round(100 * float(np.maximum(s["prob_up"], 1 - s["prob_up"]).mean()), 1),
               "middle_pct": _pct((s["prob_up"] >= 0.4) & (s["prob_up"] < 0.6)),
               "market_only_pct": _pct(s["went_up"] == majority), "market_call_pct": _pct(days["read_market"]),
               "follow_pct": _pct(s["said_up"] == own_call), "daily_auc": m.get("daily_auc")}

    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "compare": _compare(db, run_id, cutoff, m), "market_moves": market_moves, "own_moves": own_moves,
              "months": months, "worst_days": worst, "best_days": best, "misses": misses, "ceiling": ceiling,
              "checks": checks}
    report.update(_story(m, report))
    return report


def _story(m: dict, r: dict) -> dict:
    """The report's sentences: the headline, why calls failed, why they worked, why it didn't do better, next."""
    usual = "down" if m["train_up_pct"] < 50 else "up"
    beat = m["right_pct"] - m["always_pct"]
    c = r["ceiling"]
    headline = (f"Right on {m['right_pct']}% of {m['calls']:,} calls, against {m['always_pct']}% for always calling "
                f"{usual}: {beat:+.1f} points. AUC {m['auc']:.3f} (0.500 is a coin toss).")

    failed, worked, limits, nxt = [], [], [], []
    regimes = [g for g in r["market_moves"] if g["calls"] >= BIG_GROUP]
    if regimes:
        worst = min(regimes, key=lambda g: g["right_pct"])
        best = max(regimes, key=lambda g: g["right_pct"])
        failed.append(f"It failed most when {worst['label'][0].lower()}{worst['label'][1:]}: right "
                      f"{worst['right_pct']}% over {worst['sessions']} sessions. It called {worst['said_up_pct']}% of "
                      f"stocks up while {worst['went_up_pct']}% rose, so it missed the market's turn.")
        worked.append(f"It did best when {best['label'][0].lower()}{best['label'][1:]}: right {best['right_pct']}% "
                      f"over {best['sessions']} sessions, calling {100 - best['said_up_pct']:.1f}% of stocks down "
                      f"while {100 - best['went_up_pct']:.1f}% fell.")
    bad_months = sorted((g for g in r["months"] if g["calls"] >= BIG_GROUP), key=lambda g: g["right_pct"])[:2]
    for g in bad_months:
        gap = g["went_up_pct"] - g["said_up_pct"]
        why = (f"stocks rose {g['went_up_pct']}% of the time but it called up only {g['said_up_pct']}%, so it kept "
               f"expecting falls in a rising market" if gap > 10 else
               f"it called up {g['said_up_pct']}% while {g['went_up_pct']}% rose, so it expected a bounce that didn't "
               f"come" if gap < -10 else
               f"over the month its up calls ({g['said_up_pct']}%) matched the stocks that rose ({g['went_up_pct']}%), "
               f"but it read the market's direction right on only {g['market_call_pct']}% of its sessions, so its up "
               f"calls landed on falling days and its down calls on rising ones")
        failed.append(f"{datetime.strptime(g['label'], '%Y-%m'):%B %Y} was among its worst months (right "
                      f"{g['right_pct']}%): {why}.")
    if r["worst_days"]:
        d = r["worst_days"][0]
        failed.append(f"Its worst day was {d['date']} (right {d['right_pct']}%). {d['why']}")
        one_way = sum(d["said_up_pct"] >= 85 or d["said_up_pct"] <= 15 for d in r["worst_days"])
        top = [INPUTS.get(f, f) for f in list(m.get("features", {}))[:2]]
        if one_way >= 3 and top:
            n = len(r["worst_days"])
            failed.append(f"On {f'all {n}' if one_way == n else f'{one_way} of its {n}'} worst days it called nearly "
                          f"every stock the same way and the market went the other. Its strongest inputs are "
                          f"{' and '.join(top)}, so it "
                          f"bets on the whole market from today, and one wrong read sinks almost every call that day.")

    conds = [g for g in r["own_moves"][:len(OWN_MOVES)] if g["calls"] >= BIG_GROUP]
    if conds:
        g = max(conds, key=lambda g: g["right_pct"])
        said_up, rose_that_day = g["said_up_pct"] > 50, " rose" in f" {g['label'].lower()}"
        lesson = ("that it often bounces back the next day" if said_up and not rose_that_day else
                  "that it often keeps falling" if not said_up and not rose_that_day else
                  "that it often keeps rising" if said_up else "that such a jump is often given back the next day")
        if g["label"].startswith("Moved less"):
            lesson = "that such a quiet stock mostly follows the market the next day"
        worked.append(f"Its surest ground was a stock that {g['label'][0].lower()}{g['label'][1:]}: right "
                      f"{g['right_pct']}% on {g['calls']:,} calls (it said up {g['said_up_pct']}%, {g['went_up_pct']}% "
                      f"rose). It learned {lesson}.")
    locked_up = next((g for g in r["own_moves"] if g["label"].startswith("Locked at its upper")), None)
    if locked_up and locked_up["calls"]:
        worked.append(f"Stocks locked at their upper band: right {locked_up['right_pct']}% (they rose "
                      f"{locked_up['went_up_pct']}% of the time, {locked_up['next_move_pct']:+.2f}% on average). Real, "
                      f"but nobody sells a locked stock at the close, so it can't be bought there.")
    turnover = m.get("by_turnover") or []
    if turnover and turnover[0].get("up_pct") is not None:
        thin, big = turnover[0], turnover[-1]
        fixed = lambda t: max(t["up_pct"], 100 - t["up_pct"])
        worked.append(f"Thinly traded stocks ({thin['label'].lower()}): right {thin['right_pct']}% against "
                      f"{fixed(thin):.1f}% for one fixed call. Their prices catch up slowly, so yesterday's move says "
                      f"more about tomorrow.")
        limits.append(f"The edge fades as stocks get busier: {thin['right_pct']}% right under ₹1 crore a day, but "
                      f"{big['right_pct']}% over ₹50 crore, where one fixed call gets {fixed(big):.1f}%. Busy stocks' "
                      f"prices already carry what these chart inputs know.")
    bands = m.get("bands") or []
    if len(bands) >= 2 and bands[-1]["up_pct"] is not None and bands[0]["up_pct"] is not None:
        worked.append(f"Its odds mean something: when it said 60%+ up, {bands[-1]['up_pct']}% rose; under 40%, only "
                      f"{bands[0]['up_pct']}%.")

    limits.insert(0, f"Most of its score is the year itself: stocks fell on {100 - m['up_pct']:.1f}% of company-days "
                     f"and it said down on {100 - m['said_up_pct']:.1f}% of its calls. Calling down every time "
                     f"scores {m['always_pct']}%; its own edge over that is {beat:+.1f} points.")
    limits.append(f"A stock's next day is mostly the market's: calling every stock in the market's actual direction "
                  f"would be right {c['market_only_pct']}%. It read the market's direction right on "
                  f"{c['market_call_pct']}% of sessions, and {c['follow_pct']}% of its calls just follow its own call "
                  f"for the market. Its ranking within a day (AUC {c['daily_auc']}) adds only a little.")
    gap = c["got_pct"] - c["expected_pct"]
    honesty = ("its odds were honest" if abs(gap) <= 1 else
               f"it was a little overconfident ({-gap:.1f} points)" if gap < 0 else "it was a little too modest")
    limits.append(f"Its own odds expected about {c['expected_pct']}% right and it got {c['got_pct']}%: {honesty}. "
                  f"{c['middle_pct']}% of its calls sit between 40% and 60% up: chart and volume data carry little "
                  f"about one day ahead, and it knows it.")
    p = m.get("picks")
    if p and p.get("top_year_after_cost_pct") is not None:
        edge = p["top_avg_pct"] - p["liquid_avg_pct"]
        limits.append(f"Trading it: {p.get('skipped_locked_pct') or 0:.0f}% of its raw top {p['top']} each day were "
                      f"locked at the upper band and couldn't be bought. The buyable ones beat the market by "
                      f"{edge:+.3f}% a day, while a round trip costs about {p['cost_pct']}%, so buying them daily "
                      f"ends the year at {p['top_year_after_cost_pct']:+.1f}%.")
        if p["bottom_avg_pct"] < p["liquid_avg_pct"] - 0.1:
            worked.append(f"Its bottom {p['top']} each day fell {p['bottom_avg_pct']:+.3f}% the next day against "
                          f"{p['liquid_avg_pct']:+.3f}% for the market: it is better at what to avoid than at what "
                          f"to buy.")

    if (_dig(m, ("liquid", "auc")) or 0.5) < 0.55:
        nxt.append("Train and judge it only on stocks trading ₹5 crore+ a day, so it learns patterns that can be "
                   "traded instead of thin-stock quirks.")
    if regimes and min(regimes, key=lambda g: g["right_pct"])["went_up_pct"] > 50:
        nxt.append("Give it the world's overnight moves and India VIX (Chanakya's inputs), so it can see a market "
                   "turn coming instead of carrying yesterday's mood.")
    nxt.append("Predict each stock's move against the market instead of plain up or down, so a falling year can't "
               "do the work for it.")
    if p and (p.get("top_year_after_cost_pct") or 0) < 0:
        nxt.append("Hold the picks for 5 sessions instead of 1, so the costs are paid once a week, not every day.")
    if p and (p.get("skipped_locked_pct") or 0) > 20:
        nxt.append("Leave days when a stock is locked at a price band out of training, since nobody can trade at "
                   "that close.")

    checks, k = [], r["checks"]
    if k.get("excluded"):
        checks.append(f"{k['excluded']['symbols']:,} ETFs and fund units ({k['excluded']['calls']:,} calls) were left "
                      f"out of the scores: they trade in the EQ series, but they aren't companies.")
    if k["jumps"]:
        e = k["jump_example"]
        checks.append(f"{k['jumps']:,} calls had a next-day move beyond {100 * JUMP_DOWN:.0f}% or "
                      f"{100 * JUMP_UP:+.0f}%: splits and bonuses whose previous close the bhavcopy left unadjusted "
                      f"(like {e['symbol']} after {e['date']}). They aren't real moves. Runs from now on skip them, and "
                      f"keep the price line whole across them.")
    if k["locked_up"] or k["locked_down"]:
        checks.append(f"{k['locked_up']:,} calls were on stocks locked at their upper price band and "
                      f"{k['locked_down']:,} at their lower band. They count for right and wrong, but the daily picks "
                      f"skip them, since nobody could trade them at that close.")
    return {"headline": headline, "failed": failed, "worked": worked, "limits": limits, "next": nxt, "checks": checks}


if __name__ == "__main__":
    run_id = int(sys.argv[1])
    db = connect()
    try:
        db.execute("UPDATE runs SET report = ? WHERE id = ?", (json.dumps(build(db, run_id)), run_id))
        db.commit()
    finally:
        db.close()
    print(f"report for run #{run_id} written")
