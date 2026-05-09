"""Entra JWT validation. Production: RS256 via JWKS. Bypass: when Entra not configured."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        # Single-role mode keeps backward compatibility with existing nodes;
        # callers that need multi-role decisions should use ``roles``.
        primary = roles[0] if roles else None
        return JWTClaims(
            user_id=payload["oid"],
            role=primary,
            roles=roles,
        )
