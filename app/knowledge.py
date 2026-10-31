"""The teacher's self-study loop: researches the stock market topic by topic with web search (DRONA_WRITERS),
from the basics to expert level, and stores every lesson in E:/candlecast-data/knowledge.db.

Each lesson proposes deeper subtopics, which are queued and learned later, so the curriculum keeps
going deeper. Order: questions the teacher could not answer first, then shallow before deep
(basics before advanced). Before each topic, Chitragupta's new scores are studied (teacher.study_scores:
mistakes become high-priority topics, proven help answers become checked lessons) and the help requests the
other models raised are answered (teacher.help_models, one batch per topic). Only one learner runs at a time (lock file); safe
to stop and restart.

Usage: started by app/server.py; or on its own: python -m app.knowledge
"""
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

from .claude_cli import ClaudeError, UsageLimit
from . import agy_cli, codex_cli, syllabus
from .config import CODEX_WRITERS, DRONA_WRITERS, DRONA_WRITERS_2, EXTRA_LEARNERS, MARKET_DIR
from .knowledge_db import add_topic, connect, set_meta
from .system import keep_awake, logger, nap, single_instance
from .teacher import ALL_WRITERS, help_models, study_scores, write

PAUSE = int(os.environ.get("CANDLECAST_LEARN_PAUSE", "20"))  # seconds between topics; raise it to use less of the Pro quota
LIMIT_WAIT = 30 * 60       # seconds to wait when Claude's usage limit is hit
# Topics this deep don't propose further subtopics. start_fast.bat sets 1: the lessons stop adding topics, so the
# learners work through the queue instead of growing it ~4x faster than they learn.
MAX_DEPTH = int(os.environ.get("CANDLECAST_MAX_DEPTH", "8"))
MAX_ATTEMPTS = 3
LESSON_TIMEOUT = 25 * 60   # seconds for one lesson: the thinking models research for 5-15 minutes

