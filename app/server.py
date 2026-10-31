"""Local API + UI server.

Usage: python -m uvicorn app.server:app --port 8000
"""
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (autolearn, backtest, chanakya, chitragupta, datastore, drona_call, keeper, knowledge, krishna, narad,
               overview, teacher, trikal)
from .claude_cli import ClaudeError
from .config import MARKETS, ROOT, TICKERS
from .db import connect
from .features import FEATURES, build
from .fetch import refresh
from .system import keep_awake

@asynccontextmanager
async def lifespan(_app: FastAPI):
    keep_awake()  # Windows doesn't fall asleep while the server runs (the screen may still turn off)
    autolearn.start()  # keeps retraining the models in a background thread
    chitragupta.start()  # scores the models' calls against the market every hour
    chanakya.start()  # each weekday morning, the overnight world's call on every tracked symbol
    trikal.start()  # the main prediction from all of them, refreshed with news until the open
    drona_call.start()  # each weekday morning, Drona's own call on every symbol, made with what it has learned
    if os.environ.get("CANDLECAST_LEARN", "1") != "0":
        knowledge.start()  # the teacher answers help requests and researches the market (CANDLECAST_LEARN=0 stops it)
    if os.environ.get("CANDLECAST_NARAD", "1") != "0":
        narad.start()  # Narad keeps collecting and reading market news (set CANDLECAST_NARAD=0 to stop)
    keeper.start()  # downloads the market's history (1m, 15m, 1h, daily) into market.db every weekday evening
    backtest.start_auto()  # while Auto run is on, starts each next backtest by itself, a step after the last cutoff
    krishna.start()  # watches all of them every 10 minutes, fixes what is safe to fix, reviews them daily
    yield


app = FastAPI(title="candlecast", lifespan=lifespan)

# UI bar size (minutes) -> interval the models were trained on.
INTERVAL_FOR = {15: "15m", 60: "1h", 1440: "1d"}
REFRESH_EVERY = 15  # seconds; Yahoo rate-limits aggressive polling
WARMUP = 300        # candles of history fed to the indicators (EMA/RSI need warm-up)

QUOTES_REFRESH_EVERY = 120  # seconds between background refreshes of every symbol
IST = timezone(timedelta(hours=5, minutes=30))

_last_refresh: dict[tuple[str, str], float] = {}
_models: dict[str, lgb.Booster] = {}
_lock = threading.Lock()
_quotes_refreshing = threading.Event()
_quotes_last = 0.0


def interval_for(minutes: int) -> str:
    if minutes not in INTERVAL_FOR:
        raise HTTPException(400, f"Supported bar sizes: {sorted(INTERVAL_FOR)} minutes")
    return INTERVAL_FOR[minutes]


def market_for(market: str) -> str:
    if market not in MARKETS:
        raise HTTPException(400, f"market must be one of {list(MARKETS)}")
    return market


def latest_model(conn, interval: str, market: str = "stocks"):
    row = conn.execute(
        "SELECT id, name, path, metrics FROM models WHERE interval = ? AND market = ? "
        "ORDER BY active DESC, id DESC LIMIT 1", (interval, market),
    ).fetchone()
    if row is None:
        raise HTTPException(503, f"No {market} {interval} model trained yet: Sanjay trains one within the hour")
    return row


def load_booster(path: str) -> lgb.Booster:
    with _lock:
        if path not in _models:
            _models[path] = lgb.Booster(model_file=str(ROOT / path))
        return _models[path]


