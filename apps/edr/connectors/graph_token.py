"""Microsoft Graph access token acquisition via client credentials flow.

The app authenticates as itself (not on behalf of a user) using the Entra API app
registration. Tokens are cached until 60 s before expiry to avoid a round-trip on
every connector call. The lock prevents concurrent token requests during cold-start.

Returns an empty string when Entra is not configured (local / dev mode).
"""

from __future__ import annotations

import asyncio
import time

import httpx

from apps.edr.config import settings

_TOKEN_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_EXPIRY_BUFFER_S = 60  # refresh this many seconds before actual expiry


class _CachedToken:
    __slots__ = ("access_token", "expires_at")

    def __init__(self, access_token: str, expires_at: float) -> None:
        self.access_token = access_token
        self.expires_at = expires_at


_cache: _CachedToken | None = None
_lock = asyncio.Lock()


async def get_graph_token() -> str:
    """Return a valid Graph access token.  Cached; re-acquired near expiry."""
    global _cache

    if not (
        settings.entra_tenant_id
        and settings.entra_client_id
        and settings.entra_client_secret
    ):
        return ""

    async with _lock:
        now = time.monotonic()
        if _cache is not None and _cache.expires_at > now:
            return _cache.access_token

        token_url = _TOKEN_URL_TEMPLATE.format(tenant_id=settings.entra_tenant_id)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.entra_client_id,
                    "client_secret": settings.entra_client_secret,
                    "scope": _GRAPH_SCOPE,
                },
            )
            response.raise_for_status()
            body = response.json()

        expires_in = int(body.get("expires_in", 3600))
        _cache = _CachedToken(
            access_token=body["access_token"],
            expires_at=now + expires_in - _EXPIRY_BUFFER_S,
        )
        return _cache.access_token


def _reset_cache() -> None:
    """Clear the module-level token cache.  Test-only."""
    global _cache
    _cache = None
