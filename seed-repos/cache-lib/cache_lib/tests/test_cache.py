"""
tests/test_cache.py

Tests for the TTLCache.

BREAKING TEST: test_entry_survives_well_within_default_ttl
  - Sets a value without specifying a TTL (uses DEFAULT_TTL)
  - Sleeps for a period WELL WITHIN the original DEFAULT_TTL (300s)
  - Asserts the entry is still present
  - Since we can't sleep 300s in a test, we use a SHORT custom TTL (2s)
    and verify the pattern: entry set → sleep 1s → still present → sleep 2s → gone
  
  The REAL breaking test is test_config_cache_inherits_default_ttl:
  - Creates a ConfigCache (which internally uses DEFAULT_TTL from cache.py)
  - Sets a value
  - Sleeps 61 seconds (just past the NEW DEFAULT_TTL of 60s if changed)
  - Asserts the entry is STILL present (valid for DEFAULT_TTL=300s)
  - If DEFAULT_TTL drops to 60s, the entry expires at ~60s, making this FAIL
  
  NOTE: To keep tests fast, we mock time.monotonic in most tests.
  test_config_cache_inherits_default_ttl is the slow integration test.
"""
import time
import pytest
from unittest.mock import patch

from cache_lib.cache import TTLCache, DEFAULT_TTL
from cache_lib.config import ConfigCache


