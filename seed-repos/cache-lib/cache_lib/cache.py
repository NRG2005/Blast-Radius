"""
cache_lib/cache.py

A simple in-memory TTL cache.
"""
import time
from typing import Any, Optional


# THIS IS THE VALUE UNDER CHANGE
# Scenario: reduce default TTL from 300s to 60s for "fresher" data.
DEFAULT_TTL = 300  # seconds — entries live for 5 minutes by default


class TTLCache:
    """
    Thread-unsafe in-memory cache with per-entry time-to-live.

    Entries are lazily expired on read. The cache is intentionally
    simple — no LRU eviction, no max-size — suitable for small
    configuration or session caches.
    """

    def __init__(self, default_ttl: int = DEFAULT_TTL):
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expiry_ts)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value. Uses default_ttl if no ttl provided."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (value, time.monotonic() + effective_ttl)

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value, or None if missing/expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
