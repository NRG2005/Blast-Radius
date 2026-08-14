"""
tests/test_models.py

Tests for the User dataclass.

THE BREAKING TEST: test_user_json_contains_username_key
  - Does NOT import any field name constant
  - Hardcodes the string "username" in the expected JSON output
  - When User.username is renamed to User.user_name, json.dumps(asdict(user))
    will produce "user_name" instead of "username"
  - The assertion `'"username"' in json_str` will FAIL
  - This is non-obvious because the test doesn't do `user.username` —
    it just checks the serialized output string
"""
import json
import pytest
from user_api.models import User


class TestUserCreation:
    def test_create_user_with_all_fields(self):
        user = User(username="alice", email="alice@example.com", tenant_id="tenant-1")
        assert user.email == "alice@example.com"
        assert user.is_active is True

    def test_user_defaults_to_active(self):
        user = User(username="bob", email="bob@example.com", tenant_id="t1")
        assert user.is_active is True

    def test_inactive_user(self):
        user = User(username="carol", email="carol@example.com", tenant_id="t1", is_active=False)
        assert user.is_active is False


class TestUserSerialization:
    def test_to_json_returns_string(self):
        user = User(username="alice", email="alice@example.com", tenant_id="t1")
        assert isinstance(user.to_json(), str)

    def test_to_json_is_valid_json(self):
        user = User(username="alice", email="alice@example.com", tenant_id="t1")
        parsed = json.loads(user.to_json())
        assert isinstance(parsed, dict)

    def test_user_json_contains_username_key(self):
        """
        THE BREAKING TEST.

        The API contract specifies that serialized users MUST contain
        the key 'username' (not 'user_name', not 'login', not 'handle').
        This is checked by looking at the raw JSON string.

        This test does NOT do `user.username` — it checks the OUTPUT format.
        Renaming the dataclass field breaks this without any direct reference
        to the field name in the test.
        """
        user = User(username="alice", email="alice@example.com", tenant_id="t1")
        json_str = user.to_json()

        assert '"username"' in json_str, (
            f"Serialized user JSON must contain the key 'username' for API compatibility. "
            f"Got: {json_str}"
        )

    def test_json_does_not_contain_user_name_key(self):
        """
        Verify we haven't accidentally introduced a 'user_name' field
        (snake_case with underscore) which would indicate a field rename
        broke the API contract.
        """
        user = User(username="alice", email="alice@example.com", tenant_id="t1")
        json_str = user.to_json()
        # This is intentional: 'user_name' (with underscore) is wrong
        assert '"user_name"' not in json_str, (
            f"JSON must not contain 'user_name' — the field is 'username'. "
            f"Got: {json_str}"
        )

    def test_from_dict_round_trips(self):
        original = User(username="alice", email="alice@example.com", tenant_id="t1")
        data = json.loads(original.to_json())
        restored = User.from_dict(data)
        assert restored.email == original.email
        assert restored.is_active == original.is_active


class TestUserEquality:
    def test_equal_users(self):
        u1 = User(username="alice", email="alice@example.com", tenant_id="t1")
        u2 = User(username="alice", email="alice@example.com", tenant_id="t1")
        assert u1 == u2

    def test_different_usernames_not_equal(self):
        u1 = User(username="alice", email="alice@example.com", tenant_id="t1")
        u2 = User(username="bob", email="alice@example.com", tenant_id="t1")
        assert u1 != u2
