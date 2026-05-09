"""User-ID hashing for audit storage."""
from __future__ import annotations

import hashlib


def hash_user_id(user_id: str) -> str:
    """Return a deterministic SHA-256 hex digest of the raw user_id.

    The raw user_id is never stored in audit logs or PostgreSQL.
    """
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()
