"""The cloud API keys Narad reads the news with (Gemini, Groq), added and removed from the website's API keys tab.

Kept in %APPDATA%/candlecast/keys.json: outside the project folder and the data disk, readable only by your
Windows user. On the first run it is filled from the GEMINI_API_KEY and GROQ_API_KEY environment variables
(comma-separated keys); after that this file is the only list. The website never receives a key back, only
its last four characters.
"""
import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path

import requests

PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "candlecast" / "keys.json"
PROVIDERS = {"gemini": "Gemini", "groq": "Groq", "openrouter": "OpenRouter"}
_lock = threading.Lock()


def key_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def load() -> list[dict]:
    """[{id, provider, name, key, added}], filled from the environment variables the first time."""
    with _lock:
        if PATH.exists():
            return json.loads(PATH.read_text(encoding="utf-8"))
        keys = []
        for provider, var in (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY")):
            for n, key in enumerate((k.strip() for k in os.environ.get(var, "").split(",") if k.strip()), 1):
                keys.append({"id": key_id(key), "provider": provider, "name": f"{PROVIDERS[provider]} key {n}",
                             "key": key, "added": datetime.now().isoformat(timespec="seconds")})
        _write(keys)
        return keys


def _write(keys: list[dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(keys, indent=1), encoding="utf-8")


def check(provider: str, key: str) -> str | None:
    """Why the key can't be used, or None when the provider accepts it (a free model-list call, no tokens)."""
    url = {"gemini": "https://generativelanguage.googleapis.com/v1beta/models",
           "groq": "https://api.groq.com/openai/v1/models",
           "openrouter": "https://openrouter.ai/api/v1/key"}[provider]  # the key's own info: free, no tokens
    headers = {"x-goog-api-key": key} if provider == "gemini" else {"Authorization": f"Bearer {key}"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
    except requests.RequestException as e:
        return f"couldn't reach {PROVIDERS[provider]} ({type(e).__name__})"
    if r.ok:
        return None
    return f"{PROVIDERS[provider]} refused the key (HTTP {r.status_code})"


def add(provider: str, key: str, name: str = "") -> dict:
    """Store a new key after checking it works. Raises ValueError with a message for the website."""
    key = key.strip()
    if provider not in PROVIDERS:
        raise ValueError("Pick Gemini or Groq")
    if len(key) < 20 or any(c.isspace() for c in key):
        raise ValueError("That doesn't look like an API key")
    keys = load()
    if any(k["id"] == key_id(key) for k in keys):
        raise ValueError("This key is already added")
    if problem := check(provider, key):
        raise ValueError(problem)
    n = sum(k["provider"] == provider for k in keys) + 1
    entry = {"id": key_id(key), "provider": provider, "name": name.strip()[:40] or f"{PROVIDERS[provider]} key {n}",
             "key": key, "added": datetime.now().isoformat(timespec="seconds")}
    with _lock:
        _write(keys + [entry])
    return entry


def set_paused(kid: str, paused: bool) -> bool:
    """Pause or resume a key; kept in the file, so a paused key stays paused after a restart."""
    keys = load()
    found = False
    for k in keys:
        if k["id"] == kid:
            k["paused"] = paused
            found = True
    if found:
        with _lock:
            _write(keys)
    return found


PLANS_PATH = PATH.parent / "plans.json"  # which of Narad's AI plan readers are paused (no secrets in it)


def paused_plans() -> set[str]:
    try:
        return set(json.loads(PLANS_PATH.read_text(encoding="utf-8")).get("paused", []))
    except (OSError, ValueError):
        return set()


def set_plan_paused(kid: str, paused: bool) -> None:
    with _lock:
        ids = paused_plans()
        ids = ids | {kid} if paused else ids - {kid}
        PLANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLANS_PATH.write_text(json.dumps({"paused": sorted(ids)}, indent=1), encoding="utf-8")


def remove(kid: str) -> bool:
    keys = load()
    left = [k for k in keys if k["id"] != kid]
    with _lock:
        _write(left)
    return len(left) < len(keys)
