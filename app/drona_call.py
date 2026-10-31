"""Drona's call: the market teacher's own prediction for each tracked symbol's next session, made with
everything it has learned.

For each symbol Drona gets the last ten sessions of its chart and the indicators the syllabus teaches (RSI,
MACD, moving averages, volatility, volume, the last candle's pattern, the 52-week range), the market's move, the
overnight world (Chanakya's eight series), the last three days of Narad's news with Drona's own answers where
Narad asked, Sanjay's and Chanakya's calls with Chitragupta's record of each, and the lessons in its knowledge
base that best match the situation. It weighs them as its lessons teach and answers with a probability of
closing up, its reasons, the lessons it used and what would prove it wrong.

Trikal takes Drona's call first (trikal.call), since Drona has already weighed the other models. Once Drona has
MIN_CALLS scored calls, Trikal keeps it first only while its log loss is no worse than the plain average of
Sanjay and Chanakya on the same sessions (trusted); otherwise Trikal goes back to the average and says why.

Made on weekdays from 06:00 IST, once Sanjay's and Chanakya's calls exist, once per symbol per session, with the
Google AI Pro writers (DRONA_WRITERS, then account 2's), never the Claude Code login. Stored in memory.db
signals as model drona_call, where Chitragupta scores it like every other call.

Usage: started by app/server.py; or once by hand: python -m app.drona_call
"""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from . import chanakya
from .chitragupta import INDEX, IST, closes, track_record
from .claude_cli import ClaudeError, UsageLimit
from .config import DRONA_WRITERS, DRONA_WRITERS_2, FOREX, SYMBOLS, TICKERS
from .db import connect as connect_app
from .fetch import download
from .knowledge_db import connect as connect_knowledge, search
from .memory_db import connect as connect_memory
from .system import logger, nap
from .teacher import write

MODEL = "drona_call"
EVERY = 10 * 60      # seconds between checks
LESSONS = 5          # lessons from the knowledge base given with each call
PARALLEL = 3         # calls written at once
MIN_CALLS = 150      # scored calls before Drona's place in Trikal is checked against the plain average
WRITERS = DRONA_WRITERS + DRONA_WRITERS_2
WORLD = {"sp500": "S&P 500", "nasdaq": "Nasdaq", "brent": "Brent crude", "usdinr": "USD/INR",
         "us10y": "US 10-year yield", "gold": "Gold", "dollar": "Dollar index", "indiavix": "India VIX"}

SYSTEM = """You are Drona, the market teacher of CandleCast. You have studied the stock market from beginner to \
expert: fundamentals and valuation, technical analysis and candlesticks, trading psychology and risk, derivatives \
and quant finance, machine learning for markets, and India's market rules. Now make one call: the probability \
that a symbol's next session closes above its last close.

Weigh the evidence the way your lessons teach: the chart, its indicators and its last candle, volume, the market \
and the overnight world, the news, and the two models' calls with their records. Use the lessons given and cite \
each one you rely on by its id. Do not invent facts that are not in the evidence.

Be calibrated. Most days are close to a coin toss: when the evidence is mixed, a probability between 0.45 and \
0.55 is the honest answer, and 0.65 or more needs strong evidence that agrees. A call of 0.60 should come true \
about 60 times in 100. The models' records tell you how far to trust them.

Reply with JSON only, nothing before or after it:
{"prob_up": 0.00 to 1.00, "confidence": "low" | "medium" | "high", "reasons": ["3 to 5 short reasons, the \
strongest first"], "lessons": [ids of the lessons you used], "risks": ["what would prove this call wrong"]}"""

say = logger("drona_call")  # also appended to <market dir>/logs/drona_call.log


