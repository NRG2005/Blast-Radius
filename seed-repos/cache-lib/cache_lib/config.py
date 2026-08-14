"""
cache_lib/config.py

Application-level configuration helpers built on top of TTLCache.

This module provides a ConfigCache that stores application settings
with the assumption that entries last "about 5 minutes" — matching
the DEFAULT_TTL of 300 seconds. Comments and documentation in this
module explicitly reference the 5-minute window.
"""

from cache_lib.cache import TTLCache, DEFAULT_TTL


class ConfigCache(TTLCache):
    """
    Specialised cache for application configuration values.

    Entries are expected to live for approximately 5 minutes
    (the library default), which aligns with our config refresh
    cycle on the infrastructure side. Do not lower the TTL below
    60 seconds or config drift may cause test failures.

    NOTE: Integration tests in tests/test_config_cache.py sleep for
    61 seconds and then assert cache entries are STILL present (i.e.,
    not yet expired). This works because DEFAULT_TTL is 300s. If
    DEFAULT_TTL is lowered to 60s, those entries will expire right
    around the 61s mark and the test becomes flaky/failing.
    """

    def __init__(self):
        # Explicitly use the library default — we rely on the 5-minute window.
        super().__init__(default_ttl=DEFAULT_TTL)

    def get_or_default(self, key: str, default=None):
        """Return cached value or a default without caching the default."""
        result = self.get(key)
        return result if result is not None else default