# Root subjects: together they span everything a market teacher must know, beginner to quant.
ROOTS = [
    ("What a stock market is: shares, companies, exchanges and why markets exist", "the foundation"),
    ("Indian market structure: NSE, BSE, SEBI, depositories, brokers, clearing corporations", "who does what in India"),
    ("Trade lifecycle in India: order, matching, clearing, T+1 / T+0 settlement, demat", "how a trade really completes"),
    ("Order types and exchange matching engines: limit, market, SL, SL-M, IOC, AMO, auctions", "execution mechanics"),
    ("Market microstructure: order book, bid-ask spread, liquidity, impact cost, HFT, algo trading", "how prices form tick by tick"),
    ("Indices: Nifty 50, Sensex, Bank Nifty, sector indices — construction, free float, rebalancing", "benchmarks"),
    ("Candlestick charts and price action: patterns, support, resistance, trends", "chart reading"),
    ("Technical indicators and their math: moving averages, RSI, MACD, Bollinger, ATR, VWAP, volume", "indicator internals"),
    ("Dow theory, Elliott wave, Wyckoff, market breadth and intermarket analysis", "classic market theories"),
    ("Fundamental analysis: business models, moats, management quality, industry analysis", "what a company is worth"),
    ("Financial statements: balance sheet, P&L, cash flow, Ind AS, notes to accounts", "reading the numbers"),
    ("Financial ratios: P/E, P/B, EV/EBITDA, ROE, ROCE, DuPont, debt ratios, working capital cycle", "comparing companies"),
    ("Valuation: DCF, WACC, terminal value, relative valuation, sum of the parts, reverse DCF", "pricing a business"),
    ("Forensic accounting and corporate governance red flags: Satyam, IL&FS, Yes Bank cases", "avoiding frauds"),
    ("Corporate actions: dividends, splits, bonus, rights, buybacks, mergers, demergers, delisting", "events that change shares"),
    ("IPOs, FPOs, OFS, QIPs, SME listings, grey market, anchor investors, book building", "primary market"),
    ("Equity derivatives in India: futures, contract specs, lot size, margins (SPAN, exposure), MTM", "F&O basics"),
    ("Options from first principles: calls, puts, payoffs, moneyness, intrinsic and time value", "options foundation"),
    ("Option pricing: Black-Scholes, binomial trees, put-call parity, implied volatility", "option math"),
    ("Option Greeks: delta, gamma, theta, vega, rho, and higher-order Greeks in practice", "risk of options"),
    ("Volatility: historical vs implied, India VIX, volatility smile and skew, term structure", "pricing fear"),
    ("Option strategies: spreads, straddles, strangles, iron condors, calendars, ratio spreads, hedging", "positions traders build"),
    ("Open interest, PCR, max pain, option chain analysis and FII/DII derivatives data", "reading F&O data"),
    ("Risk management: position sizing, stop losses, Kelly criterion, drawdowns, risk of ruin", "staying alive"),
    ("Portfolio theory: diversification, Markowitz, CAPM, beta, Sharpe, Sortino, factor models", "building portfolios"),
    ("Quantitative trading: backtesting, walk-forward, overfitting, look-ahead bias, transaction costs", "testing strategies honestly"),
    ("Statistical arbitrage, pairs trading, mean reversion, momentum and market anomalies", "quant strategies"),
    ("Machine learning for markets: features, labels, leakage, non-stationarity, evaluation", "AI that predicts prices"),
    ("Macroeconomics and markets: GDP, inflation, interest rates, RBI monetary policy, liquidity", "the big picture"),
    ("Fund flows: FII/FPI, DII, mutual fund SIP flows, and their effect on Indian markets", "who moves the market"),
    ("Bond markets and the yield curve: G-secs, duration, convexity, credit spreads", "rates and debt"),
    ("Currency and commodity markets: USD/INR, crude, gold, MCX, and their link to equities", "related markets"),
    ("Mutual funds, ETFs, index funds, PMS, AIFs: structure, costs, tracking error", "investing vehicles"),
    ("Indian taxation of market income: STCG, LTCG, STT, F&O as business income, set-off rules", "after-tax returns"),
    ("SEBI regulations: insider trading, SAST, LODR, F&O retail rules, margin and pledge rules", "the rulebook"),
    ("Market manipulation and frauds: pump and dump, circular trading, front running, Harshad Mehta, Ketan Parekh", "what goes wrong"),
    ("Market crashes and bubbles: 1992, 2000, 2008, 2020 Covid, Adani–Hindenburg, global crashes", "history's lessons"),
    ("Behavioral finance: biases, herding, loss aversion, market sentiment and cycles", "the human side"),
    ("Trading psychology and discipline: journaling, process, handling losses", "the trader's mind"),
    ("Global markets: US (NYSE, Nasdaq, Fed), China, Japan, Europe, and how they affect India", "the world view"),
    ("Sector analysis in India: banks/NBFCs, IT, pharma, FMCG, auto, metals, energy, PSUs", "industry-specific metrics"),
    ("Event-driven trading: results season, budget, RBI policy, elections, index inclusion", "trading around events"),
]

SYSTEM = """You are building the knowledge base of a stock market teacher AI. The teacher must answer ANY question \
about markets correctly and in depth — from a beginner's "what is a share" to a quant's question on volatility skew \
dynamics or SEBI margin rules. You research one topic at a time with web search, check facts against primary \
sources (SEBI, NSE, BSE, RBI circulars and exchange documents, standard textbooks, academic papers), and write it \
down in the exact format requested.

Focus on Indian markets (NSE/BSE, SEBI, RBI, Indian tax), and cover global markets and theory fully where relevant. \
Never stop at a definition: explain how and why it works, the mechanics step by step, formulas with every symbol \
defined, worked numeric examples in rupees, real historical cases, edge cases, common misconceptions, and how \
professionals actually use it. Give every rule, limit and figure with the date it applies from, because rules \
change. When sources disagree or a rule may have changed recently, say so. When a topic comes from a book, teach \
its ideas in your own words from public sources, and never reproduce the book's text. Write in clear English."""

