"""
tests/test_client.py

Direct tests for the payment_service client module.
These tests DO reference DEFAULT_TIMEOUT directly.
"""
import pytest
from payment_service.client import fetch_user, DEFAULT_TIMEOUT


class TestFetchUser:
    def test_returns_user_dict(self):
        user = fetch_user("u1")
        assert isinstance(user, dict)
        assert "id" in user
        assert "credit_limit" in user

    def test_default_timeout_is_positive(self):
        assert DEFAULT_TIMEOUT > 0

    def test_custom_timeout_accepted(self):
        """fetch_user accepts a custom timeout without error."""
        user = fetch_user("u1", timeout=1.0)
        assert user["id"] == "u1"

    def test_timeout_is_reasonable_for_retries(self):
        """
        Sanity check: DEFAULT_TIMEOUT should be high enough that the billing
        layer's retry loop (3 retries, 2s sleep) stays within a 30s total budget.

        This test directly checks the value.
        """
        from payment_service.billing import MAX_RETRIES, RETRY_SLEEP
        max_total = DEFAULT_TIMEOUT * MAX_RETRIES + (MAX_RETRIES - 1) * RETRY_SLEEP
        assert max_total <= 30.0, (
            f"With DEFAULT_TIMEOUT={DEFAULT_TIMEOUT}s, MAX_RETRIES={MAX_RETRIES}, "
            f"RETRY_SLEEP={RETRY_SLEEP}s, worst-case billing call = {max_total}s > 30s"
        )
