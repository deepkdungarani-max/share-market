"""Narad, the news reader: collects free Indian market news and reads every item with the local Ollama model.

Every 15 minutes it pulls the publisher RSS feeds below, NSE's live corporate announcements and Google News
for each tracked company into E:/candlecast-data/memory.db. Between pulls it reads unread items (tracked
companies and publisher news first, newest first) and writes a note per item: companies, kind of event,
good and bad points, sentiment and confidence. Mixed news (good and bad points together), an unsure
reading, or a kind of news Chitragupta's scores show Narad gets wrong becomes a help request for Drona.
The same story from a second outlet is skipped. Free feeds keep only recent items: what isn't collected in
time is gone for good. Only one Narad runs at a time (lock file); safe to stop and restart.

Usage: started by app/server.py; or on its own: python -m app.narad
"""
import html
import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import NamedTuple
from urllib.parse import quote_plus

import requests

from . import agy_cli, codex_cli, keys
from .claude_cli import ClaudeError, UsageLimit, rest_after
from .config import (GEMINI_MODELS, GROQ_MODELS, NARAD_OLLAMA, NEWS_PLANS, OLLAMA_MODEL, OLLAMA_URL, OPENROUTER_MODELS,
                     SYMBOLS)
from .market_db import connect as connect_market
from .memory_db import connect
from .system import keep_awake, logger, single_instance

EVERY = 15 * 60    # seconds between pulls of every source
HELP_BELOW = 0.6   # a reading less confident than this asks Drona for help
MAX_ATTEMPTS = 3   # an item the model fails to read this often is marked failed
DUP_SIMILAR = 0.6  # share of a headline's word weight found in one read already: the same story
GEMINI_BATCH = 25     # news items per Gemini request (one request per key at a time, keys in parallel)
GROQ_BATCH = 10       # news items per Groq request
GEMINI_PAUSE = 7      # seconds between rounds: under the requests-per-minute limit of each key
GEMINI_REST = 30 * 60  # seconds a key rests after its limit runs out (HTTP 429) or it can't reach Gemini
GEMINI_BUSY = 5 * 60   # seconds a key rests when every model is overloaded (HTTP 503) or too slow
PLAN_BATCH = 30        # news items per request to an AI plan (Gemini through agy, ChatGPT through Codex)
PLAN_PAUSE = 60        # seconds between one plan's requests while news waits: an AI plan is not an API
PLAN_IDLE = 5 * 60     # …and once the queue is (nearly) empty, so batches stay full and calls few
PLAN_TIMEOUT = 400     # seconds for one batch (about 40 s usually)
PLAN_SUMMARY = 500     # characters of each item's summary sent to a plan, to keep a batch small
PLAN_NAMES = {"agy": "Google AI Pro 1", "agy2": "Google AI Pro 2", "codex": "ChatGPT Pro"}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_LIST_EVERY = 6 * 3600  # seconds between refreshes of OpenRouter's list of free models
RELIABLE_MIN = 40    # scored calls on a kind of news before Narad's record on it counts
RELIABLE_HIT = 0.52  # Narad right less often than this on a kind of news: its notes on it go to Drona
STOP = set("a an and are as at be by for from has have in into is it its of on or over the to up with after amid vs".split())
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
IST = timezone(timedelta(hours=5, minutes=30))

# Checked on 28 Oct 2026. Moneycontrol's RSS stopped updating in April 2024, so it isn't here.
FEEDS = [
    ("ET Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("ET Stocks", "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    ("Mint Markets", "https://www.livemint.com/rss/markets"),
    ("Mint Companies", "https://www.livemint.com/rss/companies"),
    ("Business Standard Markets", "https://www.business-standard.com/rss/markets-106.rss"),
    ("Business Standard Companies", "https://www.business-standard.com/rss/companies-101.rss"),
    ("BusinessLine Markets", "https://www.thehindubusinessline.com/markets/feeder/default.rss"),
    ("BusinessLine Companies", "https://www.thehindubusinessline.com/companies/feeder/default.rss"),
    ("BusinessLine Economy", "https://www.thehindubusinessline.com/economy/feeder/default.rss"),
    ("ET Economy", "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"),
    ("ET Industry", "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms"),
    ("Mint Economy", "https://www.livemint.com/rss/economy"),
    ("Business Standard Economy", "https://www.business-standard.com/rss/economy-102.rss"),
    ("The Hindu Business", "https://www.thehindu.com/business/feeder/default.rss"),
    ("NDTV Profit", "https://feeds.feedburner.com/ndtvprofit-latest"),
    ("RBI press releases", "https://www.rbi.org.in/pressreleases_rss.xml"),
]
# Moneycontrol's feeds stopped in 2024; Financial Express's don't parse; Zee Business refuses (403).
# Every filing made to NSE today (results, orders, acquisitions, board meetings…): over 1,000 a day
NSE_FEED = "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}+when:2d&hl=en-IN&gl=IN&ceid=IN:en"

EVENTS = ["results", "guidance", "order_or_contract", "acquisition_or_merger", "dividend_or_buyback",
          "fundraise_or_ipo", "rating_or_target", "management_change", "legal_or_regulatory",
          "block_or_bulk_deal", "routine_filing", "macro_or_policy", "market_move", "other"]

SYSTEM = """You read Indian stock market news for a trading system and fill in a form about it.

about: "company" when it is about one or a few listed companies, "sector" for an industry, "market" for the \
whole market or the economy.
companies: names of the listed Indian companies it is about. Empty if none.
symbols: their NSE symbols (INFY, TCS, RELIANCE, HDFCBANK…), only when you are sure.
event: the kind of news.
positives: up to 3 facts stated in the news that are good for the share price (for market news: the market).
negatives: up to 3 facts stated in the news that are bad for the share price.
Only facts the news reports, never guesses about what might happen or general risks. Most news has one side \
only: leave the other list empty. List both only when the news itself reports both, like sales up but margins down.
sentiment: overall effect on the share price, from -1 (very bad) through 0 (neutral) to 1 (very good).
confidence: from 0 to 1, how sure you are about that sentiment.
Routine filings (meeting notices, trading window, certificates, newspaper ads) are neutral with no points."""

_FIELDS = {
    "about": {"type": "string", "enum": ["company", "sector", "market"]},
    "companies": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 8},
    "symbols": {"type": "array", "items": {"type": "string", "maxLength": 20}, "maxItems": 8},
    "event": {"type": "string", "enum": EVENTS},
    "positives": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 3},
    "negatives": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 3},
    "sentiment": {"type": "number"},
    "confidence": {"type": "number"},
}
# Ollama fills exactly this JSON shape (constrained decoding), so a small model can't drift from the form.
FORM = {"type": "object", "properties": _FIELDS, "required": list(_FIELDS)}
# The same form for Gemini, which reads many items per request: a list of forms, each with its item's id.
_GEMINI_FIELDS = {"id": {"type": "INTEGER"}, **{k: {"type": v["type"].upper(), **({"enum": v["enum"]} if "enum" in v else {}),
                                                     **({"items": {"type": "STRING"}} if "items" in v else {})}
                                                for k, v in _FIELDS.items()}}
