"""
tests/test_serializer.py

Tests for the user_api serializer module.
"""
import json
import pytest
from user_api.models import User
from user_api.serializer import serialize_user, validate_user_payload, REQUIRED_FIELDS


class TestSerializeUser:
    def test_serialize_returns_valid_json(self):
        user = User(username="alice", email="alice@example.com", tenant_id="t1")
        result = serialize_user(user)
        assert json.loads(result)  # must be valid JSON

    def test_serialized_output_matches_contract(self):
        """
        The API contract specifies the exact field names in the JSON response.
        This test pins the contract by checking the parsed keys.
        """
        user = User(username="alice", email="alice@example.com", tenant_id="t1")
        parsed = json.loads(serialize_user(user))
        assert set(parsed.keys()) == {"username", "email", "tenant_id", "is_active"}

    def test_username_value_preserved(self):
        user = User(username="testuser", email="t@t.com", tenant_id="t1")
        parsed = json.loads(serialize_user(user))
        assert parsed["username"] == "testuser"

    def test_inactive_user_serialized(self):
        user = User(username="ghost", email="g@g.com", tenant_id="t1", is_active=False)
        parsed = json.loads(serialize_user(user))
        assert parsed["is_active"] is False


class TestValidateUserPayload:
    def test_valid_payload_passes(self):
        payload = {
            "username": "alice",
            "email": "alice@example.com",
            "tenant_id": "t1",
            "is_active": True,
        }
        assert validate_user_payload(payload) is True

    def test_missing_username_fails(self):
        payload = {"email": "a@b.com", "tenant_id": "t1", "is_active": True}
        assert validate_user_payload(payload) is False

    def test_required_fields_set(self):
        """Ensure REQUIRED_FIELDS matches the current API contract."""
        assert "username" in REQUIRED_FIELDS
        assert "email" in REQUIRED_FIELDS
        assert "tenant_id" in REQUIRED_FIELDS
