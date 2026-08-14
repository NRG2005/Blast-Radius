"""
payment_service/billing.py

Billing orchestration layer.

This module calls the user service to validate credit before charging.
It uses its own retry logic with back-off for transient upstream failures.

IMPORTANT ASSUMPTION (implicit, not imported from client.py):
  The retry loop below assumes each fetch_user call can take up to ~5 seconds.
  With MAX_RETRIES=3 and RETRY_SLEEP=2.0, the test for total elapsed time
  assumes: worst case ≈ 3 * 5s + 2 * 2s = 19s, so a 25s timeout in the test
  is safe. If DEFAULT_TIMEOUT is reduced to 2s, the actual max becomes
  3 * 2s + 2 * 2s = 10s — still within the 25s test budget — BUT the test
  also asserts a MINIMUM elapsed time (to prove retries actually happened),
  and that minimum is calibrated against the 5s timeout assumption.
"""
import time

from payment_service.client import fetch_user

MAX_RETRIES = 3
RETRY_SLEEP = 2.0  # seconds between attempts


class PaymentError(Exception):
    pass


class InsufficientCreditError(PaymentError):
    pass


def charge_user(user_id: str, amount: float) -> dict:
    """
    Charge a user for `amount`.

    Retries up to MAX_RETRIES times on transient errors.
    Returns a receipt dict on success.
    Raises InsufficientCreditError if the user's credit limit is too low.
    Raises PaymentError on exhausted retries.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            user = fetch_user(user_id)
            if user["credit_limit"] < amount:
                raise InsufficientCreditError(
                    f"User {user_id} credit limit {user['credit_limit']} < {amount}"
                )
            return {
                "status": "charged",
                "user_id": user_id,
                "amount": amount,
                "attempt": attempt,
            }
        except InsufficientCreditError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP)

    raise PaymentError(f"Failed after {MAX_RETRIES} retries: {last_error}")