GEMINI_FORMS = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": _GEMINI_FIELDS, "required": list(_GEMINI_FIELDS)}}
# A small model sometimes writes the next field into a list instead: "negatives", "Confidence: 0.8"
LEAKED = re.compile(rf"(overall )?({'|'.join(_FIELDS)})(\s*:.*)?", re.I)
# …or fills an empty side with a placeholder: "None", "There are no negative points mentioned in the news."
NOTHING = re.compile(r"(none|n/?a|nil)\.?|.*\bno (positive|negative|good|bad)\b.*|.*\bnot mentioned\b.*", re.I)
# It also pads one-sided news with guessed risks ("may lead to more competition"), so only points
# stated as facts decide whether news is mixed.
SPECULATIVE = re.compile(r"\b(might|may|could|potentially|possibly)\b", re.I)

say = logger("narad")  # also appended to <market dir>/logs/narad.log


class OllamaDown(Exception):
    """Ollama isn't running: keep collecting, read later."""


class ReaderDown(Exception):
    """A key couldn't get a reading (limit used up, overloaded, no internet): it rests a while."""

    def __init__(self, why: str, rest: int):
        super().__init__(why)
        self.rest = rest


_resting: dict[str, float] = {}  # Gemini or Groq key -> time it may be used again
_limits: dict[str, dict] = {}  # Groq key -> what is left of its limits, from its last reply


def _rest_for(r: requests.Response) -> int:
    """How long a key rests after HTTP 429: what the server asks (Retry-After), else GEMINI_REST."""
    try:
        return max(60, int(float(r.headers.get("retry-after", ""))))
    except ValueError:
        return GEMINI_REST


class Companies(NamedTuple):
    by_name: dict[str, str]  # normalized company name -> NSE symbol
    symbols: set[str]        # every symbol a note may carry
    tracked: dict[str, str]  # tracked symbol -> company name, searched on Google News


def norm(name: str) -> str:
    """Company name as lowercase words without a trailing Limited/Ltd: "Infosys Ltd." -> "infosys"."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    while words and words[-1] in ("limited", "ltd"):
        words.pop()
    return " ".join(words)


def symbol_for(name: str, co: "Companies") -> str | None:
    """NSE symbol for a company name: the exact listed name, else the only listed name that starts with it
    ("Cholamandalam Investment" -> CHOLAFIN; "Tata" or "HDFC" match several companies, so none)."""
    n = norm(name)
    if not n or n in co.by_name:
        return co.by_name.get(n)
    found = {s for full, s in co.by_name.items() if full.startswith(n + " ")}
    return found.pop() if len(found) == 1 else None


def companies() -> Companies:
    """Every company listed on NSE, from market.db (nse_listed is filled by app.download_yahoo)."""
    conn = connect_market()
    try:
        names = {s: n for s, n in conn.execute("SELECT symbol, name FROM nse_listed") if n}
    finally:
        conn.close()
    return Companies(
        by_name={norm(n): s for s, n in names.items()},
        symbols=set(names) | set(SYMBOLS),
        tracked={s: re.sub(r"\s+(limited|ltd\.?)$", "", names[s], flags=re.I) for s in SYMBOLS if s in names},
    )


# ---- collecting ----

def clean(text: str | None) -> str:
    """Plain text: HTML tags and entities removed, whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text or "")).split())