@app.get("/api/candles")
def candles(symbol: str, minutes: int, limit: int = 49):
    interval = interval_for(minutes)
    conn = connect()
    try:
        key = (symbol, interval)
        if time.time() - _last_refresh.get(key, 0) > REFRESH_EVERY:
            have = conn.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND interval=?", key).fetchone()[0]
            try:
                refresh(conn, symbol, interval, None if have == 0 else "5d")
                _last_refresh[key] = time.time()
            except Exception as e:  # serve what the DB already has if Yahoo is down
                if have == 0:
                    raise HTTPException(502, f"Download failed: {e}")
        rows = conn.execute(
            "SELECT ts, open, high, low, close, volume FROM candles WHERE symbol=? AND interval=? ORDER BY ts DESC LIMIT ?",
            (symbol, interval, limit),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise HTTPException(404, f"No candles for {symbol}")
    keys = ("time", "open", "high", "low", "close", "volume")
    return [dict(zip(keys, r)) for r in reversed(rows)]


class PredictIn(BaseModel):
    symbol: str
    market: str
    minutes: int
    candles: list[dict]


@app.post("/api/predict")
def predict(body: PredictIn):
    if not body.candles:
        raise HTTPException(400, "candles is empty")
    interval = interval_for(body.minutes)
    last_ts = int(body.candles[-1]["time"])
    conn = connect()
    try:
        model_id, _, path, _ = latest_model(conn, interval, market_for(body.market))
        hist = pd.read_sql(
            "SELECT ts, open, high, low, close, volume FROM candles WHERE symbol=? AND interval=? AND ts<=? "
            "ORDER BY ts DESC LIMIT ?",
            conn, params=(body.symbol, interval, last_ts, WARMUP),
        ).iloc[::-1].reset_index(drop=True)
        if hist.empty or int(hist["ts"].iloc[-1]) != last_ts:
            raise HTTPException(409, "Candle not in DB yet — fetch /api/candles first")
        row = build(hist, interval).iloc[[-1]]
        prob_up = float(load_booster(path).predict(row[FEATURES])[0])
        # The candle being predicted is the one right after the last closed one.
        target_ts = last_ts + body.minutes * 60_000
        conn.execute(
            "INSERT OR IGNORE INTO predictions (model_id, symbol, interval, ts, prob_up) VALUES (?,?,?,?,?)",
            (model_id, body.symbol, interval, target_ts, prob_up),
        )
        conn.commit()
    finally:
        conn.close()
    up = prob_up >= 0.5
    return {"direction": "up" if up else "down", "probability": round((prob_up if up else 1 - prob_up) * 100, 1)}


@app.get("/api/history")
def history(symbol: str, minutes: int, limit: int = 12):
    """Saved predictions for this symbol, scored against the candle that actually followed. Newest first."""
    interval = interval_for(minutes)
    step = minutes * 60_000
    now_ms = int(time.time() * 1000)
    conn = connect()
    try:
        preds = conn.execute(
            "SELECT ts, prob_up FROM predictions WHERE symbol=? AND interval=? ORDER BY ts DESC, id DESC LIMIT ?",
            (symbol, interval, limit * 3),
        ).fetchall()
        out, seen = [], set()
        for ts, prob_up in preds:
            # ts is "last closed + one bar"; overnight the real next candle is the next session's first.
            nxt = conn.execute(
                "SELECT ts, close, high, low FROM candles WHERE symbol=? AND interval=? AND ts>=? ORDER BY ts LIMIT 1",
                (symbol, interval, ts),
            ).fetchone()
            prev = conn.execute(
                "SELECT close FROM candles WHERE symbol=? AND interval=? AND ts<? ORDER BY ts DESC LIMIT 1",
                (symbol, interval, ts),
            ).fetchone()
            if not nxt or not prev or nxt[0] in seen or nxt[0] + step > now_ms:
                continue  # outcome unknown yet, or already scored by a newer model
            seen.add(nxt[0])
            up = prob_up >= 0.5
            start, close, high, low = nxt
            before = prev[0]
            # An unchanged close has no direction: shown as flat and not scored (as the models train)
            actual = "up" if close > before else "down" if close < before else "flat"
            out.append({
                "start": start,
                "end": start + step,
                "predicted": "up" if up else "down",
                "probability": round((prob_up if up else 1 - prob_up) * 100),
                "actual": actual,
                "movePct": (close - before) / before * 100,
                "hit": None if actual == "flat" else up == (actual == "up"),
                # In price: the close before, this candle's close, and how far it went up and down on the way
                "prevClose": before,
                "close": close,
                "high": high,
                "low": low,
                "highPct": (high - before) / before * 100,
                "lowPct": (low - before) / before * 100,
            })
            if len(out) == limit:
                break
        return out
    finally:
        conn.close()


def _refresh_all_quotes():
    try:
        conn = connect()
        for symbol in TICKERS:
            try:
                refresh(conn, symbol, "15m", "5d")
                _last_refresh[(symbol, "15m")] = time.time()
            except Exception:
                pass  # keep the other symbols going
        conn.close()
    finally:
        _quotes_refreshing.clear()


def _freshen_quotes() -> None:
    """Refresh every symbol's 15-minute candles in the background when the last refresh is older than
    QUOTES_REFRESH_EVERY: the pages showing a price now (the chart picker, Trikal) stay current."""
    global _quotes_last
    if not _quotes_refreshing.is_set() and time.time() - _quotes_last > QUOTES_REFRESH_EVERY:
        _quotes_refreshing.set()
        _quotes_last = time.time()
        threading.Thread(target=_refresh_all_quotes, daemon=True).start()


@app.get("/api/quotes")
def quotes():
    """Last price, change vs previous session close and today's 15m closes for every symbol, from the DB.

    Triggers a background refresh when stale, so the next poll gets fresher numbers.
    """
    _freshen_quotes()
    conn = connect()
    try:
        out = {}
        for symbol in TICKERS:
            rows = conn.execute(
                "SELECT ts, close FROM candles WHERE symbol=? AND interval='15m' ORDER BY ts DESC LIMIT 80",
                (symbol,),
            ).fetchall()
            if not rows:
                continue
            day = lambda ts: datetime.fromtimestamp(ts / 1000, IST).date()
            last_day = day(rows[0][0])
            today = [c for ts, c in rows if day(ts) == last_day]
            prev_close = next((c for ts, c in rows if day(ts) < last_day), today[-1])
            out[symbol] = {
                "price": rows[0][1],
                "changePct": (rows[0][1] - prev_close) / prev_close * 100,
                "closes": today[::-1],
            }
        return out
    finally:
        conn.close()


@app.get("/api/models")
def models(market: str = "stocks"):
    """Name and walk-forward accuracy of the active model of each interval of a market (stocks | forex)."""
    conn = connect()
    try:
        out = {}
        for interval in INTERVAL_FOR.values():
            try:
                _, name, _, metrics = latest_model(conn, interval, market_for(market))
            except HTTPException:
                continue
            m = json.loads(metrics or "{}")
            out[interval] = {"name": name, "accuracy": m.get("accuracy"), "confident_accuracy": m.get("confident_accuracy")}
        return out
    finally:
        conn.close()


class AskIn(BaseModel):
    question: str


def _teacher_call(fn, *args):
    try:
        return fn(*args)
    except ClaudeError as e:
        raise HTTPException(503, f"Teacher unavailable: {e}")
    except RuntimeError as e:  # knowledge disk not connected
        raise HTTPException(503, str(e))


@app.post("/api/teacher/ask")
def teacher_ask(body: AskIn):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "question is empty")
    return _teacher_call(teacher.answer, question[:4000])


