from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient
from apps.edr.connectors.graph_token import get_graph_token
from apps.edr.connectors.validation import validate_evidence_payload
from apps.edr.schemas.evidence import EvidenceObject


async def search_sharepoint(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Call the n8n SharePoint search webhook and validate the response."""
    token = await get_graph_token()
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(
        settings.sharepoint_search_webhook,
        {**payload, "access_token": token},
    )
    return validate_evidence_payload(response)
