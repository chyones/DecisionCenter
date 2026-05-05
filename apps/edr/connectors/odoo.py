from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient


async def read_odoo(payload: dict[str, Any]) -> dict[str, Any]:
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    return await client.post("/webhook/odoo-read", payload)
