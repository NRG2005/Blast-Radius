"""
user_api/models.py

Core data models for the user API.
"""
from dataclasses import dataclass, asdict
import json


@dataclass
class User:
    """Represents an authenticated user in the system."""
    # THE FIELD NAME IS UNDER CHANGE
    # Scenario: rename `username` → `user_name` to follow our new naming convention.
    username: str  # login handle, unique per tenant
    email: str
    tenant_id: str
    is_active: bool = True

    def to_json(self) -> str:
        """Serialize the user to a canonical JSON string."""
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(**data)
