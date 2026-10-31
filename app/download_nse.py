"""Download every NSE bhavcopy (daily OHLCV of every traded security) from 3 Nov 1994 to today.

Resumable and incremental: finished days are recorded in nse_bhav_days, so running it again
only fetches what's missing (new days, or days that failed last time).

Usage: python -m app.download_nse
"""
import csv
import io
import random
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone

from .market_db import connect
from .system import keep_awake, logger, progress, single_instance

FIRST_DAY = date(1994, 11, 3)   # first trading day of NSE's capital-market segment
UDIFF_FROM = date(2024, 7, 8)   # NSE switched the bhavcopy to the UDiFF format
DELAY = 0.5                     # seconds between requests — NSE blocks fast scrapers
FLUSH_EVERY = 60                # seconds: save days in batches — every commit rewrites one page per symbol
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
IST = timezone(timedelta(hours=5, minutes=30))

INSERT = "INSERT OR REPLACE INTO nse_bhav VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"

say = logger("nse")

class Blocked(Exception):
    """NSE keeps refusing; stop and let the next run resume."""


def url_for(d: date) -> str:
    if d >= UDIFF_FROM:
        return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    m = MONTHS[d.month - 1]
    return f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.year}/{m}/cm{d.day:02d}{m}{d.year}bhav.csv.zip"


def fetch(url: str) -> bytes | None:
    """The file, or None when NSE has none for that day (weekend/holiday)."""
    for wait in (10, 30, 60, 180, 600):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            say(f"  HTTP {e.code} — retrying in {wait}s")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            say(f"  {type(e).__name__}: {e} — retrying in {wait}s")
        time.sleep(wait)
    raise Blocked(url)


def num(v: str | None) -> float | None:
    v = (v or "").strip()
    try:
        return float(v) if v not in ("", "-") else None
    except ValueError:
        return None


def whole(v: str | None) -> int | None:
    n = num(v)
    return int(n) if n is not None else None


def rows_old(reader: csv.DictReader, day: str):
    for raw in reader:
        r = {k.strip().upper(): (v or "").strip() for k, v in raw.items() if k}
        if r.get("SYMBOL"):
            yield (day, r["SYMBOL"], r.get("SERIES", ""), r.get("ISIN") or None, None,
                   num(r.get("OPEN")), num(r.get("HIGH")), num(r.get("LOW")), num(r.get("CLOSE")),
                   num(r.get("LAST")), num(r.get("PREVCLOSE")), whole(r.get("TOTTRDQTY")),
                   num(r.get("TOTTRDVAL")), whole(r.get("TOTALTRADES")))


def rows_udiff(reader: csv.DictReader, day: str):
    for r in reader:
        symbol = (r.get("TckrSymb") or "").strip()
        if symbol:
            yield (day, symbol, (r.get("SctySrs") or "").strip(), (r.get("ISIN") or "").strip() or None,
                   (r.get("FinInstrmNm") or "").strip() or None,
                   num(r.get("OpnPric")), num(r.get("HghPric")), num(r.get("LwPric")), num(r.get("ClsPric")),
                   num(r.get("LastPric")), num(r.get("PrvsClsgPric")), whole(r.get("TtlTradgVol")),
                   num(r.get("TtlTrfVal")), whole(r.get("TtlNbOfTxsExctd")))


def parse(data: bytes, d: date) -> list[tuple]:
    z = zipfile.ZipFile(io.BytesIO(data))
    reader = csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"))
    return list((rows_udiff if d >= UDIFF_FROM else rows_old)(reader, d.isoformat()))


def flush(conn, pending: list[tuple[str, str, list[tuple]]]) -> None:
    """Save buffered days in one transaction, so each symbol's page on disk is rewritten once, not once per day."""
    with conn:
        for day, status, rows in pending:
            conn.executemany(INSERT, rows)
            conn.execute("INSERT OR REPLACE INTO nse_bhav_days VALUES (?, ?, ?)", (day, status, len(rows)))
    pending.clear()


def finalize(conn) -> None:
    say("Indexing and building nse_symbols (first/last trading day of every security)…")
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_bhav_date ON nse_bhav(date);
        DROP TABLE IF EXISTS nse_symbols;
        CREATE TABLE nse_symbols AS
            SELECT symbol, series, MIN(date) AS first_date, MAX(date) AS last_date,
                   COUNT(*) AS trading_days, MAX(isin) AS isin, MAX(name) AS name
            FROM nse_bhav GROUP BY symbol, series;
    """)
    rows, first, last = conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM nse_bhav").fetchone()
    symbols = conn.execute("SELECT COUNT(DISTINCT symbol) FROM nse_symbols").fetchone()[0]
    say(f"nse_bhav: {rows:,} rows, {symbols:,} symbols, {first} -> {last}")


def main() -> int:
    """Exit codes for the data keeper (app/keeper.py): 0 done, 2 NSE kept refusing, 3 already running."""
    if not single_instance("download_nse"):
        say("another NSE download is already running")
        return 3
    keep_awake()
    conn = connect()
    done = {r[0] for r in conn.execute("SELECT date FROM nse_bhav_days")}
    today = datetime.now(IST).date()
    # Weekends too: NSE has held special Saturday/Sunday sessions (budget days, Muhurat trading)
    todo = [d for d in (FIRST_DAY + timedelta(n) for n in range((today - FIRST_DAY).days + 1)) if d.isoformat() not in done]
    say(f"{len(done):,} days already done, {len(todo):,} to check")

    started, saved, blocked = time.time(), 0, False
    pending, flushed = [], time.time()  # downloaded days not written yet: (date, status, rows)
    for i, d in enumerate(todo, 1):
        try:
            data = fetch(url_for(d))
        except Blocked:
            say("STOPPED: NSE keeps refusing. Run again later — it resumes from here.")
            blocked = True
            break
        if data is None:
            # The latest days may just not be published yet (bhavcopy appears in the evening)
            if (today - d).days > 3:
                pending.append((d.isoformat(), "holiday", []))
        else:
            try:
                rows = parse(data, d)
            except (zipfile.BadZipFile, UnicodeDecodeError, csv.Error) as e:
                say(f"  {d}: unreadable file ({e}) — will retry next run")
                rows = None
            if rows is not None:
                pending.append((d.isoformat(), "ok", rows))
                saved += 1
        if time.time() - flushed > FLUSH_EVERY:
            flush(conn, pending)
            flushed = time.time()
        if i % 5 == 0 or i == len(todo):
            progress("NSE bhavcopy", "days", i, len(todo), started)
        if i % 200 == 0 or i == len(todo):
            left = (len(todo) - i) * (time.time() - started) / i / 60
            say(f"{d}  checked {i:,}/{len(todo):,}  trading days saved {saved:,}  ~{left:.0f} min left")
        time.sleep(DELAY + random.random() * 0.2)

    flush(conn, pending)
    # nse_symbols (each security's first and last day) takes ~45 minutes over 12M rows and nothing in the app
    # reads it: rebuilt on a full run, or when the daily runs added days and it's the weekend
    missing = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'nse_symbols'").fetchone() is None
    if missing or (saved and (len(todo) > 30 or today.weekday() >= 5)):
        finalize(conn)
    conn.close()
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
