import ctypes
import msvcrt
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import MARKET_DIR

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

_locks = {}  # name -> open lock file, held until the process exits


def disk_problem() -> str | None:
    """Why the market-data disk can't be used right now (not connected, locked by BitLocker…), or None."""
    try:
        if Path(MARKET_DIR.anchor).exists():
            return None
        return f"{MARKET_DIR.anchor} not found — connect the external hard disk (or set CANDLECAST_MARKET_DIR)."
    except OSError as e:  # a BitLocker-locked drive raises here instead of looking missing
        return f"{MARKET_DIR.anchor} can't be read ({e.strerror or e}) — unlock or reconnect the external hard disk."


def single_instance(name: str) -> bool:
    """True if this process now holds <market dir>/<name>.lock, so only one such worker runs at a time."""
    if name in _locks:
        return True
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    f = open(MARKET_DIR / f"{name}.lock", "a+")
    f.seek(0)  # every process locks the same byte
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return False
    _locks[name] = f
    return True


def locked(name: str) -> bool:
    """Whether some process holds <market dir>/<name>.lock right now (see single_instance), without taking it."""
    path = MARKET_DIR / f"{name}.lock"
    if not path.exists():
        return False
    try:
        with open(path, "a+") as f:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        return True
    return False


def keep_awake() -> None:
    """Stop Windows from sleeping while this process runs (the screen may still turn off).

    Released automatically when the process exits.
    """
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def nap(seconds: float) -> None:
    """time.sleep that ends on time across the laptop's sleep. Windows doesn't count its sleep against a
    waiting thread's timeout, so after waking a 1-hour time.sleep would still run out its hour; this checks the
    wall clock every 30 seconds instead, so every loop picks up within half a minute of the laptop waking."""
    end = time.time() + seconds
    while (left := end - time.time()) > 0:
        time.sleep(min(30.0, left))


PROGRESS = MARKET_DIR / "progress.json"  # what a running download is doing, for the website's Data tab


def progress(job: str, step: str, done: int, total: int, started: float) -> None:
    """Note a download's progress (and its time left at the pace so far) for the website. Never fails the job."""
    import json
    elapsed = time.time() - started
    left = (total - done) * elapsed / done if done else None
    try:
        PROGRESS.write_text(json.dumps({"job": job, "step": step, "done": done, "total": total,
                                        "seconds_left": round(left) if left is not None else None,
                                        "at": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    except OSError:
        pass


def logger(name: str) -> Callable[[str], None]:
    """print() with a timestamp that also appends to <market dir>/logs/<name>.log."""
    path = MARKET_DIR / "logs" / f"{name}.log"

    def say(msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    return say