FORMAT = """Research this topic with web search (several searches; read primary sources where you can). \
Then reply in EXACTLY this format, with nothing before or after it:

<level>beginner | intermediate | advanced | expert</level>
<lesson>
Markdown lesson of 1,200 to 2,500 words with these sections: Core idea; How it works (mechanics, step by step); \
Formulas and numbers (with a worked example); India specifics (rules, circulars, dates); Real examples and history; \
Edge cases and common mistakes; How traders, investors and quants use it; Related concepts.
</lesson>
<qa difficulty="hard"><q>question</q><a>complete worked answer</a></qa>
(6 to 10 qa blocks. Mostly hard or expert: multi-step calculations, tricky edge cases, "why" questions, \
interview-grade questions, scenarios. difficulty is one of: medium, hard, expert.)
{subtopics}
<source url="https://...">title</source>
(one source tag per source you actually used)"""

SUBTOPICS = """<subtopic why="one line: why go deeper here">title of a deeper or more advanced subtopic</subtopic>
(3 to 6 subtopics that go deeper than this lesson, each narrow enough for one lesson, not already in the \
list of covered topics.)"""

say = logger("knowledge")  # also appended to <market dir>/logs/knowledge.log


def state(conn, text: str) -> None:
    set_meta(conn, "learner", json.dumps({"state": text, "at": datetime.now().isoformat(timespec="seconds")}))


def seed(conn) -> None:
    for title, why in ROOTS:
        add_topic(conn, title, depth=0, why=why)
    conn.commit()


def path_of(conn, topic_id: int) -> list[str]:
    titles = []
    while topic_id is not None:
        parent, title = conn.execute("SELECT parent_id, title FROM topics WHERE id = ?", (topic_id,)).fetchone()
        titles.append(title)
        topic_id = parent
    return titles[::-1]


def tag(text: str, name: str) -> str:
    m = re.search(rf"<{name}>(.*?)</{name}>", text, re.S)
    return m.group(1).strip() if m else ""


def parse(text: str) -> dict:
    return {
        "level": tag(text, "level").lower() or None,
        "lesson": tag(text, "lesson"),
        "qa": [(d or None, q.strip(), a.strip()) for d, q, a in re.findall(
            r'<qa(?:\s+difficulty="([^"]*)")?\s*>\s*<q>(.*?)</q>\s*<a>(.*?)</a>\s*</qa>', text, re.S)],
        "subtopics": [(t.strip(), w.strip()) for w, t in re.findall(
            r'<subtopic(?:\s+why="([^"]*)")?\s*>(.*?)</subtopic>', text, re.S) if t.strip()],
        "sources": [{"url": u, "title": t.strip()} for u, t in re.findall(
            r'<source\s+url="([^"]*)"\s*>(.*?)</source>', text, re.S)],
    }


_studying: set[int] = set()  # topics a learner is researching right now, so the other learner skips them
_studying_lock = threading.Lock()


def learn_one(conn, writers: list[str] | None = None, label: str = "") -> bool:
    """Research the next topic with these writers (default: all). False when nothing is queued."""
    with _studying_lock:
        busy = list(_studying) or [0]
        row = conn.execute(
            "SELECT id, title, why, depth FROM topics WHERE status = 'pending' "
            f"AND id NOT IN ({','.join('?' * len(busy))}) ORDER BY priority DESC, depth, id LIMIT 1", busy
        ).fetchone()
        if row is None:
            return False
        _studying.add(row[0])
    try:
        return _learn(conn, *row, writers, label)
    finally:
        with _studying_lock:
            _studying.discard(row[0])


