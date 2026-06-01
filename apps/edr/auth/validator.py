"""Entra JWT validation. Production: RS256 via JWKS. Bypass: when Entra not configured."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Effective-role precedence (highest privilege first). Entra returns the ``roles``
# app-role claim as an *unordered* array, so a user assigned several app roles must
# resolve to a single effective role by privilege, not by array position. In the
# owner-operator model ``admin`` is a full owner plus system operator and outranks
# all. Mirrors the 9 roles in apps/edr/rbac/roles.py with admin promoted to the top.
_ROLE_PRECEDENCE: tuple[str, ...] = (
    "admin",
    "executive",
    "project_manager",
    "finance",
    "commercial",
    "document_control",
    "procurement",
    "legal",
    "auditor",
)


@dataclass
class JWTClaims:
    user_id: str
    role: str | None
    roles: tuple[str, ...] = ()


class EntraJWTValidator:
    """Validates Entra ID JWTs (RS256) against the tenant's JWKS endpoint.

    The PyJWKClient is cached on the instance so repeated validate() calls
    reuse the JWKS fetch (PyJWT's client caches keys for ~1h by default).
    Requires PyJWT[crypto] at runtime. Only constructed when ENTRA_CLIENT_ID is set.
    """

    def __init__(self, tenant_id: str, client_id: str) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._jwks_uri = (
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )
        self._jwks_client: Any = None

    def _get_jwks_client(self) -> Any:
        from jwt import PyJWKClient

        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self._jwks_uri)
        return self._jwks_client

    def validate(self, token: str) -> JWTClaims:
        import jwt

        signing_key = self._get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._client_id,
            issuer=f"https://login.microsoftonline.com/{self._tenant_id}/v2.0",
        )
        roles_claim = payload.get("roles", [])
        roles: tuple[str, ...] = tuple(r for r in roles_claim if isinstance(r, str))
        # Resolve the single effective role by privilege precedence rather than
        # positionally: Entra's ``roles`` array is unordered, so a user assigned
        # both (e.g.) executive and admin must resolve to admin regardless of order.
        # Falls back to the first role for any value outside the precedence list.
        # ``roles`` stays available for callers that need the full multi-role set.
        primary = next(
            (r for r in _ROLE_PRECEDENCE if r in roles),
            roles[0] if roles else None,
        )
        return JWTClaims(
            user_id=payload["oid"],
            role=primary,
            roles=roles,
        )
