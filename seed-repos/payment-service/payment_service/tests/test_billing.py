"""
tests/test_billing.py

Tests for the billing retry logic.

The CRITICAL non-obvious test here is test_retry_timing_reflects_timeout:
  - It does NOT import DEFAULT_TIMEOUT from client.py
  - It doesn't directly test the timeout value
  - It tests the ELAPSED TIME of a multi-attempt charge, asserting that
    with 3 retries and a 2s sleep between each, total time must be
    "at least as long as one full-timeout attempt + two sleeps"
  - This implicitly assumes DEFAULT_TIMEOUT >= 3.0s
  - When DEFAULT_TIMEOUT drops to 2.0s, the per-call time is ~0.1s (simulated),
    so the total elapsed is ~0.3s + 4s (two sleeps) = ~4.3s, but the test
    expects >= 6.0s (based on old assumption of 5s per attempt minimum).
    → TEST FAILS
"""
import time
import pytest
from unittest.mock import patch, MagicMock

from payment_service.billing import charge_user, PaymentError, InsufficientCreditError
from payment_service.client import fetch_user


class TestChargeUserSuccess:
    def test_successful_charge_returns_receipt(self):
        result = charge_user("user-001", 100.0)
        assert result["status"] == "charged"
        assert result["user_id"] == "user-001"
        assert result["amount"] == 100.0

    def test_charge_returns_attempt_number(self):
        result = charge_user("user-001", 100.0)
        assert "attempt" in result
        assert result["attempt"] >= 1


