from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient


async def search_sharepoint(payload: dict[str, Any]) -> dict[str, Any]:
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    return await client.post("/webhook/sharepoint-search", payload)