def when(text: str | None) -> str | None:
    """A feed timestamp as UTC in SQLite's format (2026-10-28 16:08:45), or None if unreadable."""
    text = (text or "").strip()
    try:
        dt = parsedate_to_datetime(text)  # RSS: Wed, 28 Oct 2026 21:38:45 +0530
    except (TypeError, ValueError):
        try:
            dt = datetime.strptime(text, "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)  # NSE: 28-Oct-2026 21:59:40
        except ValueError:
            return None
    if dt.tzinfo is None:  # RFC 822 "-0000" means UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def items(url: str) -> list[ET.Element]:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:  # a publisher left a bare "&" in a title ("Bombay Coated & Special Steels")
        root = ET.fromstring(re.sub(rb"&(?!#?\w+;)", b"&amp;", r.content))
    return root.findall(".//item")


def link(it: ET.Element) -> str:
    return (it.findtext("link") or "").strip()


def publisher(name: str, url: str) -> list[tuple]:
    return [(name, clean(it.findtext("title")), clean(it.findtext("description")), link(it),
             when(it.findtext("pubDate")), 1) for it in items(url)]


def nse(co: Companies) -> list[tuple]:
    rows = []
    for it in items(NSE_FEED):
        company = clean(it.findtext("title"))  # Raymond Realty Limited
        # "Raymond Realty Limited has informed the Exchange about Resignation of Statutory Auditor |SUBJECT: Resignation…"
        about, _, subject = clean(it.findtext("description")).partition("|SUBJECT:")
        tracked = co.by_name.get(norm(company)) in co.tracked
        rows.append(("NSE announcements", f"{company}: {(subject or about).strip()}", about.strip(), link(it),
                     when(it.findtext("pubDate")), 1 if tracked else 0))
    return rows


def google(company: str) -> list[tuple]:
    # A short all-caps name collides with common acronyms: plain "ITC" mostly finds GST's input tax credit
    q = f'"{company}" share' if company.isupper() and len(company) <= 4 else f'"{company}"'
    rows = []
    for it in items(GOOGLE_NEWS.format(q=quote_plus(q))):
        source = clean(it.findtext("source")) or "unknown"
        title = clean(it.findtext("title")).removesuffix(f" - {source}")  # Google appends " - Publisher"
        # Google's description only links back to the article, so there is no summary
        rows.append((f"Google News: {source}", title, "", link(it), when(it.findtext("pubDate")), 1))
    return rows


def save(conn, rows: list[tuple]) -> int:
    """Store (source, title, summary, url, published_at, priority) rows; returns how many were new."""
    before = conn.total_changes
    conn.executemany("INSERT OR IGNORE INTO news (source, title, summary, url, published_at, priority) "
                     "VALUES (?,?,?,?,?,?)", [r for r in rows if r[1] and r[3]])
    conn.commit()
    return conn.total_changes - before


def collect(conn, co: Companies) -> None:
    """Pull every source once and store what's new. One source failing doesn't stop the others."""
    jobs = [(name, publisher, name, url) for name, url in FEEDS]
    jobs.append(("NSE announcements", nse, co))
    jobs += [("Google News", google, company) for company in co.tracked.values()]
    new, failed = {}, []
    for label, fetch, *args in jobs:
        try:
            new[label] = new.get(label, 0) + save(conn, fetch(*args))
        except Exception as e:  # feed down, bad XML, blocked…
            failed.append(f"{label} ({type(e).__name__})")
        if fetch is google:
            time.sleep(1)  # Google blocks rapid-fire searches
    say(f"pulled {sum(new.values())} new: " + ", ".join(f"{k} {v}" for k, v in new.items())
        + (f" — failed: {', '.join(failed)}" if failed else ""))


# ---- reading ----

def read(source: str, title: str, summary: str) -> dict:
    """The form the model filled for one news item."""
    text = f"Source: {source}\nTitle: {title}\n" + (f"Summary: {summary}\n" if summary else "")
    try:
        # A filled form is ~150 tokens. The cap stops a small model that loops inside a string, which
        # otherwise runs on for 10+ minutes on a CPU.
        r = requests.post(f"{OLLAMA_URL}/api/chat", timeout=300, json={
            "model": OLLAMA_MODEL, "stream": False, "format": FORM, "options": {"temperature": 0, "num_predict": 400},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        })
    except requests.ConnectionError as e:
        raise OllamaDown(f"{OLLAMA_URL}: {type(e).__name__}")
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def tidy(form: dict, co: Companies) -> dict:
    """The form checked: only symbols that exist on NSE, numbers in range, short point lists."""
    def strings(key: str, n: int) -> list[str]:
        return [s.strip()[:200] for s in form.get(key) or []
                if isinstance(s, str) and s.strip() and not LEAKED.fullmatch(s.strip()) and not NOTHING.fullmatch(s.strip())][:n]

    def number(key: str, lo: float, hi: float) -> float:
        try:
            return min(max(float(form.get(key)), lo), hi)
        except (TypeError, ValueError):
            return 0.0

    names = strings("companies", 8)
    said = {s.upper().removesuffix(".NS").removesuffix(".BO") for s in strings("symbols", 8)}
    symbols = sorted({s for s in said if s in co.symbols} | {s for s in (symbol_for(n, co) for n in names) if s})
    confidence = number("confidence", 0, 100)
    return {
        "about": form.get("about") if form.get("about") in ("company", "sector", "market")
        else "company" if symbols else "market",
        "companies": names,
        "symbols": symbols,
        "event": form.get("event") if form.get("event") in EVENTS else "other",
        "positives": strings("positives", 5),
        "negatives": strings("negatives", 5),
        "sentiment": number("sentiment", -1, 1),
        "confidence": confidence / 100 if confidence > 1 else confidence,  # some replies give a percentage
    }


def question(title: str, summary: str, note: dict) -> str:
    """What Drona is asked about a news item Narad couldn't settle."""
    target = " ".join(note["symbols"]) or f"the {note['about']}"
    return "\n".join(line for line in (
        title,
        summary,
        f"Good points: {'; '.join(note['positives']) or 'none'}",
        f"Bad points: {'; '.join(note['negatives']) or 'none'}",
        f"Narad's reading: sentiment {note['sentiment']:+.1f}, confidence {note['confidence']:.2f}",
        f"Is this news good or bad for {target}, and how strongly, from -1 to +1?",
    ) if line)


def words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in STOP}


def duplicate_of(conn, news_id: int, title: str, published: str) -> int | None:
    """An item read already that tells the same story (another outlet's headline within a day), if any.

    Words count by how rare they are in that day's headlines, so company names and exact numbers decide it,
    not templates like "Q2 results: net profit rises". NSE filings aren't compared: their titles are templates.
    """
    mine = words(title)
    if len(mine) < 4:
        return None
    rows = conn.execute("SELECT id, title, status FROM news WHERE source != 'NSE announcements' AND "
                        "COALESCE(published_at, fetched_at) BETWEEN datetime(?, '-1 day') AND datetime(?, '+1 day')",
                        (published, published)).fetchall()
    corpus = [(i, words(t), status) for i, t, status in rows]
    seen_in = Counter(w for _, ws, _ in corpus for w in ws)
    rarity = {w: math.log(len(corpus) / n) for w, n in seen_in.items()}
    weight = lambda ws: sum(rarity.get(w, 0.0) for w in ws)
    for other, ws, status in corpus:
        if status == "read" and other != news_id and len(ws) >= 4 and len(ws & mine) >= 3:
            if weight(ws & mine) >= DUP_SIMILAR * min(weight(ws), weight(mine)) > 0:
                return other
    return None


def unreliable(conn, event: str) -> bool:
    """True once Chitragupta's scores show Narad is mostly wrong on this kind of news; its own confidence
    can't tell, because a small model rates itself high either way."""
    # Joined on the numeric id, so news_notes' primary key is used (a built 'news:' || id string can't be)
    n, right = conn.execute("SELECT COUNT(*), AVG(s.hit) FROM scores s JOIN news_notes n "
                            "ON n.news_id = CAST(substr(s.ref, 6) AS INTEGER) AND s.ref LIKE 'news:%' "
                            "WHERE s.model = 'narad' AND s.hit IS NOT NULL AND n.event = ?", (event,)).fetchone()
    return n >= RELIABLE_MIN and right < RELIABLE_HIT