def _learn(conn, topic_id: int, title: str, why: str | None, depth: int, writers: list[str] | None, label: str) -> bool:
    trail = path_of(conn, topic_id)
    # Siblings and own children: subtopics must not repeat them
    parent = conn.execute("SELECT parent_id FROM topics WHERE id = ?", (topic_id,)).fetchone()[0]
    nearby = [t for (t,) in conn.execute(
        "SELECT title FROM topics WHERE (parent_id IS ? OR parent_id = ?) AND id != ? LIMIT 80",
        (parent, topic_id, topic_id))]

    prompt = (
        f"Topic to learn: {title}\n"
        f"Path in the curriculum: Stock market > {' > '.join(trail)}\n"
        f"Why this topic: {why or 'asked by a student'}\n"
        f"Topics already covered or queued nearby: {'; '.join(dict.fromkeys(nearby)) or 'none'}\n\n"
        + FORMAT.format(subtopics=SUBTOPICS if depth < MAX_DEPTH else "(No subtopics: this branch is deep enough.)")
    )
    if not label:
        state(conn, f"Researching: {title}")
    say(f"{label}depth {depth}: {title}")
    try:
        text, used = write(prompt, SYSTEM, kind="lesson", web=True, cloud=False, writers=writers,
                           timeout=LESSON_TIMEOUT, what=title)
        got = parse(text)
        if len(got["lesson"]) < 400:
            raise ClaudeError("reply had no usable lesson")
    except UsageLimit:
        raise
    except ClaudeError as e:
        conn.execute("UPDATE topics SET attempts = attempts + 1 WHERE id = ?", (topic_id,))
        attempts = conn.execute("SELECT attempts FROM topics WHERE id = ?", (topic_id,)).fetchone()[0]
        if attempts >= MAX_ATTEMPTS:
            conn.execute("UPDATE topics SET status = 'failed' WHERE id = ?", (topic_id,))
        conn.commit()
        say(f"{label}  failed ({attempts}/{MAX_ATTEMPTS}): {e}")
        return True

    store(conn, topic_id, title, depth, got, used, label)
    return True


def store(conn, topic_id: int, title: str, depth: int, got: dict, used: str, label: str = "") -> None:
    """Save a parsed lesson with its Q&A (both searchable) and queue its subtopics; the topic is then learned."""
    conn.execute("INSERT OR REPLACE INTO lessons (topic_id, level, body, sources, model) VALUES (?,?,?,?,?)",
                 (topic_id, got["level"], got["lesson"], json.dumps(got["sources"]), used))
    conn.execute("DELETE FROM search WHERE ref = ?", (topic_id,))
    conn.execute("DELETE FROM qa WHERE topic_id = ?", (topic_id,))
    conn.execute("INSERT INTO search (title, body, kind, ref) VALUES (?,?,'lesson',?)", (title, got["lesson"], topic_id))
    for difficulty, q, a in got["qa"]:
        conn.execute("INSERT INTO qa (topic_id, question, answer, difficulty) VALUES (?,?,?,?)", (topic_id, q, a, difficulty))
        conn.execute("INSERT INTO search (title, body, kind, ref) VALUES (?,?,'qa',?)", (q, a, topic_id))
    added = sum(add_topic(conn, t, parent_id=topic_id, depth=depth + 1, why=w) is not None
                for t, w in got["subtopics"][:6])
    conn.execute("UPDATE topics SET status = 'done', learned_at = datetime('now') WHERE id = ?", (topic_id,))
    conn.commit()
    say(f"{label}  learned with {used}: {len(got['lesson'].split())} words, {len(got['qa'])} Q&A, {added} new subtopics")


