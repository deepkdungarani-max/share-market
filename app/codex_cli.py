"""Runs prompts through CandleCast's own Codex CLI (`codex exec`), so Drona can use your ChatGPT Pro plan.

It is a separate install (%LOCALAPPDATA%/candlecast/codex) signed in through its own CODEX_HOME
(%LOCALAPPDATA%/candlecast/codex-home), so the Codex in your IDE keeps its own account. Sign in or switch
accounts with tools/codex-login.ps1. Each call is ephemeral, read-only sandboxed in an empty folder, with
live web search on.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .claude_cli import ClaudeError, UsageLimit

_BASE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "candlecast"
CODEX = os.environ.get("CANDLECAST_CODEX") or str(
    _BASE / "codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe")
CODEX_HOME = _BASE / "codex-home"
WORKDIR = _BASE / "codex-work"
_EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def available() -> bool:
    return Path(CODEX).exists() and (CODEX_HOME / "auth.json").exists()


def account() -> str | None:
    """The ChatGPT account Codex last worked as, from its own log database (the login file is never read)."""
    found: dict[bytes, int] = {}
    for db in CODEX_HOME.glob("logs_*.sqlite"):
        try:
            for m in _EMAIL.findall(db.read_bytes()[-4_000_000:]):
                found[m] = found.get(m, 0) + 1
        except OSError:
            pass
    return max(found, key=found.get).decode() if found else ("ChatGPT" if available() else None)


def _limit_hit(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in ("usage limit", "rate limit", "rate_limit", "quota", "429", "limit reached",
                                "too many requests"))


def ask(prompt: str, system: str, *, model: str | None = None, effort: str | None = None, web: bool = True,
        timeout: int = 900) -> tuple[str, int | None]:
    """Codex's final answer as text and the tokens it used. model / effort None = Codex's defaults."""
    WORKDIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        last = Path(tmp) / "last.txt"
        cmd = [CODEX, *(["--search"] if web else []), "exec", "--skip-git-repo-check", "--ephemeral",
               "--sandbox", "read-only", "--color", "never", "--json", "-C", str(WORKDIR), "-o", str(last),
               *(["-m", model] if model else []),
               *(["-c", f'model_reasoning_effort="{effort}"'] if effort else []), "-"]
        try:
            proc = subprocess.run(cmd, input=f"{system}\n\n---\n\n{prompt}", capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout, cwd=WORKDIR,
                                  env={**os.environ, "CODEX_HOME": str(CODEX_HOME)},
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except FileNotFoundError:
            raise ClaudeError(f"Codex CLI not found ({CODEX})")
        except subprocess.TimeoutExpired:
            raise ClaudeError(f"Codex took longer than {timeout}s")
        text = last.read_text(encoding="utf-8", errors="replace") if last.exists() else ""

    tokens, errors = None, []
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type", "")
        if kind == "turn.completed":
            usage = event.get("usage") or {}
            tokens = sum(v for k, v in usage.items() if k.endswith("_tokens") and k != "cached_input_tokens"
                         and isinstance(v, int)) or None
        elif kind in ("error", "turn.failed"):
            errors.append(str(event.get("message") or (event.get("error") or {}).get("message") or event))
    if text.strip() and not errors:
        return text, tokens
    msg = ("; ".join(errors) or proc.stderr.strip()[-500:] or f"exit code {proc.returncode}")[:500]
    raise (UsageLimit if _limit_hit(msg) else ClaudeError)(msg)
