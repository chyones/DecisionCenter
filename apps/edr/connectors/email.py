from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient
from apps.edr.connectors.validation import validate_evidence_payload
from apps.edr.schemas.evidence import EvidenceObject


async def search_email(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Call the n8n email search webhook and validate the response."""
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(settings.email_search_webhook, payload)
    return validate_evidence_payload(response)