@app.post("/api/teacher/review")
def teacher_review(body: AskIn):
    return _teacher_call(teacher.review, body.question[:2000])


@app.get("/api/teacher/status")
def teacher_status():
    return _teacher_call(teacher.status)


@app.get("/api/teacher/history")
def teacher_history(limit: int = 30):
    return _teacher_call(teacher.history, min(limit, 200))


@app.get("/api/teacher/lesson/{topic_id}")
def teacher_lesson(topic_id: int):
    found = _teacher_call(teacher.lesson, topic_id)
    if found is None:
        raise HTTPException(404, "Lesson not learned yet")
    return found


@app.get("/api/teacher/mistakes")
def teacher_mistakes():
    return _teacher_call(teacher.mistakes)


def _view(fn, *args):
    try:
        return fn(*args)
    except RuntimeError as e:  # E: disk not connected or locked
        raise HTTPException(503, str(e))


@app.get("/api/overview")
def overview_view():
    """Whether every model is doing its job, Trikal's strongest calls, the scorecard and the latest news."""
    view = _view(overview.view)
    view["models"] += [keeper.health(), krishna.health()]
    return view


def _interval(interval: str) -> str:
    if interval not in datastore.INTERVALS:
        raise HTTPException(400, f"interval must be one of {list(datastore.INTERVALS)}")
    return interval


@app.get("/api/data/summary")
def data_summary():
    """How far market.db's history goes per bar size, the sessions missing, and the downloads' state."""
    return {**_view(datastore.summary), "keeper": keeper.view()}


