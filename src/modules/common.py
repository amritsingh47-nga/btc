"""
Shared helpers for the dashboard modules (macro, news, stocks, crypto,
portfolio, fx).

Free-tier rule: every upstream call is cached with a TTL and degrades
cleanly — a module that can't reach its API (no key, no network, rate
limit) reports {"available": false, "reason": ...} instead of breaking
the app.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

from src.utils.logger import log

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "modules"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


def cached(key: str, ttl: float, fetch: Callable[[], Any],
           stale_ok: bool = True) -> Any:
    """Return cached value if fresh; otherwise call fetch().

    On fetch failure returns the stale value when stale_ok, else raises."""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    try:
        value = fetch()
    except Exception:
        if stale_ok:
            with _cache_lock:
                hit = _cache.get(key)
            if hit:
                return hit[1]
        raise
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def http_get_json(url: str, params: Optional[Dict] = None, timeout: float = 15,
                  headers: Optional[Dict] = None) -> Any:
    resp = requests.get(url, params=params, timeout=timeout, headers=headers or {
        'User-Agent': 'analysts-trading-bot/1.0 (personal dashboard)'
    })
    resp.raise_for_status()
    return resp.json()


def http_get_text(url: str, timeout: float = 15) -> str:
    resp = requests.get(url, timeout=timeout, headers={
        'User-Agent': 'analysts-trading-bot/1.0 (personal dashboard)'
    })
    resp.raise_for_status()
    return resp.text


def unavailable(reason: str, **extra) -> Dict[str, Any]:
    payload = {'available': False, 'reason': reason}
    payload.update(extra)
    return payload


def load_json_store(name: str, default: Any) -> Any:
    path = DATA_DIR / f"{name}.json"
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        log.warning(f"store {name} unreadable: {e}")
    return default


def save_json_store(name: str, value: Any) -> None:
    path = DATA_DIR / f"{name}.json"
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, default=str))
    tmp.replace(path)
