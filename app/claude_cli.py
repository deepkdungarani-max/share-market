"""Runs prompts through the Claude Code CLI (`claude -p`), so learning uses your Claude login — no API key.

Each call is a fresh, isolated session: no hooks, plugins, MCP servers, project settings or saved
transcript, and only the tools asked for (web search / fetch for research, none otherwise).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Call the native claude.exe directly: going through claude.cmd would mangle multi-line arguments.
_NPM_EXE = Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
CLAUDE = os.environ.get("CANDLECAST_CLAUDE") or (str(_NPM_EXE) if _NPM_EXE.exists() else shutil.which("claude") or "claude")
SETTINGS = Path(tempfile.gettempdir()) / "candlecast-claude-settings.json"
WEB_TOOLS = "WebSearch,WebFetch"
# Hooks off: user hooks (style rules, notifications…) must not leak into lessons. Written once, at import.
SETTINGS.write_text('{"disableAllHooks": true}', encoding="utf-8")


class ClaudeError(Exception):
    pass


class UsageLimit(ClaudeError):
    """Claude says the plan's usage limit (or a rate limit) is reached: wait, then try again."""


_RESETS_IN = re.compile(r"resets?\s+in\s+(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", re.I)
_TRY_AT = re.compile(r"try again at\s+(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", re.I)


def rest_after(error: object, default: int, since: datetime | None = None) -> int:
    """Seconds from `since` (the moment the error came, default now) until a used-up plan resets, from what it
    said ("Resets in 3h47m47s" from Antigravity, "try again at 4:03 AM" from Codex, in this laptop's time),
    else default. A minute is added to be safe."""
    text = str(error)
    m = _RESETS_IN.search(text)
    if m and any(m.groups()):
        h, mins, secs = (int(x or 0) for x in m.groups())
        return h * 3600 + mins * 60 + secs + 60
    m = _TRY_AT.search(text)
    if m:
        hour, minute = int(m.group(1)) % 12 if m.group(3) else int(m.group(1)), int(m.group(2))
        if m.group(3) and m.group(3).lower().startswith("p"):
            hour += 12
        now = since or datetime.now()
        at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if at <= now:
            at += timedelta(days=1)
        return int((at - now).total_seconds()) + 60
    return default


def _limit_hit(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in ("usage limit", "rate limit", "rate_limit", "limit reached", "429", "overloaded"))


def ask(prompt: str, system: str, *, model: str, web: bool = False, timeout: int = 900) -> str:
    """Claude's final answer as text. web=True lets it search and read web pages first."""
    tools = WEB_TOOLS if web else ""
    cmd = [
        CLAUDE, "-p", "--output-format", "json", "--model", model,
        "--setting-sources", "project", "--settings", str(SETTINGS), "--strict-mcp-config",
        "--no-session-persistence", "--system-prompt", system,
        "--tools", tools, "--allowedTools", tools,
    ]
    try:
        # Prompt goes through stdin: no command-line length limit. cwd = temp, so no project settings apply.
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, cwd=tempfile.gettempdir(),
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        raise ClaudeError(f"Claude Code CLI not found ({CLAUDE}). Install it: npm i -g @anthropic-ai/claude-code")
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"Claude took longer than {timeout}s")

    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        msg = (proc.stderr or proc.stdout).strip()[-500:] or f"exit code {proc.returncode}"
        raise (UsageLimit if _limit_hit(msg) else ClaudeError)(msg)
    result = out.get("result") or ""
    if out.get("is_error") or out.get("subtype") != "success":
        msg = result or str(out.get("api_error_status") or out.get("subtype"))
        raise (UsageLimit if _limit_hit(msg) or out.get("api_error_status") == 429 else ClaudeError)(msg[:500])
    return result
