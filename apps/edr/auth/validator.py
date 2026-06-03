"""Entra JWT validation. Production: RS256 via JWKS. Bypass: when Entra not configured.

Entra emits either **v2.0** access tokens (issuer ``…/v2.0``, audience == client id)
or **v1.0** tokens (issuer ``https://sts.windows.net/{tenant}/``, audience
``api://{client id}``), depending on the API app's ``accessTokenAcceptedVersion``.
Both are signed by the same tenant keys for the same app, so this validator accepts
either form: the trust boundary (tenant id + client id) is identical — only the
``iss``/``aud`` claim *format* differs.
"""
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

    Accepts both v1.0 and v2.0 tokens for the same tenant/app (see module docstring).
    """

    def __init__(self, tenant_id: str, client_id: str) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._jwks_uri = (
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )
        # v1.0 keys endpoint — fallback when a v1 token's signing key (``kid``) is
        # not published at the v2.0 keys endpoint. Microsoft normally serves the
        # same keys at both, so this is belt-and-suspenders.
        self._jwks_uri_v1 = (
            f"https://login.microsoftonline.com/{tenant_id}/discovery/keys"
        )
        # Accept both token-version issuer/audience forms (same tenant + app).
        self._issuers: list[str] = [
            f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            f"https://sts.windows.net/{tenant_id}/",
        ]
        self._audiences: list[str] = [client_id, f"api://{client_id}"]
        self._jwks_client: Any = None
        self._jwks_client_v1: Any = None

    def _get_jwks_client(self) -> Any:
        from jwt import PyJWKClient

        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self._jwks_uri)
        return self._jwks_client

    def _signing_key(self, token: str) -> Any:
        """Resolve the RS256 signing key by ``kid``, falling back to the v1 keyset.

        v1.0 tokens are normally signed with keys also published at the v2.0 keys
        endpoint; if a particular ``kid`` is missing there we retry the v1 endpoint.
        """
        from jwt import PyJWKClient
        from jwt.exceptions import PyJWKClientError

        try:
            return self._get_jwks_client().get_signing_key_from_jwt(token)
        except PyJWKClientError:
            if self._jwks_client_v1 is None:
                self._jwks_client_v1 = PyJWKClient(self._jwks_uri_v1)
            return self._jwks_client_v1.get_signing_key_from_jwt(token)

    def validate(self, token: str) -> JWTClaims:
        import jwt

        signing_key = self._signing_key(token)
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audiences,
                issuer=self._issuers,
            )
        except (jwt.InvalidIssuerError, jwt.InvalidAudienceError) as exc:
            # Surface the offending non-secret claims so an iss/aud/version
            # mismatch is named explicitly instead of an opaque "Invalid issuer".
            raise ValueError(self._claim_mismatch_detail(token, exc)) from exc
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

    def _claim_mismatch_detail(self, token: str, exc: Exception) -> str:
        """Build a non-secret diagnostic naming actual vs expected iss/aud/ver.

        Decodes the token *without* signature verification purely to read the
        offending claims for the error message; the value is never trusted.
        """
        import jwt

        try:
            claims = jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return f"token validation failed: {exc}"
        return (
            f"token claim mismatch ({exc}): "
            f"iss={claims.get('iss')!r} aud={claims.get('aud')!r} "
            f"ver={claims.get('ver')!r}; "
            f"expected iss in {self._issuers} and aud in {self._audiences}"
        )