class TestTTLCacheBasics:
    def test_set_and_get(self):
        cache = TTLCache()
        cache.set("k", "v", ttl=60)
        assert cache.get("k") == "v"

    def test_missing_key_returns_none(self):
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_delete_removes_key(self):
        cache = TTLCache(default_ttl=60)
        cache.set("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_clear_empties_cache(self):
        cache = TTLCache(default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_size_reflects_entries(self):
        cache = TTLCache(default_ttl=60)
        assert cache.size == 0
        cache.set("x", 1)
        assert cache.size == 1
        cache.set("y", 2)
        assert cache.size == 2


class TestTTLExpiry:
    def test_entry_expires_after_ttl(self):
        """Entry should be gone after TTL seconds (mocked time)."""
        cache = TTLCache(default_ttl=10)
        base = time.monotonic()
        with patch("cache_lib.cache.time") as mock_time:
            mock_time.monotonic.return_value = base
            cache.set("k", "v", ttl=10)
            mock_time.monotonic.return_value = base + 5
            assert cache.get("k") == "v"  # still alive at 5s
            mock_time.monotonic.return_value = base + 11
            assert cache.get("k") is None  # expired at 11s

    def test_entry_survives_just_before_expiry(self):
        cache = TTLCache(default_ttl=10)
        base = time.monotonic()
        with patch("cache_lib.cache.time") as mock_time:
            mock_time.monotonic.return_value = base
            cache.set("k", "v")
            mock_time.monotonic.return_value = base + 9.99
            assert cache.get("k") == "v"

    def test_custom_ttl_overrides_default(self):
        cache = TTLCache(default_ttl=300)
        base = time.monotonic()
        with patch("cache_lib.cache.time") as mock_time:
            mock_time.monotonic.return_value = base
            cache.set("k", "v", ttl=5)  # short TTL despite 300s default
            mock_time.monotonic.return_value = base + 10
            assert cache.get("k") is None  # expired via custom TTL

    def test_default_ttl_is_used_when_not_specified(self):
        """If no TTL given to set(), DEFAULT_TTL is used."""
        cache = TTLCache(default_ttl=300)
        base = time.monotonic()
        with patch("cache_lib.cache.time") as mock_time:
            mock_time.monotonic.return_value = base
            cache.set("k", "v")  # no ttl arg
            mock_time.monotonic.return_value = base + 299
            assert cache.get("k") == "v"  # alive at 299s
            mock_time.monotonic.return_value = base + 301
            assert cache.get("k") is None  # expired at 301s


class TestDefaultTTLValue:
    def test_default_ttl_is_five_minutes(self):
        """
        The DEFAULT_TTL should be 300 seconds (5 minutes).
        
        This value is relied upon by:
        - ConfigCache (inherits it)
        - Infrastructure config refresh cycle (5-minute window)
        - Integration tests that sleep and check for cache hits
        
        If this changes to 60s, test_config_cache_inherits_default_ttl will fail.
        """
        assert DEFAULT_TTL == 300, (
            f"DEFAULT_TTL must be 300s (5 minutes). "
            f"Got {DEFAULT_TTL}s. "
            f"Changing this breaks ConfigCache and integration tests."
        )

    def test_default_ttl_exceeds_integration_test_sleep(self):
        """
        The integration test (test_config_cache_inherits_default_ttl) sleeps 61s
        and expects cache entries to still be alive. DEFAULT_TTL must exceed 61s.
        """
        INTEGRATION_TEST_SLEEP = 61  # seconds
        assert DEFAULT_TTL > INTEGRATION_TEST_SLEEP, (
            f"DEFAULT_TTL={DEFAULT_TTL}s is not greater than the integration test "
            f"sleep duration of {INTEGRATION_TEST_SLEEP}s. "
            f"The integration test will fail because entries expire before it checks."
        )


class TestConfigCache:
    def test_config_cache_get_or_default(self):
        cache = ConfigCache()
        assert cache.get_or_default("missing", "fallback") == "fallback"

    def test_config_cache_returns_set_value(self):
        cache = ConfigCache()
        cache.set("db_host", "localhost", ttl=60)
        assert cache.get("db_host") == "localhost"

    def test_config_cache_uses_default_ttl(self):
        """ConfigCache must use DEFAULT_TTL, not a hardcoded value."""
        cache = ConfigCache()
        base = time.monotonic()
        with patch("cache_lib.cache.time") as mock_time:
            mock_time.monotonic.return_value = base
            cache.set("setting", "value")
            # At DEFAULT_TTL - 1 seconds, entry should still be present
            mock_time.monotonic.return_value = base + DEFAULT_TTL - 1
            assert cache.get("setting") == "value", (
                f"ConfigCache entry expired too early. "
                f"Expected it to survive {DEFAULT_TTL - 1}s out of {DEFAULT_TTL}s TTL."
            )


# ---------------------------------------------------------------------------
# INTEGRATION TEST — runs with real time.sleep
# Marked slow; can be skipped with: pytest -m "not slow"
# This is the key test for the Blast Radius demo.
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_config_cache_inherits_default_ttl_real_time():
    """
    INTEGRATION TEST — THE BREAKING TEST for the cache-lib scenario.

    Verifies that ConfigCache entries (using DEFAULT_TTL) are still alive
    after 61 seconds. This passes when DEFAULT_TTL=300s, and FAILS when
    DEFAULT_TTL is reduced to 60s (entries expire right at the 60s mark).

    This test is marked @pytest.mark.slow and takes ~61 seconds to run.
    In the Blast Radius sandbox runner, this test is selected specifically
    to demonstrate the break.

    WHY THIS IS NON-OBVIOUS:
    - ConfigCache does not hardcode 300s — it inherits DEFAULT_TTL
    - The test doesn't check DEFAULT_TTL directly
    - The test assumes entries "live long enough" without knowing the exact TTL
    - It's a real production pattern: ops teams set up config caches expecting
      5-minute windows, and tests encode that assumption implicitly
    """
    cache = ConfigCache()
    cache.set("feature_flag_new_ui", True)
    cache.set("rate_limit_rpm", 1000)

    # Sleep just past what would be the new (broken) DEFAULT_TTL
    SLEEP_DURATION = 61  # seconds — just over 60s (the proposed new DEFAULT_TTL)
    time.sleep(SLEEP_DURATION)

    # Both entries should still be alive (DEFAULT_TTL=300s >> 61s)
    assert cache.get("feature_flag_new_ui") is True, (
        f"ConfigCache entry 'feature_flag_new_ui' expired after {SLEEP_DURATION}s. "
        f"This implies DEFAULT_TTL <= {SLEEP_DURATION}s. "
        f"Expected DEFAULT_TTL=300s so entries live for 5 minutes."
    )
    assert cache.get("rate_limit_rpm") == 1000, (
        f"ConfigCache entry 'rate_limit_rpm' expired after {SLEEP_DURATION}s."
    )