def run(take_over: bool = False) -> None:
    """take_over: when another learner holds the lock, keep checking and continue once it stops."""
    told = None
    while True:
        try:
            if single_instance("knowledge"):  # only one learner at a time
                conn = connect()
                seed(conn)
                if added := syllabus.seed(conn):
                    say(f"syllabus: {added} topics queued, beginner to expert")
                break
            msg = "another learner is already running" + (" — will take over when it stops" if take_over else "")
        except Exception as e:  # E: disk not connected
            msg = f"not started — {type(e).__name__}: {e}"
        if msg != told:  # say it once, not every 10 minutes
            say(msg)
            told = msg
        if not take_over:
            return
        nap(10 * 60)
    say(f"started — writers {', '.join(ALL_WRITERS)}, knowledge in {MARKET_DIR / 'knowledge.db'}")
    learners = [(DRONA_WRITERS_2, "[account 2] ", lambda: agy_cli.available(2), lambda: agy_cli.account(2)),
                (CODEX_WRITERS, "[chatgpt] ", codex_cli.available, codex_cli.account)]
    for n in range(2, EXTRA_LEARNERS + 2):  # more lessons at once on each Google account (config.EXTRA_LEARNERS)
        learners += [(DRONA_WRITERS, f"[account 1 · {n}] ", lambda: True, lambda: agy_cli.account(1)),
                     (DRONA_WRITERS_2, f"[account 2 · {n}] ", lambda: agy_cli.available(2), lambda: agy_cli.account(2))]
    for writers, label, ready, who in learners:
        name = f"knowledge {label.strip()}"
        if not any(t.name == name and t.is_alive() for t in threading.enumerate()):  # restarted by Krishna
            threading.Thread(target=parallel_learner, args=(writers, label, ready, who), daemon=True,
                             name=name).start()
    while True:
        try:
            queued, kept = study_scores()  # learn from the latest scored calls first
            if queued or kept:
                say(f"from Chitragupta's scores: {queued} mistakes queued to study, {kept} checked lessons kept")
            # One batch of the other models' help requests (newest first), then one topic: Narad raises hundreds
            # an hour while it reads with the cloud keys, so answering all of them first would stop the studying.
            try:
                answered = help_models()
            except UsageLimit:
                raise
            except ClaudeError as e:  # a failed batch mustn't hold up this round's lesson
                say(f"help answers failed — {e}")
                answered = 0
            if answered:
                say(f"answered {answered} help requests")
            if not learn_one(conn) and not answered:
                state(conn, "Idle: every queued topic is learned")
                nap(10 * 60)
                continue
        except UsageLimit as e:
            until = datetime.now() + timedelta(seconds=LIMIT_WAIT)
            state(conn, f"Paused: Gemini (Antigravity) usage used up — trying again at {until:%H:%M}")
            say(f"usage limit ({e}) — waiting {LIMIT_WAIT // 60} min")
            nap(LIMIT_WAIT)
            continue
        except Exception as e:  # disk unplugged, DB locked…: keep the loop alive
            say(f"error — {type(e).__name__}: {e}")
            time.sleep(60)
            continue
        state(conn, "Between topics")
        time.sleep(PAUSE)


def parallel_learner(writers: list[str], label: str, ready, who) -> None:
    """Studies at the same time as the main loop, with these writers only, while ready() says their plan is
    set up (account 2's worker runs, Codex is signed in). Help requests and Chitragupta's scores stay with
    the main loop. who() names the account for the log."""
    conn, told = connect(), None
    while True:
        try:
            if not ready():
                if told != "off":
                    say(f"{label}not set up — checking every 5 min")
                    told = "off"
                nap(5 * 60)
                continue
            if told != "on":
                say(f"{label}studying in parallel as {who()}")
                told = "on"
            if not learn_one(conn, writers=writers, label=label):
                nap(10 * 60)
                continue
        except UsageLimit as e:
            say(f"{label}usage limit ({e}) — waiting {LIMIT_WAIT // 60} min")
            nap(LIMIT_WAIT)
            continue
        except Exception as e:  # disk unplugged, DB locked…: keep the loop alive
            say(f"{label}error — {type(e).__name__}: {e}")
            time.sleep(60)
            continue
        time.sleep(PAUSE)


def start() -> None:
    threading.Thread(target=run, args=(True,), daemon=True, name="knowledge").start()


if __name__ == "__main__":
    keep_awake()
    run()
