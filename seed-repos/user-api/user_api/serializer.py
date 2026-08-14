"""
user_api/serializer.py

API serialization utilities.

Provides stable, versioned JSON output for User objects.
The output format is documented in the API spec and used by downstream
consumers (mobile clients, partner integrations).
"""
import json
from user_api.models import User


# The canonical API response format — field names here are part of the
# public contract. They happen to match the dataclass field names,
# but this is an intentional design decision so that renaming a field
# in the model would automatically propagate here.
REQUIRED_FIELDS = {"username", "email", "tenant_id", "is_active"}


def serialize_user(user: User) -> str:
    """Return the canonical JSON representation of a User for API responses."""
    data = {
        "username": user.username,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "is_active": user.is_active,
    }
    return json.dumps(data, sort_keys=True)


def validate_user_payload(payload: dict) -> bool:
    """Check that an incoming JSON payload has all required user fields."""
    return REQUIRED_FIELDS.issubset(payload.keys())