def _candles(app, symbol: str, as_of: str) -> pd.DataFrame:
    df = pd.read_sql("SELECT ts, open, high, low, close, volume FROM candles WHERE symbol = ? AND interval = '1d' "
                     "ORDER BY ts", app, params=(symbol,))
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True).dt.tz_convert(IST).dt.strftime("%Y-%m-%d")
    return df.drop_duplicates("date", keep="last")[lambda d: d["date"] <= as_of].tail(300).reset_index(drop=True)


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    change = close.diff()
    gain = change.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-change).clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def _candle(df: pd.DataFrame) -> list[str]:
    """Names of the patterns the last candle (with the one before) makes."""
    o, h, l, c = (df[k].iloc[-1] for k in ("open", "high", "low", "close"))
    po, ph, pl, pc = (df[k].iloc[-2] for k in ("open", "high", "low", "close"))
    body, rng = abs(c - o), h - l
    if rng <= 0:
        return []
    upper, lower, falling = h - max(o, c), min(o, c) - l, df["close"].iloc[-1] < df["close"].iloc[-6]
    names = []
    if body <= 0.1 * rng:
        names.append("doji")
    elif body >= 0.9 * rng:
        names.append(f"{'bullish' if c > o else 'bearish'} marubozu")
    if lower >= 2 * body and upper <= max(body, 0.1 * rng):
        names.append("hammer" if falling else "hanging man")
    if upper >= 2 * body and lower <= max(body, 0.1 * rng):
        names.append("inverted hammer" if falling else "shooting star")
    if pc < po and c > o and c >= po and o <= pc:
        names.append("bullish engulfing")
    if pc > po and c < o and c <= po and o >= pc:
        names.append("bearish engulfing")
    if h < ph and l > pl:
        names.append("inside day")
    if o > ph:
        names.append("gap up")
    elif o < pl:
        names.append("gap down")
    return names


def _chart(df: pd.DataFrame, pair: bool) -> tuple[str, list[str]]:
    """The last ten sessions and the indicators at the last close, as text, and words to find lessons by."""
    c, v = df["close"], df["volume"].fillna(0)
    chg = c.pct_change()
    ema = lambda n: c.ewm(span=n, adjust=False).mean()
    macd = ema(12) - ema(26)
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    rsi = float(_rsi(c).iloc[-1])
    avg_vol = v.rolling(20).mean()
    vol_ratio = float(v.iloc[-1] / avg_vol.iloc[-1]) if not pair and avg_vol.iloc[-1] else None
    year = df.tail(250)
    hi, lo = float(year["high"].max()), float(year["low"].min())
    last = float(c.iloc[-1])
    digits = 4 if pair else 2
    rows = [f"{r.date}: open {r.open:.{digits}f}, high {r.high:.{digits}f}, low {r.low:.{digits}f}, close "
            f"{r.close:.{digits}f} ({100 * g:+.2f}%)" + (f", volume {r.volume / a:.1f}x its 20-day average"
                                                       if not pair and a else "")
            for r, g, a in zip(df.tail(10).itertuples(), chg.tail(10), avg_vol.tail(10))]
    patterns = _candle(df)
    sma200 = c.rolling(200).mean().iloc[-1]
    lines = [
        f"RSI(14) {rsi:.1f}",
        f"MACD histogram {hist.iloc[-1]:+.{digits}f} ({'rising' if hist.iloc[-1] > hist.iloc[-2] else 'falling'}"
        f"{', just crossed above its signal' if hist.iloc[-1] > 0 >= hist.iloc[-2] else ''}"
        f"{', just crossed below its signal' if hist.iloc[-1] < 0 <= hist.iloc[-2] else ''})",
        f"close vs EMA 21: {100 * (last / ema(21).iloc[-1] - 1):+.1f}%, vs EMA 50: {100 * (last / ema(50).iloc[-1] - 1):+.1f}%"
        + (f", vs the 200-day average: {100 * (last / sma200 - 1):+.1f}%" if pd.notna(sma200) else ""),
        f"20-session return {100 * (last / c.iloc[-21] - 1):+.1f}%, daily volatility {100 * chg.tail(20).std():.2f}%",
        f"52-week range: {100 * (1 - last / hi):.1f}% below the high, {100 * (last / lo - 1):.1f}% above the low",
        f"last candle: {', '.join(patterns) or 'no named pattern'}",
    ]
    words = list(patterns)
    words += ["RSI overbought"] if rsi >= 70 else ["RSI oversold"] if rsi <= 30 else []
    words += ["MACD crossover"] if (hist.iloc[-1] > 0) != (hist.iloc[-2] > 0) else []
    words += ["52-week high breakout"] if last >= 0.98 * hi else ["52-week low"] if last <= 1.02 * lo else []
    words += ["volume surge breakout"] if vol_ratio and vol_ratio >= 1.8 else []
    words += ["uptrend moving average"] if last > ema(50).iloc[-1] > ema(200).iloc[-1] else \
        ["downtrend moving average"] if last < ema(50).iloc[-1] < ema(200).iloc[-1] else []
    return "\n".join(["Last ten sessions:", *rows, "Indicators at the last close:", *lines]), words


