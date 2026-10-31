"""Runs prompts through the Antigravity CLI (`agy -p`), so Drona can use your Google AI Pro quota — no API key.

agy signs in with the Google account stored in a Windows user's Credential Manager, one account per Windows
user. Account 1 is yours: run `agy` once in a terminal to sign in. Account 2 lives in the hidden Windows user
candlecast2 (tools/agy2/setup.ps1), where a background worker runs agy for Drona: jobs go through
C:/ProgramData/candlecast/agy2/in and out. agy carries Gemini and Claude models, each with its own Pro quota,
and searches the web on its own. Each call runs sandboxed in an empty folder, so it can't touch the project.

Google allows headless runs on your own machine for your own use, on the same quota as the IDE: Drona calls
it one topic at a time per account, never in a tight loop.
"""
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .claude_cli import ClaudeError, UsageLimit

AGY = os.environ.get("CANDLECAST_AGY") or shutil.which("agy") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "agy/bin/agy.exe")
WORKDIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "candlecast" / "agy-work"
QUEUE = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "candlecast" / "agy2"
MAX_ARG = 30_000  # Windows caps a command line at 32,767 characters, and agy takes the prompt only as an argument
# seconds: an older heartbeat means account 2's worker isn't running. Long enough for one job: a worker started
# before it beat during jobs only beats between them.
ALIVE = 20 * 60

LOG = Path.home() / ".gemini" / "antigravity-cli" / "cli.log"
_SIGNED_IN = re.compile(r"authenticated successfully as (\S+@\S+)")


def _heartbeat() -> dict | None:
    try:
        beat = json.loads((QUEUE / "out" / "heartbeat.json").read_text(encoding="utf-8-sig"))
        age = datetime.now(timezone.utc) - datetime.fromisoformat(beat["at"].replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError):
        return None
    return beat if age.total_seconds() < ALIVE else None


def available(n: int = 1) -> bool:
    if n == 1:
        return Path(AGY).exists()
    beat = _heartbeat()
    return bool(beat and beat.get("agy") and beat.get("account"))


def parallel(n: int = 2) -> int:
    """How many jobs account n runs at once: account 1 runs agy directly, as often as asked; account 2's worker
    says so in its heartbeat (one, for a worker started before it could run several)."""
    if n == 1:
        return 99
    return int((_heartbeat() or {}).get("parallel") or 1)


def account(n: int = 1) -> str | None:
    """The Google account agy last signed in as, from its own log (the token itself is never read)."""
    if n != 1:
        return (_heartbeat() or {}).get("account")
    try:
        with LOG.open("rb") as f:
            f.seek(max(0, LOG.stat().st_size - 512_000))
            found = _SIGNED_IN.findall(f.read().decode("utf-8", "replace"))
    except OSError:
        return None
    return found[-1] if found else None


def _limit_hit(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in ("quota", "rate limit", "resource_exhausted", "resource exhausted", "429",
                                "limit reached", "exhausted", "usage limit"))


def _run_here(args: list[str], timeout: int) -> tuple[str, str, int]:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run([AGY, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout + 60, cwd=WORKDIR, stdin=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        raise ClaudeError(f"Antigravity CLI not found ({AGY})")
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"agy took longer than {timeout}s")
    return proc.stdout, proc.stderr, proc.returncode


def _run_worker(args: list[str], timeout: int) -> tuple[str, str, int]:
    """Hand the job to account 2's worker and wait for its reply. It works one job at a time, so a job may
    first wait for the one before it."""
    if not available(2):
        raise ClaudeError("account 2's worker isn't running (tools/agy2/setup.ps1)")
    job = uuid.uuid4().hex
    tmp, ready, reply = QUEUE / "in" / f"{job}.tmp", QUEUE / "in" / f"{job}.json", QUEUE / "out" / f"{job}.json"
    tmp.write_text(json.dumps({"args": subprocess.list2cmdline(args), "timeout": timeout}), encoding="utf-8")
    tmp.replace(ready)
    deadline = time.time() + 2 * timeout + 120
    while time.time() < deadline:
        if reply.exists():
            try:
                out = json.loads(reply.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                time.sleep(1)  # still being moved into place
                continue
            reply.unlink(missing_ok=True)
            return out.get("stdout") or "", out.get("stderr") or "", int(out.get("code", -1))
        time.sleep(2)
    ready.unlink(missing_ok=True)
    raise ClaudeError(f"account 2's worker didn't answer within {2 * timeout + 120}s")


def ask(prompt: str, system: str, *, model: str, timeout: int = 900, account_no: int = 1) -> tuple[str, int | None]:
    """The model's final answer as text and the tokens it used, from Google account 1 or 2 (agy has no system
    prompt flag, so the instructions go first)."""
    text = f"{system}\n\n---\n\n{prompt}"
    if len(text) > MAX_ARG:
        raise ClaudeError(f"prompt too long for agy ({len(text):,} characters)")
    args = ["--output-format", "json", "--model", model, "--sandbox", "--print-timeout", f"{timeout}s",
            "--disable-slash-commands", "-p", text]
    stdout, stderr, code = (_run_here if account_no == 1 else _run_worker)(args, timeout)
    try:
        out = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        msg = (stderr or stdout).strip()[-500:] or f"exit code {code}"
        raise (UsageLimit if _limit_hit(msg) else ClaudeError)(msg)
    if out.get("status") != "SUCCESS":
        msg = str(out.get("error") or out.get("status"))[:500]
        raise (UsageLimit if _limit_hit(msg) else ClaudeError)(msg)
    usage = out.get("usage") or {}
    return out.get("response") or "", usage.get("total_tokens")
