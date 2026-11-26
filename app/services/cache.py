"""Tiny thread-safe TTL cache for expensive read-only responses.

Search results are not cached (filters vary per keystroke); the facet menus,
stats and coverage payloads are, because every client requests them on open and
they only change when a collection run writes new records.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable

from app.config import settings

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}
MAX_ENTRIES = 256


def _key(namespace: str, params: dict | None) -> str:
    payload = json.dumps(params or {}, sort_keys=True, default=str)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"{namespace}:{digest}"


def get_or_set(
    namespace: str,
    params: dict | None,
    producer: Callable[[], Any],
    *,
    ttl: int | None = None,
) -> Any:
    ttl = settings.search_cache_seconds if ttl is None else ttl
    if ttl <= 0:
        return producer()
    key = _key(namespace, params)
    now = time.monotonic()
    with _lock:
        cached = _store.get(key)
        if cached and cached[0] > now:
            return cached[1]
    value = producer()
    with _lock:
        if len(_store) >= MAX_ENTRIES:
            # Drop expired entries, then the oldest one.
            for stale in [item for item, entry in _store.items() if entry[0] <= now]:
                _store.pop(stale, None)
            if len(_store) >= MAX_ENTRIES:
                _store.pop(next(iter(_store)), None)
        _store[key] = (now + ttl, value)
    return value


def invalidate(namespace: str | None = None) -> None:
    with _lock:
        if namespace is None:
            _store.clear()
            return
        for key in [item for item in _store if item.startswith(f"{namespace}:")]:
            _store.pop(key, None)


def stats() -> dict:
    now = time.monotonic()
    with _lock:
        live = sum(1 for expiry, _ in _store.values() if expiry > now)
        return {"entries": len(_store), "live": live, "ttl_seconds": settings.search_cache_seconds}