def _world(today: str) -> tuple[str, list[str]]:
    """The overnight world: each series' last change dated before the session, as Chanakya reads it."""
    parts, words = [], []
    for name, label in WORLD.items():
        try:
            close = download(chanakya.GLOBAL[name], "1d", "1mo")["close"]
        except Exception:  # one series missing doesn't stop the call
            continue
        close = close[close.index.strftime("%Y-%m-%d") < today].dropna()
        if len(close) < 2:
            continue
        change = 100 * (close.iloc[-1] / close.iloc[-2] - 1)
        parts.append(f"{label} {close.iloc[-1]:.2f} ({change:+.2f}%)" if name == "indiavix" else f"{label} {change:+.2f}%")
        if name in ("sp500", "nasdaq") and abs(change) >= 1:
            words.append(f"US market {'rally' if change > 0 else 'selloff'} global cues")
        if name == "indiavix" and change >= 8:
            words.append("India VIX spike volatility")
        if name == "brent" and abs(change) >= 2:
            words.append("crude oil price")
    return ("Overnight world (last change before this session): " + ", ".join(parts)) if parts else "", words


def _news(mem, symbol: str, since: str) -> tuple[str, list[str]]:
    """The last three days' news on the symbol (market-wide news for NIFTY 50 and the rupee pairs)."""
    where, args = ("n.about = 'market'", ()) if symbol == INDEX or symbol in FOREX else ("n.symbols LIKE ?", (f'%"{symbol}"%',))
    rows = mem.execute(
        "SELECT w.title, n.event, n.sentiment, n.positives, n.negatives, h.answer FROM news_notes n "
        "JOIN news w ON w.id = n.news_id LEFT JOIN help_requests h ON h.asker = 'narad' "
        "AND h.ref = 'news:' || n.news_id AND h.status = 'answered' "
        f"WHERE {where} AND COALESCE(w.published_at, w.fetched_at) >= ? "
        "ORDER BY COALESCE(w.published_at, w.fetched_at) DESC LIMIT 6", (*args, since)).fetchall()
    lines, words = [], []
    for title, event, sentiment, pos, neg, answer in rows:
        drona = json.loads(answer)["sentiment"] if answer else None
        points = json.loads(pos)[:2] + [f"risk: {x}" for x in json.loads(neg)[:2]]
        lines.append(f"- [{event}; Narad {sentiment:+.1f}" + (f", your earlier answer {drona:+.1f}" if drona is not None else "")
                     + f"] {title}" + (f" ({'; '.join(points)})" if points else ""))
        words.append(event.replace("_", " "))
    return ("News, last three days:\n" + "\n".join(lines)) if lines else "News, last three days: none", words


def _lessons(kb, words: list[str], pair: bool) -> list[dict]:
    """The lessons that best match the situation: its candle, indicators, news and world."""
    query = " ".join(words + (["rupee currency forex RBI"] if pair else ["stock next day price move"]))
    seen, out = set(), []
    for hit in search(kb, query, 4 * LESSONS):
        if hit["topic_id"] in seen:
            continue
        seen.add(hit["topic_id"])
        out.append({"id": hit["topic_id"], "title": hit["title"], "text": " ".join(hit["body"].split())[:900]})
        if len(out) == LESSONS:
            break
    return out