def read_many(items: list[tuple[int, str, str, str]], key: str) -> tuple[dict[int, dict], str]:
    """Gemini's forms for several news items (id, source, title, summary) in one request with one key:
    ({news id: form}, model that read them). Each model is tried in turn while the earlier ones are busy."""
    text = "\n\n".join(f"[id {i}]\nSource: {source}\nTitle: {title}" + (f"\nSummary: {summary}" if summary else "")
                       for i, source, title, summary in items)
    body = {"systemInstruction": {"parts": [{"text": SYSTEM + "\n\nFill one form for every news item below, with "
                                                       "that item's id."}]},
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": GEMINI_FORMS}}
    busy = []
    for model in GEMINI_MODELS:
        try:
            r = requests.post(GEMINI_URL.format(model=model), timeout=180, json=body,
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        except requests.Timeout:
            busy.append(f"{model} too slow")
            continue
        except requests.RequestException as e:
            raise ReaderDown(type(e).__name__, GEMINI_REST)
        if r.status_code in (500, 503):
            busy.append(f"{model} overloaded")
            continue
        if r.status_code != 200:  # 429: this key's limit is used up; 400/403: a bad key or request
            raise ReaderDown(f"HTTP {r.status_code}: {' '.join(r.text.split())[:160]}",
                             _rest_for(r) if r.status_code == 429 else GEMINI_REST)
        try:
            forms = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, ValueError) as e:
            busy.append(f"{model} unreadable reply ({type(e).__name__})")
            continue
        return {int(f["id"]): f for f in forms if isinstance(f, dict) and str(f.get("id", "")).isdigit()}, f"gemini:{model}"
    raise ReaderDown("; ".join(busy), GEMINI_BUSY)


def forms_prompt(items: list[tuple[int, str, str, str]], summary_chars: int | None = None) -> tuple[str, str]:
    """(instructions, items) asking for a JSON object {"forms": [...]}, one form per item with its id: for the
    readers that have no response schema (Groq's JSON mode, the AI plans)."""
    text = "\n\n".join(f"[id {i}]\nSource: {source}\nTitle: {title}"
                       + (f"\nSummary: {summary[:summary_chars] if summary_chars else summary}" if summary else "")
                       for i, source, title, summary in items)
    shape = ", ".join(f'"{k}"' for k in _GEMINI_FIELDS)
    system = (SYSTEM + f"\n\nevent is one of: {', '.join(EVENTS)}.\nReply with only a JSON object "
              f'{{"forms": [...]}} holding one form for every news item below, each with the keys {shape}.')
    return system, text


def _forms(forms: list) -> dict[int, dict]:
    return {int(f["id"]): f for f in forms if isinstance(f, dict) and str(f.get("id", "")).isdigit()}


def read_many_plan(items: list[tuple[int, str, str, str]], writer: str) -> tuple[dict[int, dict], str]:
    """The same as read_many, with an AI plan through its CLI: agy:<model> (Google AI Pro account 1), agy2:<model>
    (account 2) or codex:<model>@<effort> (ChatGPT). A plan out of usage rests until it resets."""
    kind, _, model = writer.partition(":")
    system, text = forms_prompt(items, PLAN_SUMMARY)
    try:
        if kind == "codex":
            if not codex_cli.available():
                raise ReaderDown("ChatGPT isn't signed in (tools/codex-login.ps1)", GEMINI_REST)
            model, _, effort = model.partition("@")
            reply, _ = codex_cli.ask(text, system, model=model, effort=effort or None, web=False, timeout=PLAN_TIMEOUT)
        else:
            account = 2 if kind == "agy2" else 1
            if account == 2 and agy_cli.parallel(2) < 2:
                # A worker that runs one job at a time would make news wait behind Drona's 10-minute lessons
                raise ReaderDown("account 2's worker runs one job at a time: restart its task to load the new "
                                 "worker (see the Krishna page)", GEMINI_REST)
            reply, _ = agy_cli.ask(text, system, model=model, timeout=PLAN_TIMEOUT, account_no=account)
    except UsageLimit as e:
        raise ReaderDown(str(e)[:200], rest_after(e, GEMINI_REST))
    except ClaudeError as e:
        raise ReaderDown(str(e)[:200], GEMINI_BUSY)
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        return _forms(json.loads(m.group(0))["forms"]), writer
    except (AttributeError, KeyError, ValueError, TypeError) as e:
        raise ReaderDown(f"unreadable reply ({type(e).__name__}): {reply[:120]}", GEMINI_BUSY)


_free_models: dict = {"at": 0.0, "ids": [], "json": set()}  # json: the free models that take response_format


def openrouter_models() -> list[str]:
    """OpenRouter's free models to read with, best first: config.OPENROUTER_MODELS that are still free, then any
    other free model with a long enough context that can answer in JSON. The free list changes every few weeks,
    so it is fetched again every OPENROUTER_LIST_EVERY."""
    if time.time() - _free_models["at"] > OPENROUTER_LIST_EVERY:
        try:
            listed = requests.get(OPENROUTER_MODELS_URL, timeout=30).json()["data"]
        except (requests.RequestException, ValueError, KeyError):
            listed = None
        if listed is not None:
            free = {m["id"]: m for m in listed if m["id"].endswith(":free")}
            others = [i for i, m in free.items() if i not in OPENROUTER_MODELS
                      and "response_format" in (m.get("supported_parameters") or [])
                      and (m.get("context_length") or 0) >= 32_000 and "safety" not in i]
            _free_models.update(at=time.time(), ids=[m for m in OPENROUTER_MODELS if m in free] + others,
                                json={i for i, m in free.items() if "response_format" in (m.get("supported_parameters") or [])})
    return _free_models["ids"] or list(OPENROUTER_MODELS)


_openrouter_daily: dict[str, tuple[float, dict | None]] = {}  # key -> (fetched at, today's free-model requests)


def openrouter_daily(key: str) -> dict | None:
    """Today's free-model requests of an OpenRouter key, as OpenRouter counts them ({used, limit, remaining}; the
    day is a UTC day): 50 a day until the account has bought $10 of credit, 1,000 after. Asked at most once a
    minute; the call costs nothing."""
    at, info = _openrouter_daily.get(key, (0.0, None))
    if time.time() - at > 60:
        try:
            info = requests.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"},
                                timeout=10).json()["data"].get("free_model_daily_requests")
        except (requests.RequestException, ValueError, KeyError, AttributeError):
            pass  # keep the last count
        _openrouter_daily[key] = (time.time(), info)
    return info


def _until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    return int((now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - now).total_seconds()) + 60


