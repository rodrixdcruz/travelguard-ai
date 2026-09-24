"""Tiny in-memory TTL cache shared by Nominatim-backed providers.

Same contract as the weather cache: thread-safe, monotonic clock, oldest-entry
eviction, values copied on the way in AND out so callers can never mutate a
shared entry. Nominatim data changes on OSM edit timescales (days), so a
6-hour TTL for geocoding and 30 minutes for POI fallbacks keeps "LIVE" honest
while making repeat lookups effectively free — and spares Nominatim, which
rate-limits per User-Agent.
"""
from __future__ import annotations

import time
from itertools import count
from threading import Lock
from typing import Any, Hashable

_LOCK = Lock()
_CACHE: dict[Hashable, tuple[float, Any, int]] = {}
_TICK = count()

# Entry = (expires_at_monotonic, value_copy, tick) — tick breaks eviction ties.
MAX_ENTRIES = 512


def cached(key: Hashable, ttl_seconds: float, producer):
    """Return cache[key]; on miss/expiry call producer() once and store it.

    producer() is called OUTSIDE the lock so slow HTTP never blocks other
    threads; a stampede may compute twice, which is harmless (same data).
    """
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None and hit[0] > now:
            return _copy(hit[1])
        if hit is not None:
            _CACHE.pop(key, None)

    value = producer()

    with _LOCK:
        if len(_CACHE) >= MAX_ENTRIES:
            oldest = min(_CACHE, key=lambda k: (_CACHE[k][0], _CACHE[k][2]))
            _CACHE.pop(oldest, None)
        _CACHE[key] = (time.monotonic() + ttl_seconds, _copy(value), next(_TICK))
    return _copy(value)


def _copy(value: Any) -> Any:
    """Deep-enough copy for JSON-shaped values (dict/list/scalars)."""
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy(v) for v in value]
    return value
