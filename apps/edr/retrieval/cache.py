"""Redis-backed evidence cache with in-memory fallback. Phase 1D."""

import hashlib
import json
from typing import Any

from apps.edr.config import settings

_NO_CACHE_KEYWORDS = {"delay", "claim", "payment"}


class EvidenceCache:
    """Cache retrieval results per user + query + project + RBAC fingerprint.

    Falls back to an in-memory dict if Redis is unreachable.
    """

    def __init__(self) -> None:
        self._memory: dict[str, Any] = {}
        self._redis = None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(settings.redis_url)
        except Exception:  # pragma: no cover
            self._redis = None

    def _build_key(
        self,
        user_id: str,
        query: str,
        project_code: str,
        allowed_resources: dict[str, Any],
    ) -> str:
        normalized_query = " ".join(query.lower().split())
        rbac_fingerprint = hashlib.sha256(
            json.dumps(allowed_resources, sort_keys=True).encode()
        ).hexdigest()[:16]
        return f"edr:cache:{user_id}:{normalized_query}:{project_code}:{rbac_fingerprint}"

    def _ttl(self, query: str) -> int:
        lowered = query.lower()
        if any(kw in lowered for kw in _NO_CACHE_KEYWORDS):
            return 0
        return 21_600

    async def get(
        self,
        user_id: str,
        query: str,
        project_code: str,
        allowed_resources: dict[str, Any],
    ) -> Any | None:
        key = self._build_key(user_id, query, project_code, allowed_resources)
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
                if raw:
                    return json.loads(raw)
            except Exception:  # pragma: no cover
                pass
        return self._memory.get(key)

    async def set(
        self,
        user_id: str,
        query: str,
        project_code: str,
        allowed_resources: dict[str, Any],
        value: Any,
    ) -> None:
        ttl = self._ttl(query)
        if ttl == 0:
            return
        key = self._build_key(user_id, query, project_code, allowed_resources)
        payload = json.dumps(value)
        if self._redis is not None:
            try:
                await self._redis.setex(key, ttl, payload)
                return
            except Exception:  # pragma: no cover
                pass
        self._memory[key] = value