@app.get("/api/data/symbols")
def data_symbols(interval: str, page: int = 1, q: str = ""):
    """One page (20) of every symbol downloaded at a bar size, with its bars, first and last day, days missing."""
    return _view(datastore.symbols, _interval(interval), page, q.strip()[:40])


@app.get("/api/data/bars")
def data_bars(interval: str, symbol: str, page: int = 1):
    """One page (20) of a symbol's bars at a bar size, newest first."""
    return _view(datastore.bars, _interval(interval), symbol[:30], page)


@app.post("/api/data/sync")
def data_sync():
    """Start the downloads now (NSE bhavcopy, then Yahoo 1m/15m/1h/daily) instead of waiting for 19:00."""
    return {"started": keeper.sync_now(), "keeper": keeper.view()}


@app.get("/api/backtest")
def backtest_view(run: int | None = None):
    """Every one-year backtest run, and one finished run's results and days (the latest unless `run` says)."""
    return _view(backtest.view, run)


@app.get("/api/backtest/day")
def backtest_day(run: int, date: str, page: int = 1, q: str = "", show: str = "all", sort: str = "confidence"):
    """One page (20) of a session's calls in a run: every company called that day and how each turned out."""
    if show not in backtest.SHOWS or sort not in backtest.SORTS:
        raise HTTPException(400, f"show must be one of {list(backtest.SHOWS)}, sort one of {list(backtest.SORTS)}")
    return _view(backtest.day_calls, run, date[:10], page, q.strip()[:40], show, sort)


@app.get("/api/backtest/companies")
def backtest_companies(run: int, page: int = 1, q: str = "", sort: str = "right"):
    """One page (20) of every company's year in a run: calls, right, turnover."""
    if sort not in backtest.COMPANY_SORTS:
        raise HTTPException(400, f"sort must be one of {list(backtest.COMPANY_SORTS)}")
    return _view(backtest.companies, run, page, q.strip()[:40], sort)


@app.get("/api/backtest/company")
def backtest_company(run: int, symbol: str):
    """A company's totals and every call it got in a run."""
    found = _view(backtest.company, run, symbol[:30])
    if found is None:
        raise HTTPException(404, f"{symbol} got no calls in run {run}")
    return found


class BacktestIn(BaseModel):
    cutoff: str | None = None
    retrain: str = "once"  # "quarter" or "month": a fresh model for each stretch of the test year
    history: str = "all"  # "10y" or "5y": each model learns only that many years of sessions


@app.post("/api/backtest/run")
def backtest_run(body: BacktestIn):
    """Start a backtest in the background: train before the cutoff (default a year back), call every day after,
    retraining every quarter or month of that year, on all history or only the last 10 or 5 years, as asked."""
    cutoff = None
    if body.cutoff:
        try:
            cutoff = datetime.strptime(body.cutoff, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "cutoff must be a date like 2025-10-30")
        if not datetime(1998, 1, 1).date() <= cutoff <= (datetime.now() - timedelta(days=30)).date():
            raise HTTPException(400, "pick a cutoff from 1998 up to a month ago: the model needs years to learn "
                                     "from and at least a month to be tested on")
    if body.retrain not in backtest.RETRAINS:
        raise HTTPException(400, f"retrain must be one of {list(backtest.RETRAINS)}")
    if body.history not in backtest.HISTORY:
        raise HTTPException(400, f"history must be one of {list(backtest.HISTORY)}")
    return {"started": backtest.start(cutoff, body.retrain, body.history), **backtest.view()}


@app.post("/api/backtest/pause")
def backtest_pause():
    """Freeze the running backtest where it stands; Continue picks it up from there."""
    return {"done": backtest.pause(), **backtest.view()}


@app.post("/api/backtest/resume")
def backtest_resume():
    """Let a paused backtest go on."""
    return {"done": backtest.resume(), **backtest.view()}


class BacktestAutoIn(BaseModel):
    on: bool
    step: str = "session"  # how far each next cutoff moves: "session", "week" or "month"
    runs: int = 10
    retrain: str = "once"
    history: str = "all"