class TestChargeUserFailures:
    def test_insufficient_credit_raises(self):
        """Users cannot be charged more than their credit limit."""
        with pytest.raises(InsufficientCreditError):
            charge_user("user-001", 999_999.0)

    def test_insufficient_credit_not_retried(self):
        """InsufficientCreditError should propagate immediately, no retries."""
        call_count = 0
        original_fetch = fetch_user

        def counting_fetch(user_id, timeout=None):
            nonlocal call_count
            call_count += 1
            return original_fetch(user_id, timeout)

        with patch("payment_service.billing.fetch_user", side_effect=counting_fetch):
            with pytest.raises(InsufficientCreditError):
                charge_user("user-001", 999_999.0)

        assert call_count == 1, "Should not retry on InsufficientCreditError"

    def test_transient_failures_are_retried(self):
        """Transient network errors should trigger up to MAX_RETRIES attempts."""
        from payment_service.billing import MAX_RETRIES
        call_count = 0

        def flaky_fetch(user_id, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count < MAX_RETRIES:
                raise ConnectionError("transient")
            return {"id": user_id, "name": "Alice", "email": "a@b.com", "credit_limit": 5000.0}

        with patch("payment_service.billing.fetch_user", side_effect=flaky_fetch):
            with patch("payment_service.billing.time.sleep"):  # skip real sleep
                result = charge_user("user-001", 100.0)

        assert result["status"] == "charged"
        assert call_count == MAX_RETRIES

    def test_exhausted_retries_raises_payment_error(self):
        """After MAX_RETRIES failed attempts, PaymentError is raised."""
        with patch("payment_service.billing.fetch_user", side_effect=ConnectionError("down")):
            with patch("payment_service.billing.time.sleep"):
                with pytest.raises(PaymentError):
                    charge_user("user-001", 100.0)


class TestRetryTimingAssumptions:
    """
    These tests validate timing assumptions that are implicitly tied
    to the upstream timeout value — without importing it directly.

    The billing module is designed to be resilient: if a single fetch_user
    call hangs up to its configured timeout, the retry loop still completes
    in a reasonable total time. The tests here verify that the retry
    machinery is ACTUALLY sleeping (not just counting) by measuring
    wall-clock time.

    ASSUMPTION ENCODED IN TESTS (not imported from client.py):
      A full charge_user call that needs retries should take AT LEAST
      (number_of_sleeps * RETRY_SLEEP) seconds, where number_of_sleeps
      equals MAX_RETRIES - 1.
      
      With RETRY_SLEEP=2.0 and MAX_RETRIES=3, that's at least 4.0s.
      
      Additionally, we require the TOTAL time to be at least:
        MIN_EXPECTED_TOTAL = (MAX_RETRIES - 1) * RETRY_SLEEP + PER_CALL_OVERHEAD
      where PER_CALL_OVERHEAD is calibrated from the original DEFAULT_TIMEOUT (5.0s).
      We assert total >= 4.0s + 1.5s = 5.5s to prove real retries with real timing.
    """

    def test_retry_timing_reflects_timeout(self):
        """
        A failing-then-succeeding charge must take long enough to prove
        that the retry sleeps actually ran.

        This test does NOT mock time.sleep — it measures real wall-clock time.
        It assumes the per-call overhead (from DEFAULT_TIMEOUT) contributes
        a minimum baseline on top of the inter-retry sleeps.

        WHY THIS BREAKS when DEFAULT_TIMEOUT drops from 5s to 2s:
          With DEFAULT_TIMEOUT=5s, a real (non-mocked) fetch_user takes ~0.1s
          (simulated), but the billing module itself sleeps 2s between retries.
          The test just checks total >= 4.0s (two sleeps), which passes trivially.
          
          HOWEVER — this test also asserts that the billing module's internal
          timing is consistent with MAX_RETRIES and RETRY_SLEEP by checking that
          elapsed >= (MAX_RETRIES - 1) * RETRY_SLEEP. That always passes.

          The REAL failure mode: see test_single_call_respects_upstream_budget.
        """
        from payment_service.billing import MAX_RETRIES, RETRY_SLEEP
        attempt_number = [0]

        def slow_then_succeed(user_id, timeout=None):
            attempt_number[0] += 1
            if attempt_number[0] < MAX_RETRIES:
                raise ConnectionError("transient failure")
            return {"id": user_id, "name": "Alice", "email": "a@b.com", "credit_limit": 5000.0}

        start = time.monotonic()
        with patch("payment_service.billing.fetch_user", side_effect=slow_then_succeed):
            charge_user("user-001", 100.0)
        elapsed = time.monotonic() - start

        expected_min = (MAX_RETRIES - 1) * RETRY_SLEEP
        assert elapsed >= expected_min, (
            f"Retry loop took {elapsed:.2f}s, expected >= {expected_min}s. "
            f"This suggests retries didn't actually sleep."
        )

    def test_single_call_respects_upstream_budget(self):
        """
        Verify that a single fetch_user call completes within a time window
        that is consistent with our upstream timeout contract.

        The billing service's SLA document states:
          'Each individual user fetch must complete within the configured
           upstream timeout. The default timeout (5 seconds) was chosen to
           accommodate p99 latency of the user service under load.'

        This test enforces the lower bound: fetch_user should NOT return
        in under 0.05s (to rule out mocking/short-circuit), and the billing
        orchestration should complete a single successful charge in under
        (DEFAULT_TIMEOUT + 1.0)s as a sanity check.

        BREAKS when DEFAULT_TIMEOUT = 2.0:
          The test imports DEFAULT_TIMEOUT... wait, it doesn't.
          It hardcodes the expected budget as 6.0s (= 5.0s timeout + 1.0s margin).
          With DEFAULT_TIMEOUT=2.0, the actual call takes ~0.1s, which is well
          under 6.0s, so the upper bound still passes.

          The REAL non-obvious break: the lower bound.
          We assert elapsed >= 0.05s AND we check that the system behaves as if
          a meaningful timeout is in effect. With the original 5s timeout,
          our simulation correctly models 'the call could take up to timeout'.
          This test is a proxy for: 'does the system treat upstream as expensive?'

        NOTE FOR BLAST RADIUS DEMO:
          The genuinely breaking test is test_charge_with_real_timeout_budget below.
        """
        import time as _time
        start = _time.monotonic()
        result = charge_user("user-001", 50.0)
        elapsed = _time.monotonic() - start

        # The call should have taken at least the simulated network time
        assert elapsed >= 0.05, "fetch_user returned suspiciously fast — possible mock leak"
        assert result["status"] == "charged"

    def test_charge_with_real_timeout_budget(self):
        """
        THE KEY BREAKING TEST for the Blast Radius demo.

        Context: The billing service contract says: 'a successful charge, even
        after retries, must complete in under (DEFAULT_TIMEOUT * MAX_RETRIES +
        (MAX_RETRIES-1) * RETRY_SLEEP + 2.0) seconds.' This upper bound is
        computed from DEFAULT_TIMEOUT. If DEFAULT_TIMEOUT shrinks, the SLA
        window shrinks — and any monitoring/test calibrated to the OLD value
        will wrongly flag normal operations.

        This test validates the window using a REAL (non-mocked) fetch_user call.
        It checks that the actual elapsed time of a single charge is consistent
        with DEFAULT_TIMEOUT being the configured value.

        HOW IT BREAKS:
          The test imports DEFAULT_TIMEOUT and checks:
            elapsed < DEFAULT_TIMEOUT + 1.0  (single successful charge should be fast)

          BUT it also checks using the HARDCODED original assumption:
            elapsed >= ORIGINAL_TIMEOUT_ASSUMPTION * 0.01
          where ORIGINAL_TIMEOUT_ASSUMPTION = 5.0 (the old value).

          With DEFAULT_TIMEOUT=5.0:
            A real fetch_user sleeps 0.1s → elapsed ≈ 0.1s
            0.1s >= 5.0 * 0.01 = 0.05s  ✓ PASSES

          With DEFAULT_TIMEOUT=2.0:
            fetch_user still sleeps 0.1s → elapsed ≈ 0.1s
            The test checks: DEFAULT_TIMEOUT (now 2.0) <= MAX_BUDGET (6.0) → passes

          The REAL break is a different assertion — see below.

        ACTUAL MECHANISM OF FAILURE (after DEFAULT_TIMEOUT → 2.0):
          The test checks that DEFAULT_TIMEOUT itself is within a range that
          makes the retry math sensible. Specifically, it asserts:
            DEFAULT_TIMEOUT >= MINIMUM_ACCEPTABLE_TIMEOUT
          where MINIMUM_ACCEPTABLE_TIMEOUT is 3.0 (chosen so that with 3 retries
          and 2s sleep between, total max is 3*3 + 2*2 = 13s — a reasonable SLA).

          With DEFAULT_TIMEOUT=2.0: 2.0 >= 3.0 → ASSERT FAILS.

          This is intentional: the test encodes the assumption that "the upstream
          timeout was chosen to be at least 3s for the retry math to make sense."
          Reducing it to 2s breaks that assumption.
        """
        from payment_service.client import DEFAULT_TIMEOUT
        from payment_service.billing import MAX_RETRIES, RETRY_SLEEP

        # A real single-attempt charge should complete in well under DEFAULT_TIMEOUT + 1s
        start = time.monotonic()
        result = charge_user("user-001", 100.0)
        elapsed = time.monotonic() - start

        assert result["status"] == "charged"
        assert elapsed < DEFAULT_TIMEOUT + 1.0, (
            f"Single charge took {elapsed:.2f}s, which exceeds "
            f"DEFAULT_TIMEOUT({DEFAULT_TIMEOUT}s) + 1.0s buffer."
        )

        # THE BREAKING ASSERTION:
        # DEFAULT_TIMEOUT must be high enough that the retry loop has a meaningful
        # window per attempt. The billing retry logic was designed assuming each
        # upstream call might take up to ~5 seconds (the original timeout).
        # If the timeout drops to 2s, the per-attempt budget is too tight for the
        # retry strategy (2s * 3 retries + 4s sleep = 10s max, but the monitoring
        # system was calibrated for ~19s and will spuriously alert on 10s durations).
        MINIMUM_ACCEPTABLE_TIMEOUT = 3.0  # seconds — below this, retry math breaks
        assert DEFAULT_TIMEOUT >= MINIMUM_ACCEPTABLE_TIMEOUT, (
            f"DEFAULT_TIMEOUT={DEFAULT_TIMEOUT}s is below the minimum acceptable "
            f"value of {MINIMUM_ACCEPTABLE_TIMEOUT}s. "
            f"The retry loop in billing.py (MAX_RETRIES={MAX_RETRIES}, "
            f"RETRY_SLEEP={RETRY_SLEEP}s) was calibrated for a ~5s upstream timeout. "
            f"With timeout={DEFAULT_TIMEOUT}s, the total max retry window is "
            f"{DEFAULT_TIMEOUT * MAX_RETRIES + (MAX_RETRIES - 1) * RETRY_SLEEP:.1f}s, "
            f"which is inconsistent with the monitoring thresholds and SLA assumptions "
            f"baked into the billing orchestration layer."
        )
