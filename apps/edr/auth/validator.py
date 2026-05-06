"""Entra JWT validation. Production: RS256 via JWKS. Bypass: when Entra not configured."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JWTClaims:
    user_id: str
    role: str | None


class EntraJWTValidator:
    """Validates Entra ID JWTs (RS256) against the tenant's JWKS endpoint.

    Requires PyJWT[crypto] at runtime. Only constructed when ENTRA_CLIENT_ID is set.
    """

    def __init__(self, tenant_id: str, client_id: str) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._jwks_uri = (
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )

    def validate(self, token: str) -> JWTClaims:
        import jwt
        from jwt import PyJWKClient

        jwks_client = PyJWKClient(self._jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._client_id,
            issuer=f"https://login.microsoftonline.com/{self._tenant_id}/v2.0",
        )
        roles: list[str] = payload.get("roles", [])
        return JWTClaims(
            user_id=payload["oid"],
            role=roles[0] if roles else None,
        )