def read_many_openrouter(items: list[tuple[int, str, str, str]], key: str) -> tuple[dict[int, dict], str]:
    """The same as read_many, with OpenRouter's free models (OpenAI-style API). An account that has once bought
    $10 of credit gets 1,000 free-model requests a day (20 a minute); once the day's are used up the key rests
    until 00:00 UTC (05:30 IST). Each model is tried in turn while the earlier ones are busy."""
    system, text = forms_prompt(items, PLAN_SUMMARY)
    busy = []
    for model in openrouter_models()[:4]:
        try:
            r = requests.post(OPENROUTER_URL, timeout=180, headers={"Authorization": f"Bearer {key}", "X-Title": "CandleCast"},
                              json={"model": model, "temperature": 0, "max_tokens": 8192,
                                    **({"response_format": {"type": "json_object"}} if model in _free_models["json"] else {}),
                                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]})
        except requests.Timeout:
            busy.append(f"{model} too slow")
            continue
        except requests.RequestException as e:
            raise ReaderDown(type(e).__name__, GEMINI_BUSY)
        if r.status_code == 429:
            message = " ".join(r.text.split())[:160]
            if "per-day" in message or "per day" in message:  # the account's free requests for today are used up
                raise ReaderDown(f"HTTP 429: {message}", _until_utc_midnight())
            busy.append(f"{model} busy (429)")  # per-minute limit, or the free model's own provider is full
            continue
        if r.status_code in (401, 402, 403):
            raise ReaderDown(f"HTTP {r.status_code}: {' '.join(r.text.split())[:160]}", GEMINI_REST)
        if r.status_code != 200:
            busy.append(f"{model} HTTP {r.status_code}")
            continue
        try:
            body = r.json()
            content = body["choices"][0]["message"]["content"] or ""
            m = re.search(r"\{.*\}", content, re.S)
            return _forms(json.loads(m.group(0))["forms"]), f"openrouter:{model}"
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            busy.append(f"{model} unreadable reply ({type(e).__name__})")  # also an upstream error in a 200 body
    raise ReaderDown("; ".join(busy) or "no free model", GEMINI_BUSY)


def read_many_groq(items: list[tuple[int, str, str, str]], key: str) -> tuple[dict[int, dict], str]:
    """The same as read_many, with Groq (OpenAI-style API, JSON mode instead of a schema)."""
    system, text = forms_prompt(items)
    busy, limited = [], []
    for model in GROQ_MODELS:
        try:
            r = requests.post(GROQ_URL, timeout=120, headers={"Authorization": f"Bearer {key}"}, json={
                "model": model, "temperature": 0, "response_format": {"type": "json_object"},
                "reasoning_effort": "low", "max_completion_tokens": 8192,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]})
        except requests.Timeout:
            busy.append(f"{model} too slow")
            continue
        except requests.RequestException as e:
            raise ReaderDown(type(e).__name__, GEMINI_REST)
        h = r.headers  # Groq reports what is left of the key's limits on every reply
        if "x-ratelimit-remaining-requests" in h:
            _limits[key] = {"requests_left": h.get("x-ratelimit-remaining-requests"),
                            "requests_limit": h.get("x-ratelimit-limit-requests"),
                            "requests_reset": h.get("x-ratelimit-reset-requests"),
                            "tokens_left": h.get("x-ratelimit-remaining-tokens"),
                            "tokens_limit": h.get("x-ratelimit-limit-tokens")}
        if r.status_code == 429:  # this model's limit (e.g. tokens per day) is used up: the next model reads
            limited.append(_rest_for(r))
            busy.append(f"{model} limit used up")
            continue
        if r.status_code >= 500:
            busy.append(f"{model} overloaded")
            continue
        if r.status_code != 200:
            raise ReaderDown(f"HTTP {r.status_code}: {' '.join(r.text.split())[:160]}", GEMINI_REST)
        try:
            forms = json.loads(r.json()["choices"][0]["message"]["content"])["forms"]
        except (KeyError, IndexError, ValueError, TypeError) as e:
            busy.append(f"{model} unreadable reply ({type(e).__name__})")
            continue
        return {int(f["id"]): f for f in forms if isinstance(f, dict) and str(f.get("id", "")).isdigit()}, f"groq:{model}"
    if len(limited) == len(GROQ_MODELS):  # every model's limit is used up: the key rests
        raise ReaderDown("HTTP 429: " + "; ".join(busy), min(limited))
    raise ReaderDown("; ".join(busy), GEMINI_BUSY)


def cloud_write(prompt: str, system: str) -> tuple[str, str]:
    """A free-text reply from the first cloud key that isn't resting: (text, "gemini:model" / "groq:model" /
    "openrouter:model").

    For Drona's help answers while Claude's usage limit is used up. Not for lessons: those need web research,
    and Groq's browser search spent ~100k tokens (half a key's daily limit) on one thin lesson, while Google
    Search on Gemini isn't in its free tier and OpenRouter's web search is billed even on free models.
    OpenRouter keys go last: their free requests (50 a day before $10 of credit) are shared with Narad. The AI
    plans in READERS are not keys and are skipped. A key whose limits are all used up rests, shared with
    Narad's readers. ReaderDown when no key could write."""
    tried = []
    order = {"gemini": 0, "groq": 1, "openrouter": 2}
    for reader in sorted((r for r in list(READERS.values()) if r["provider"] in order),
                         key=lambda r: order[r["provider"]]):
        key = reader["key"]
        if reader.get("paused") or _resting.get(key, 0) > time.time():
            continue
        try:
            if reader["provider"] == "gemini":
                return _gemini_write(prompt, system, key)
            if reader["provider"] == "openrouter":
                return _openrouter_write(prompt, system, key)
            return _groq_write(prompt, system, key)
        except ReaderDown as e:
            if "HTTP 429" in str(e):  # only a used-up limit rests the key; Narad keeps it for anything else
                _resting[key] = time.time() + e.rest
            tried.append(f"{reader['name']}: {e}")
    raise ReaderDown("; ".join(tried) or "every cloud key is resting", GEMINI_BUSY)