def _prompt(app, mem, kb, symbol: str, as_of: str, today: str, models: dict, records: dict,
            world: tuple[str, list[str]]) -> tuple[str, list[dict]]:
    pair = symbol in FOREX
    df = _candles(app, symbol, as_of)
    if len(df) < 60:
        raise ClaudeError(f"only {len(df)} daily candles for {symbol}")
    chart, words = _chart(df, pair)
    since = (datetime.fromisoformat(today) - timedelta(days=3)).date().isoformat()
    news, news_words = _news(mem, symbol, since)
    market = ""
    if symbol in SYMBOLS and symbol != INDEX:
        nifty = _candles(app, INDEX, as_of)["close"]
        if len(nifty) > 6:
            market = (f"Market: NIFTY 50 {100 * (nifty.iloc[-1] / nifty.iloc[-2] - 1):+.2f}% on the last session, "
                      f"{100 * (nifty.iloc[-1] / nifty.iloc[-6] - 1):+.2f}% over five.")
    rec = lambda m: (f"{records[m][1]}% right over {records[m][0]:,} scored calls" if m in records
                     else "no scored calls yet")
    lessons = _lessons(kb, words + news_words + world[1], pair)
    kind = "a rupee pair (RBI reference market); its day ends at 05:30 IST" if pair else \
        "the NIFTY 50 index" if symbol == INDEX else "an NSE stock"
    parts = [
        f"Symbol: {symbol}, {kind}. Call the session after {as_of}: will it close above {as_of}'s close?",
        chart, market, world[0], news,
        f"Models: Sanjay (the chart model) says {100 * models['sanjay']:.0f}% up; its record: {rec('sanjay')}. "
        f"Chanakya (the overnight world model) says {100 * models['chanakya']:.0f}% up; its record: {rec('chanakya')}.",
        "Lessons from your knowledge base:\n" + "\n".join(f"[lesson {x['id']}] {x['title']}: {x['text']}"
                                                          for x in lessons) if lessons else "",
    ]
    return "\n\n".join(p for p in parts if p), lessons


def _parse(text: str, lessons: list[dict]) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ClaudeError(f"no JSON in the reply: {text[:200]}")
    try:
        got = json.loads(m.group(0))
        p = float(got["prob_up"])
    except (ValueError, KeyError, TypeError) as e:
        raise ClaudeError(f"unreadable reply ({e}): {text[:200]}")
    if not 0 <= p <= 1:
        raise ClaudeError(f"prob_up {p} is not a probability")
    titles = {x["id"]: x["title"] for x in lessons}
    used = [int(i) for i in got.get("lessons") or [] if str(i).strip().isdigit() and int(i) in titles]
    texts = lambda key, n: [str(x)[:300] for x in got.get(key) or [] if str(x).strip()][:n]
    return {"prob_up": min(max(p, 0.01), 0.99), "confidence": str(got.get("confidence", ""))[:10],
            "reasons": texts("reasons", 6), "risks": texts("risks", 4),
            "lessons": [{"id": i, "title": titles[i]} for i in dict.fromkeys(used)]}


def due(mem, now: datetime) -> dict[str, tuple[str, dict]]:
    """Symbols whose Sanjay and Chanakya calls for their last finished session exist and Drona's doesn't:
    {symbol: (as_of, {sanjay, chanakya})}."""
    app = connect_app()
    try:
        px = closes(app)
    finally:
        app.close()
    today = now.date().isoformat()
    days = [d for d in sorted(px.get(INDEX, {})) if d < today]
    calendar = chanakya.calendars(px, days, now)
    as_of = {s: calendar[s][-1] for s in TICKERS if calendar.get(s)}
    models = {}
    for model, symbol, d, p in mem.execute("SELECT model, symbol, as_of, prob_up FROM signals "
                                           "WHERE model IN ('sanjay', 'chanakya', ?)", (MODEL,)):
        if as_of.get(symbol) == d:
            models.setdefault(symbol, {})[model] = p
    return {s: (as_of[s], m) for s, m in models.items() if {"sanjay", "chanakya"} <= set(m) and MODEL not in m}