@app.post("/api/backtest/auto")
def backtest_auto(body: BacktestAutoIn):
    """Turn Auto run on or off: each next backtest starts by itself, its cutoff a step after the last run's."""
    for name, value, allowed in (("step", body.step, backtest.STEPS), ("retrain", body.retrain, backtest.RETRAINS),
                                 ("history", body.history, backtest.HISTORY)):
        if value not in allowed:
            raise HTTPException(400, f"{name} must be one of {list(allowed)}")
    if not 1 <= body.runs <= 100:
        raise HTTPException(400, "runs must be from 1 to 100")
    backtest.set_auto(body.on, body.step, body.runs, body.retrain, body.history)
    return backtest.view()


@app.get("/api/krishna")
def krishna_view():
    """What is wrong now, what Krishna fixed or found lately, and its latest daily review."""
    return _view(krishna.view)


@app.post("/api/krishna/check")
def krishna_check():
    """Check everything now (with the safe fixes), instead of waiting for the next 10-minute round."""
    _view(krishna.run_check)
    return _view(krishna.view)


@app.post("/api/krishna/review")
def krishna_review():
    """Write today's review now. Takes a few minutes: the best AI plan reads every scorecard first."""
    try:
        _view(krishna.review, True)
    except ClaudeError as e:
        raise HTTPException(503, f"No AI plan could write the review right now: {e}")
    return _view(krishna.view)


@app.get("/api/trikal")
def trikal_view():
    """Trikal's latest call with each symbol's price now, every model's scorecard, Trikal's scored calls and
    Narad's and Drona's activity."""
    _freshen_quotes()  # its "now" column comes from the latest 15-minute candles
    return _view(trikal.view)


@app.get("/api/news")
def news_view(scope: str = "tracked", symbol: str = "", limit: int = 60):
    """Narad's notes (tracked stocks, help requests or all) with Drona's answers."""
    return _view(narad.feed, scope, symbol, max(1, min(limit, 300)))


@app.get("/api/readers")
def readers_view():
    """Every reader Narad uses (each Gemini and Groq key, and Ollama) with what it is doing and has done."""
    return _view(narad.readers_view)


@app.get("/api/writers")
def writers_view():
    """Drona's writers (agy on the Google AI Pro quota): state, calls and tokens in the last 24 h and 7 days."""
    return _view(teacher.writers_view)


class KeyIn(BaseModel):
    provider: str
    key: str
    name: str = ""


# Only this laptop reaches the server (127.0.0.1), and these take JSON or DELETE, which another website in
# the browser can't send here without a CORS preflight this server never allows.
@app.post("/api/keys")
def add_key(body: KeyIn):
    """Check a Gemini or Groq key with its provider, store it and start reading the news with it."""
    try:
        return narad.add_key(body.provider, body.key, body.name)
    except ValueError as e:
        raise HTTPException(400, str(e))


class PauseIn(BaseModel):
    paused: bool


@app.post("/api/keys/{kid}/pause")
def pause_key(kid: str, body: PauseIn):
    """Pause or resume a key without removing it."""
    if not narad.pause_key(kid, body.paused):
        raise HTTPException(404, "No such key")
    return {"id": kid, "paused": body.paused}


@app.delete("/api/keys/{kid}")
def remove_key(kid: str):
    if not narad.remove_key(kid):
        raise HTTPException(404, "No such key")
    return {"removed": kid}


@app.get("/api/sanjay")
def sanjay_view(market: str = "stocks"):
    """Sanjay's latest daily call on every symbol of a market (stocks | forex) and how its daily model tested."""
    return _view(autolearn.view, market_for(market))


@app.get("/api/world")
def world_view():
    """Chanakya's latest call and the overnight moves it read."""
    return _view(chanakya.view)


@app.get("/api/scores")
def scores_view():
    """Chitragupta's track records and the latest scored calls."""
    return _view(chitragupta.view)


class UIFiles(StaticFiles):
    """The built UI. Unknown non-API paths get index.html, so reloading a page such as /teacher works."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code != 404 or path.startswith("api"):
                raise
            return await super().get_response("index.html", scope)


DIST = ROOT / "web" / "dist"
if DIST.exists():
    app.mount("/", UIFiles(directory=DIST, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse)
    def no_ui():
        return "<p>UI not built. Run <code>build_ui.bat</code>, then restart.</p>"
