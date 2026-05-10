from dataclasses import dataclass
from typing import Any

import httpx

from apps.edr.config import settings


@dataclass(frozen=True)
class N8NWebhookClient:
    base_url: str
    token: str | None = None

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(base_url=self.base_url, timeout=settings.n8n_timeout) as client:
            response = await client.post(path, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
