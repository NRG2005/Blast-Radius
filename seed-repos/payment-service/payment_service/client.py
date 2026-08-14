"""
payment_service/client.py

HTTP client for the upstream user service.
The DEFAULT_TIMEOUT controls how long we wait for each individual request.
"""
import time

# THIS IS THE VALUE UNDER CHANGE
# Scenario: we want to reduce this from 5.0 to 2.0 to "speed up" the service.
DEFAULT_TIMEOUT = 5.0  # seconds


def fetch_user(user_id: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """
    Fetch a user record from the upstream user service.

    In production this would make an HTTP request. Here we simulate
    a network call that takes ~1 second.
    """
    # Simulate network latency
    time.sleep(0.1)
    return {
        "id": user_id,
        "name": "Alice Example",
        "email": "alice@example.com",
        "credit_limit": 5000.0,
    }
