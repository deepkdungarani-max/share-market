import os
from pathlib import Path

# Paths are relative to the project folder, so the pendrive works under any drive letter.
ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
BACKUP_DIR = ROOT / "backups"

# Every database lives on the 2 TB external hard disk: bulk market history (every NSE security since 1994 +
# Yahoo intraday), the app DB, the teacher's knowledge and the models' shared memory. Set
# CANDLECAST_MARKET_DIR if that disk gets another drive letter.
MARKET_DIR = Path(os.environ.get("CANDLECAST_MARKET_DIR", "E:/candlecast-data"))
MARKET_DB_PATH = MARKET_DIR / "market.db"
# The app DB: candles of the tracked symbols, trained model records, predictions and paper trades
DB_PATH = MARKET_DIR / "trading.db"
# What the teacher has learned about the market (lessons, hard Q&A, questions you asked). Same disk.
KNOWLEDGE_DB_PATH = MARKET_DIR / "knowledge.db"
# Shared memory of the models: news Narad collected, Narad's notes, help requests for Drona. Same disk.
MEMORY_DB_PATH = MARKET_DIR / "memory.db"

# Who writes Drona's lessons, help answers and Teacher answers, tried in order: models in the Antigravity CLI
# on your Google AI Pro quota (its Claude and its Gemini have separate quotas; when one is used up the next
# writes). Your Anthropic Claude Code login is never used unless you add it here yourself as claude:<model>.
# Best first: Claude Opus 4.6 (Thinking), then Sonnet 4.6, then Gemini 3.8 Flash (High).
DRONA_WRITERS = os.environ.get("CANDLECAST_DRONA_WRITERS",
                               "agy:claude-opus-4-6-thinking,agy:claude-sonnet-4-6,agy:gemini-3.8-flash-high").split(",")
# The same on the second Google AI Pro account (Windows user candlecast2, tools/agy2/setup.ps1). A second
# learner studies with these at the same time, so both accounts' quotas work in parallel.
DRONA_WRITERS_2 = os.environ.get("CANDLECAST_DRONA_WRITERS_2",
                                 "agy2:claude-opus-4-6-thinking,agy2:claude-sonnet-4-6,agy2:gemini-3.8-flash-high").split(",")
# Your ChatGPT Pro plan through CandleCast's own Codex CLI (tools/codex-login.ps1); a third learner studies
# with it as codex:<model>@<reasoning effort> (low … xhigh, max). Best first: GPT-6-Astra, Codex's frontier
# model, then GPT-6.1-Sol, its workhorse, when Astra's usage runs out.
CODEX_WRITERS = os.environ.get("CANDLECAST_CODEX_WRITERS", "codex:gpt-6-astra@high,codex:gpt-6.1-sol@high").split(",")
# More lessons at once: this many extra learners on each Google AI Pro account, besides the main loop (account 1)
# and the account 2 learner. A lesson takes ~5 min of research; each extra pair roughly doubles the pace, and
# spends that account's quota faster (a writer whose usage runs out rests until its reset, as before).
EXTRA_LEARNERS = int(os.environ.get("CANDLECAST_EXTRA_LEARNERS", "1"))
# Narad reads the news with these AI plans, all in parallel: agy = Google AI Pro account 1, agy2 = account 2,
# codex = ChatGPT (codex:<model>@<effort>). Fast models: a news item is a short read, and thousands come a day.
# The API keys on the website's API keys tab read alongside them while they aren't paused.
NEWS_PLANS = [p for p in os.environ.get(
    "CANDLECAST_NEWS_PLANS", "agy:gemini-3.8-flash-low,agy2:gemini-3.8-flash-low,codex:gpt-6-luna@low").split(",") if p]
# The local Ollama model reads news only if there's no other reader, or when this is set to 1: the user wants
# the news read by Gemini and ChatGPT, and a small local model misreads too much of it.
NARAD_OLLAMA = os.environ.get("CANDLECAST_NARAD_OLLAMA", "0") == "1"
# Offline fallback for Teacher answers when no writer can answer: a local Ollama model.
OLLAMA_URL = os.environ.get("CANDLECAST_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("CANDLECAST_OLLAMA_MODEL", "qwen2.5:3b")
# Narad reads the news with Gemini and Groq keys (far faster than the local model on a CPU), all in parallel,
# and falls back to Ollama while every key rests. The keys are added on the website's API keys tab and kept
# outside the project (see app/keys.py). Models are tried in order: when the first is overloaded (HTTP 503)
# or too slow, the lighter one reads instead.
GEMINI_MODELS = os.environ.get("CANDLECAST_GEMINI_MODELS", "gemini-flash-latest,gemini-flash-lite-latest").split(",")
GROQ_MODELS = os.environ.get("CANDLECAST_GROQ_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",")
# OpenRouter's free models Narad prefers, best first; the free list changes, so any other free model that can
# answer in JSON is tried after these (see narad.openrouter_models)
OPENROUTER_MODELS = os.environ.get(
    "CANDLECAST_OPENROUTER_MODELS",
    "nvidia/nemotron-3-ultra-550b-a55b:free,google/gemma-4-31b-it:free,nvidia/nemotron-3.5-super-vl:free").split(",")

# NSE symbols -> Yahoo Finance tickers.
SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "INFY": "INFY.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "LT": "LT.NS",
    "ITC": "ITC.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "MARUTI": "MARUTI.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
}
# Rupee pairs -> Yahoo tickers: the forex an Indian resident may trade (RBI allows INR pairs on recognised
# exchanges, i.e. NSE/BSE currency derivatives). Yahoo's rates are the 24-hour interbank ones, Monday to
# Friday; a daily candle is one UTC day, so it is final at 05:30 IST the next morning. No volume.
FOREX = {
    "USDINR": "USDINR=X",
    "EURINR": "EURINR=X",
    "GBPINR": "GBPINR=X",
    "JPYINR": "JPYINR=X",
}
# Every symbol by market, as the website names them; Sanjay trains one model per market and interval
MARKETS = {"stocks": SYMBOLS, "forex": FOREX}
TICKERS = {**SYMBOLS, **FOREX}


def market_of(symbol: str) -> str:
    return "forex" if symbol in FOREX else "stocks"

# Yahoo history limits: 15m -> last 60 days, 1h -> last 730 days, 1d -> since listing.
INTERVALS = {"15m": "60d", "1h": "730d", "1d": "max"}

for d in (MODELS_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)