def _openrouter_write(prompt: str, system: str, key: str) -> tuple[str, str]:
    """Each free model in turn, as in read_many_openrouter; the day's free requests used up rests the key until
    00:00 UTC."""
    busy = []
    for model in openrouter_models()[:4]:
        try:
            r = requests.post(OPENROUTER_URL, timeout=300, headers={"Authorization": f"Bearer {key}", "X-Title": "CandleCast"},
                              json={"model": model, "temperature": 0.3, "max_tokens": 12000,
                                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        except requests.Timeout:
            busy.append(f"{model} too slow")
            continue
        except requests.RequestException as e:
            raise ReaderDown(type(e).__name__, GEMINI_BUSY)
        if r.status_code == 429:
            message = " ".join(r.text.split())[:160]
            if "per-day" in message or "per day" in message:
                raise ReaderDown(f"HTTP 429: {message}", _until_utc_midnight())
            busy.append(f"{model} busy (429)")
            continue
        if r.status_code in (401, 402, 403):
            raise ReaderDown(f"HTTP {r.status_code}: {' '.join(r.text.split())[:160]}", GEMINI_REST)
        if r.status_code != 200:
            busy.append(f"{model} HTTP {r.status_code}")
            continue
        try:
            text = r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError, TypeError) as e:
            busy.append(f"{model} unreadable reply ({type(e).__name__})")  # also an upstream error in a 200 body
            continue
        if text.strip():
            return text, f"openrouter:{model}"
        busy.append(f"{model} empty reply")
    raise ReaderDown("; ".join(busy) or "no free model", GEMINI_BUSY)


def _gemini_write(prompt: str, system: str, key: str) -> tuple[str, str]:
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 16384}}
    busy = []
    for model in GEMINI_MODELS:
        try:
            r = requests.post(GEMINI_URL.format(model=model), timeout=300, json=body,
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        except requests.Timeout:
            busy.append(f"{model} too slow")
            continue
        except requests.RequestException as e:
            raise ReaderDown(type(e).__name__, GEMINI_BUSY)
        if r.status_code in (500, 503):
            busy.append(f"{model} overloaded")
            continue
        if r.status_code != 200:
            raise ReaderDown(f"HTTP {r.status_code}: {' '.join(r.text.split())[:160]}",
                             _rest_for(r) if r.status_code == 429 else GEMINI_REST)
        try:
            text = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, ValueError) as e:
            busy.append(f"{model} unreadable reply ({type(e).__name__})")
            continue
        return text, f"gemini:{model}"
    raise ReaderDown("; ".join(busy), GEMINI_BUSY)


def _groq_write(prompt: str, system: str, key: str) -> tuple[str, str]:
    """Each model in turn: one whose own limit (e.g. tokens per day) is used up hands over to the next."""
    busy, limited = [], []
    for model in GROQ_MODELS:
        try:
            r = requests.post(GROQ_URL, timeout=300, headers={"Authorization": f"Bearer {key}"}, json={
                "model": model, "temperature": 0.3, "reasoning_effort": "low", "max_completion_tokens": 12000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]})
        except requests.Timeout:
            busy.append(f"{model} too slow")
            continue
        except requests.RequestException as e:
            raise ReaderDown(type(e).__name__, GEMINI_BUSY)
        if r.status_code == 429:
            limited.append(_rest_for(r))
            busy.append(f"{model} limit used up")
            continue
        if r.status_code >= 500:
            busy.append(f"{model} overloaded")
            continue
        if r.status_code != 200:
            raise ReaderDown(f"HTTP {r.status_code}: {' '.join(r.text.split())[:160]}", GEMINI_REST)
        try:
            return r.json()["choices"][0]["message"]["content"] or "", f"groq:{model}"
        except (KeyError, IndexError, ValueError) as e:
            busy.append(f"{model} unreadable reply ({type(e).__name__})")
    if len(limited) == len(GROQ_MODELS):  # every model's limit is used up: the key rests
        raise ReaderDown("HTTP 429: " + "; ".join(busy), min(limited))
    raise ReaderDown("; ".join(busy), GEMINI_BUSY)


# How each provider reads: (reader, items per request). Groq gets smaller batches: its free tier counts
# tokens per minute, and gpt-oss spends some on thinking first.
READ_WITH = {"gemini": (read_many, GEMINI_BATCH), "groq": (read_many_groq, GROQ_BATCH),
             "openrouter": (read_many_openrouter, PLAN_BATCH),
             "agy": (read_many_plan, PLAN_BATCH), "agy2": (read_many_plan, PLAN_BATCH),
             "codex": (read_many_plan, PLAN_BATCH)}
PLANS = ("agy", "agy2", "codex")  # providers that are AI plans (config.NEWS_PLANS), not keys

# Every cloud key Narad reads with, all used at the same time (key id -> {name, provider, key, added, fn, batch}).
# Keys are added and removed from the website while the server runs: see add_key() and remove_key().
READERS: dict[str, dict] = {}
_stats: dict[str, dict] = {}  # key id -> what it has done since the server started
_co: "Companies | None" = None  # set by run(), so a key added later starts reading at once


def _use(entry: dict) -> dict:
    """Put a stored key or an AI plan to work; its worker starts now when Narad is running, otherwise in run()."""
    fn, batch = READ_WITH[entry["provider"]]
    plan = entry["provider"] in PLANS
    reader = {**entry, "fn": fn, "batch": batch, "pause": PLAN_PAUSE if plan else GEMINI_PAUSE,
              "idle": PLAN_IDLE if plan else GEMINI_PAUSE}
    READERS[entry["id"]] = reader
    _stats.setdefault(entry["id"], {"requests": 0, "items": 0, "failures": 0, "model": None, "last_ok": None,
                                    "last_error": None})
    if _co is not None:
        _start_worker(entry["id"], reader)
    return reader


def _start_worker(kid: str, reader: dict) -> None:
    name = f"narad {reader['name']}"
    if any(t.name == name and t.is_alive() for t in threading.enumerate()):
        return  # already reading (run() restarted by Krishna after its own thread stopped)
    threading.Thread(target=key_worker, args=(kid, reader, _co), daemon=True, name=name).start()


def add_key(provider: str, key: str, name: str = "") -> dict:
    """Check, store and start reading with a new key. ValueError says why it can't be added."""
    reader = _use(keys.add(provider, key, name))
    say(f"{reader['name']} added — reading with it now")
    return _public(reader["id"], reader, time.time())


def pause_key(kid: str, paused: bool) -> bool:
    """Stop (or let again) a key or AI plan reading without removing it. Its worker idles while it is paused."""
    reader = READERS.get(kid)
    if reader is None:
        return False
    if reader["provider"] in PLANS:
        keys.set_plan_paused(kid, paused)
    elif not keys.set_paused(kid, paused):
        return False
    reader["paused"] = paused
    say(f"{reader['name']} {'paused' if paused else 'resumed'}")
    return True


def remove_key(kid: str) -> bool:
    """Stop reading with a key and forget it. Its worker finishes the batch in hand and stops. The AI plans
    can't be removed here (config.NEWS_PLANS); pause them instead."""
    if kid.startswith("plan:"):
        return False
    reader = READERS.pop(kid, None)
    removed = keys.remove(kid)
    if reader:
        say(f"{reader['name']} removed")
    return removed or reader is not None


for _entry in keys.load():
    _use(_entry)
