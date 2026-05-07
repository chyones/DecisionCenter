from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient
from apps.edr.connectors.validation import validate_evidence_payload
from apps.edr.schemas.evidence import EvidenceObject


async def read_odoo(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Call the n8n Odoo read webhook and validate the response."""
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(settings.odoo_read_webhook, payload)
    return validate_evidence_payload(response)