def call(mem, now: datetime) -> int:
    """Drona's call on every symbol that is due; returns how many were made."""
    todo = due(mem, now)
    if not todo:
        return 0
    today = now.date().isoformat()
    records = {m: (n, right) for m, event, n, right, _ in track_record(mem) if not event}
    world = _world(today)
    app, kb = connect_app(), connect_knowledge()
    try:
        prompts = {}
        for symbol, (as_of, models) in todo.items():
            try:
                prompts[symbol] = _prompt(app, mem, kb, symbol, as_of, today, models, records, world)
            except ClaudeError as e:
                say(f"{symbol}: skipped, {e}")
    finally:
        app.close()
        kb.close()

    def one(symbol: str):
        prompt, lessons = prompts[symbol]
        text, used = write(prompt, SYSTEM, kind="call", cloud=False, timeout=600, writers=WRITERS,
                           what=f"Drona's call on {symbol}")
        return {**_parse(text, lessons), "writer": used}

    made = 0
    with ThreadPoolExecutor(PARALLEL) as pool:
        futures = {symbol: pool.submit(one, symbol) for symbol in prompts}
        for symbol, future in futures.items():
            as_of, models = todo[symbol]
            try:
                got = future.result()
            except UsageLimit as e:
                say(f"{symbol}: no writer has usage left ({e}); tried again in {EVERY // 60} min")
                continue
            except ClaudeError as e:
                say(f"{symbol}: failed, {e}")
                continue
            detail = {**{k: v for k, v in got.items() if k != "prob_up"}, "sanjay": round(models["sanjay"], 4),
                      "chanakya": round(models["chanakya"], 4)}
            with mem:
                mem.execute("INSERT OR IGNORE INTO signals (model, symbol, as_of, prob_up, detail) VALUES (?, ?, ?, ?, ?)",
                            (MODEL, symbol, as_of, got["prob_up"], json.dumps(detail)))
            made += 1
            say(f"{symbol} after {as_of}: {100 * got['prob_up']:.0f}% up ({got['confidence']}) by {got['writer']}; "
                f"{len(got['lessons'])} lessons used")
    return made


def trusted(mem) -> tuple[bool, str]:
    """Whether Trikal takes Drona's call first, and why. First until MIN_CALLS of Drona's calls are scored; after
    that only while its log loss is no worse than the plain average of Sanjay and Chanakya on the same sessions."""
    rows = np.array(mem.execute(
        "SELECT d.prob_up, (s.prob_up + c.prob_up) / 2, sc.move > 0 FROM signals d "
        "JOIN signals s ON s.model = 'sanjay' AND s.symbol = d.symbol AND s.as_of = d.as_of "
        "JOIN signals c ON c.model = 'chanakya' AND c.symbol = d.symbol AND c.as_of = d.as_of "
        "JOIN scores sc ON sc.model = ? AND sc.ref = 'signal:' || d.as_of AND sc.symbol = d.symbol "
        "WHERE d.model = ? AND sc.move <> 0", (MODEL, MODEL)).fetchall(), dtype=float).reshape(-1, 3)
    n = len(rows)
    if n < MIN_CALLS:
        return True, f"Drona's call comes first; it is checked against the models' average after {MIN_CALLS} scored calls ({n} so far)."
    loss = lambda q: float(-np.mean(rows[:, 2] * np.log(np.clip(q, 0.01, 0.99))
                                    + (1 - rows[:, 2]) * np.log(1 - np.clip(q, 0.01, 0.99))))
    drona, average = loss(rows[:, 0]), loss(rows[:, 1])
    if drona <= average:
        return True, f"Drona's call comes first: over {n} scored calls its log loss {drona:.4f} is no worse than the average's {average:.4f}."
    return False, (f"Back to the models' average: over {n} scored calls Drona's log loss {drona:.4f} is worse than "
                   f"the average's {average:.4f}. Drona's call stays on record and comes first again once it catches up.")


def once() -> int:
    """Drona's calls when they are due (weekdays from 06:00 IST until the close); returns calls made."""
    now = datetime.now(IST)
    if now.weekday() >= 5 or now.hour < chanakya.FROM_HOUR or (now.hour, now.minute) >= chanakya.CLOSE:
        return 0
    mem = connect_memory()
    try:
        return call(mem, now)
    finally:
        mem.close()


def run() -> None:
    from . import trikal  # Trikal reads Drona's calls: refresh it as soon as new ones exist
    say("started")
    while True:
        try:
            if once():
                trikal.once()
        except Exception as e:  # the disk, a network hiccup: keep the loop alive
            say(f"error — {type(e).__name__}: {e}")
        nap(EVERY)


def start() -> None:
    if not any(t.name == "drona_call" and t.is_alive() for t in threading.enumerate()):
        threading.Thread(target=run, daemon=True, name="drona_call").start()


if __name__ == "__main__":
    mem = connect_memory()
    try:
        print(f"{call(mem, datetime.now(IST))} calls made")
    finally:
        mem.close()