_paused_plans = keys.paused_plans()
for _writer in NEWS_PLANS:
    _kind, _, _model = _writer.partition(":")
    _use({"id": f"plan:{_writer}", "provider": _kind, "key": _writer, "added": None,
          "name": f"{PLAN_NAMES.get(_kind, _kind)} · {_model.replace('@', ' ')}",
          "paused": f"plan:{_writer}" in _paused_plans})


_claimed: set[int] = set()  # items a reader is working on right now, so no other reader takes them
_claim_lock = threading.Lock()


def pick(conn, n: int) -> list[tuple]:
    """Claim the next n unread items (tracked companies and publisher news first, newest first). Repeats of
    a story read already are marked duplicate on the way and skipped. Hand them back with release()."""
    with _claim_lock:
        picked = _pick(conn, n)
        _claimed.update(row[0] for row in picked)
    return picked


def release(items: list[tuple]) -> None:
    with _claim_lock:
        _claimed.difference_update(row[0] for row in items)


def _pick(conn, n: int) -> list[tuple]:
    picked = []
    while len(picked) < n:
        taken = [row[0] for row in picked] + list(_claimed) or [0]
        row = conn.execute("SELECT id, source, title, summary, COALESCE(published_at, fetched_at) FROM news "
                           f"WHERE status = 'new' AND id NOT IN ({','.join('?' * len(taken))}) "
                           "ORDER BY priority DESC, published_at DESC LIMIT 1", taken).fetchone()
        if row is None:
            break
        news_id, source, title, _, published = row
        if source != "NSE announcements" and (same := duplicate_of(conn, news_id, title, published)):
            conn.execute("UPDATE news SET status = 'duplicate' WHERE id = ?", (news_id,))
            conn.commit()
            say(f"#{news_id} same story as #{same}, not read again · {title[:80]}")
            continue
        picked.append(row)
    return picked


def failed(conn, news_id: int, why: str) -> None:
    conn.execute("UPDATE news SET attempts = attempts + 1, "
                 "status = CASE WHEN attempts + 1 >= ? THEN 'failed' ELSE status END WHERE id = ?",
                 (MAX_ATTEMPTS, news_id))
    conn.commit()
    say(f"#{news_id} not read — {why}")


def save_note(conn, co: Companies, news_id: int, title: str, summary: str, form: dict, model: str) -> None:
    """Narad's note from a filled form, plus a help request for Drona when the news needs one."""
    note = tidy(form, co)

    def firm(points: list[str]) -> bool:
        return any(not SPECULATIVE.search(p) for p in points)

    mixed = firm(note["positives"]) and firm(note["negatives"])
    help_reason = ("mixed" if mixed else "unsure" if note["confidence"] < HELP_BELOW
                   else "unreliable" if unreliable(conn, note["event"]) else None)
    if note["about"] == "company" and not note["symbols"]:
        help_reason = None  # an unlisted company: no share price for Drona to judge
    with conn:
        conn.execute("INSERT OR REPLACE INTO news_notes (news_id, about, companies, symbols, event, positives, "
                     "negatives, sentiment, confidence, model) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (news_id, note["about"], json.dumps(note["companies"]), json.dumps(note["symbols"]),
                      note["event"], json.dumps(note["positives"]), json.dumps(note["negatives"]),
                      note["sentiment"], note["confidence"], model))
        if help_reason:
            conn.execute("INSERT OR IGNORE INTO help_requests (asker, ref, question, reason) VALUES ('narad', ?, ?, ?)",
                         (f"news:{news_id}", question(title, summary, note), help_reason))
        conn.execute("UPDATE news SET status = 'read' WHERE id = ?", (news_id,))
    say(f"#{news_id} {note['event']} {note['sentiment']:+.1f} ({note['confidence']:.2f}) "
        f"{' '.join(note['symbols']) or note['about']}{f' — help: {help_reason}' if help_reason else ''} · {title[:80]}")


def key_worker(kid: str, reader: dict, co: Companies) -> None:
    """One cloud key reading on its own, batch after batch, so a fast key never waits for a slow one.
    When its limit runs out it rests for as long as the server asks, then carries on. Stops once the key
    is removed (or removed and added again: the new entry gets its own worker)."""
    name, fn, key, batch = reader["name"], reader["fn"], reader["key"], reader["batch"]
    conn = connect()
    while READERS.get(kid) is reader:
        if reader.get("paused"):
            time.sleep(10)
            continue
        wait = _resting.get(key, 0) - time.time()
        if wait > 0:
            time.sleep(min(60, wait))
            continue
        items = []
        try:
            items = pick(conn, batch)
            if not items:
                time.sleep(max(60, reader["idle"]))  # everything is read: look again in a while
                continue
            stats = _stats[kid]
            stats["requests"] += 1
            try:
                forms, model = fn([(i, s, t, m or "") for i, s, t, m, _ in items], key)
            except ReaderDown as e:
                _resting[key] = time.time() + e.rest
                stats["failures"] += 1
                stats["last_error"] = f"{datetime.now():%H:%M} {e}"[:200]
                say(f"{name} rests {max(1, e.rest // 60)} min — {e}")
                continue  # its items go back to the queue for the other readers
            stats.update(model=model, last_ok=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         items=stats["items"] + len(forms))
            for news_id, _, title, summary, _ in items:
                if news_id in forms:
                    save_note(conn, co, news_id, title, summary or "", forms[news_id], model)
                else:
                    failed(conn, news_id, f"{name} left it out of its reply")
        except Exception as e:  # DB locked, disk unplugged…: keep the worker alive
            say(f"{name} error — {type(e).__name__}: {e}")
            time.sleep(30)
        finally:
            release(items)
        # Stay under the key's requests-per-minute limit; a plan waits longer, more so once the queue runs dry
        time.sleep(reader["pause"] if len(items) >= batch else reader["idle"])
    conn.close()


def _public(kid: str, reader: dict, now: float) -> dict:
    """A key as the website sees it: never the key itself, only its last 4 characters (an AI plan has no key)."""
    rest = _resting.get(reader["key"], 0) - now
    hint = "AI plan" if reader["provider"] in PLANS else f"…{reader['key'][-4:]}"
    limits = _limits.get(reader["key"])
    if reader["provider"] == "openrouter" and (daily := openrouter_daily(reader["key"])):
        limits = {"requests_left": str(daily.get("remaining")), "requests_limit": str(daily.get("limit")),
                  "requests_reset": "00:00 UTC (05:30 IST)", "tokens_left": None, "tokens_limit": None}
    return {"id": kid, "name": reader["name"], "provider": reader["provider"], "hint": hint,
            "added": reader["added"], "batch": reader["batch"],
            "state": "paused" if reader.get("paused") else "resting" if rest > 0 else "reading",
            "rests_for": max(0, int(rest)), "limits": limits, **_stats[kid]}


def readers_view() -> dict:
    """For the website: every reader Narad uses (each cloud key, and the local model), what it is doing
    and what it has done since the server started, plus notes per model in the last 24 hours."""
    now = time.time()
    keys = [_public(kid, reader, now) for kid, reader in list(READERS.items())]
    conn = connect()
    try:
        per_model = conn.execute("SELECT model, COUNT(*) FROM news_notes WHERE created_at >= datetime('now', '-1 day') "
                                 "GROUP BY model ORDER BY 2 DESC").fetchall()
    finally:
        conn.close()
    return {"keys": keys, "ollama": {"model": OLLAMA_MODEL, "state": "off" if not ollama_reads()
                                     else "standby" if READERS and not all_resting() else "reading"},
            "per_model": [{"model": m, "notes": n} for m, n in per_model]}


def all_resting() -> bool:
    return all(r.get("paused") or _resting.get(r["key"], 0) > time.time() for r in list(READERS.values()))


def ollama_reads() -> bool:
    """Whether the local model may read news: only with no other reader at all, unless config.NARAD_OLLAMA."""
    return NARAD_OLLAMA or not READERS


def read_one(conn, co: Companies) -> bool:
    """Read the next item with the local Ollama model. False when everything is read."""
    items = pick(conn, 1)
    if not items:
        return False
    news_id, source, title, summary, _ = items[0]
    try:
        form = read(source, title, summary or "")
    except OllamaDown:
        raise
    except Exception as e:  # unreadable reply, Ollama error…
        failed(conn, news_id, f"{type(e).__name__}: {e}")
        return True
    finally:
        release(items)
    save_note(conn, co, news_id, title, summary or "", form, f"ollama:{OLLAMA_MODEL}")
    return True


def feed(scope: str = "tracked", symbol: str = "", limit: int = 60) -> dict:
    """For the website: Narad's notes, newest first, each with Drona's answer where Narad asked for help.

    scope: tracked (notes naming a tracked stock), help (sent to Drona) or all; symbol narrows to one stock.
    """
    conn = connect()
    try:
        where, args = [], []
        if symbol:
            where.append("EXISTS (SELECT 1 FROM json_each(n.symbols) WHERE value = ?)")
            args.append(symbol)
        elif scope == "tracked":
            where.append(f"EXISTS (SELECT 1 FROM json_each(n.symbols) WHERE value IN ({','.join('?' * len(SYMBOLS))}))")
            args += list(SYMBOLS)
        if scope == "help":
            where.append("h.id IS NOT NULL")
        rows = conn.execute(
            "SELECT w.id, w.source, w.title, w.url, COALESCE(w.published_at, w.fetched_at), n.about, n.symbols, "
            "n.event, n.positives, n.negatives, n.sentiment, n.confidence, h.reason, h.status, h.answer "
            "FROM news_notes n JOIN news w ON w.id = n.news_id "
            "LEFT JOIN help_requests h ON h.asker = 'narad' AND h.ref = 'news:' || n.news_id "
            + (f"WHERE {' AND '.join(where)} " if where else "")
            + "ORDER BY COALESCE(w.published_at, w.fetched_at) DESC LIMIT ?", (*args, limit)).fetchall()
        return {
            "notes": [{"id": i, "source": source, "title": title, "url": url, "published": published, "about": about,
                       "symbols": json.loads(symbols), "event": event, "positives": json.loads(pos),
                       "negatives": json.loads(neg), "sentiment": sentiment, "confidence": confidence,
                       "help": None if reason is None else
                       {"reason": reason, "status": status, "answer": json.loads(answer) if answer else None}}
                      for i, source, title, url, published, about, symbols, event, pos, neg, sentiment, confidence,
                      reason, status, answer in rows],
            "news": dict(conn.execute("SELECT status, COUNT(*) FROM news GROUP BY status").fetchall()),
            "help": dict(conn.execute("SELECT status, COUNT(*) FROM help_requests GROUP BY status").fetchall()),
            "tracked": list(SYMBOLS),
        }
    finally:
        conn.close()


def run(take_over: bool = False) -> None:
    """take_over: when another Narad holds the lock, keep checking and continue once it stops."""
    told = None
    while True:
        try:
            if single_instance("narad"):
                conn = connect()
                co = companies()
                break
            msg = "another Narad is already running" + (" — will take over when it stops" if take_over else "")
        except Exception as e:  # E: disk not connected
            msg = f"not started — {type(e).__name__}: {e}"
        if msg != told:  # say it once, not every 10 minutes
            say(msg)
            told = msg
        if not take_over:
            return
        time.sleep(10 * 60)
    global _co
    readers = [r["name"] for r in READERS.values() if not r.get("paused")]
    say(f"started — {len(FEEDS)} publisher feeds, NSE announcements, Google News for {len(co.tracked)} companies; "
        + (f"reading with {', '.join(readers)} in parallel" if readers else "every reader is paused")
        + (f", ollama:{OLLAMA_MODEL} when every reader rests" if ollama_reads() else ""))
    _co = co
    for kid, reader in list(READERS.items()):
        _start_worker(kid, reader)
    next_pull = read_after = 0.0
    while True:
        try:
            if time.time() >= next_pull:
                collect(conn, co)
                next_pull = time.time() + EVERY
            # The keys and plans read on their own threads; the local model only while every one of them rests,
            # and only if it may read at all (ollama_reads)
            if ollama_reads() and all_resting() and time.time() >= read_after and read_one(conn, co):
                if read_after:
                    say("Ollama is back — reading again")
                    read_after = 0.0
                continue
        except OllamaDown as e:
            if not read_after:  # say it once per outage
                say(f"Ollama not reachable ({e}) — still collecting; will try reading every 5 min")
            read_after = time.time() + 5 * 60
        except Exception as e:  # disk unplugged, DB locked…: keep the loop alive
            say(f"error — {type(e).__name__}: {e}")
        time.sleep(min(60, max(1, next_pull - time.time())))


def start() -> None:
    threading.Thread(target=run, args=(True,), daemon=True, name="narad").start()


if __name__ == "__main__":
    keep_awake()
    run()
