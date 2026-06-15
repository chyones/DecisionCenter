import hashlib
from typing import Any

import httpx

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient
from apps.edr.connectors.graph_token import get_graph_token
from apps.edr.connectors.validation import validate_evidence_payload
from apps.edr.schemas.evidence import EvidenceObject

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def search_email(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Call the n8n email search webhook and validate the response.

    Used for *user / shared mailbox* evidence via ``/users/{mailbox}/messages``.
    Microsoft 365 *group* mailboxes are not user principals and 404 on that
    endpoint — use ``search_group_conversations`` for those.
    """
    token = await get_graph_token()
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(
        settings.email_search_webhook,
        {**payload, "access_token": token},
    )
    return validate_evidence_payload(response)


async def search_group_conversations(
    group_id: str,
    group_mail: str | None = None,
    project_code: str | None = None,
    top: int = 25,
) -> list[EvidenceObject]:
    """Read a Microsoft 365 *Unified group* mailbox's conversations via Graph.

    A Unified group mailbox is not a user principal, so ``/users/{mail}/messages``
    returns 404 ErrorInvalidUser. The correct path is
    ``/groups/{id}/conversations`` (proven against the live tenant with the app's
    application token — no per-user delegation needed). The app holds the Graph
    token directly; the n8n email webhook (per-user ``/messages``) cannot serve a
    group mailbox without a workflow redesign, so this reads Graph directly.
    """
    token = await get_graph_token()
    if not token:
        raise RuntimeError("Graph token unavailable")
    url = f"{_GRAPH_BASE}/groups/{group_id}/conversations?$top={int(top)}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.n8n_timeout) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    conversations = data.get("value", []) if isinstance(data, dict) else []
    evidence: list[EvidenceObject] = []
    for conv in conversations:
        conv_id = conv.get("id", "")
        topic = conv.get("topic") or "No subject"
        preview = (conv.get("preview") or topic or "").strip()
        senders = conv.get("uniqueSenders") or []
        digest = hashlib.sha256(
            (conv_id + (conv.get("lastDeliveredDateTime") or "")).encode("utf-8")
        ).hexdigest()
        evidence.append(
            EvidenceObject(
                evidence_id="eml-grp-" + (conv_id or digest[:16]),
                source_type="email",
                source_uri=f"{_GRAPH_BASE}/groups/{group_id}/conversations/{conv_id}",
                title=topic,
                project_code=project_code,
                timestamp=conv.get("lastDeliveredDateTime"),
                excerpt=preview[:500],
                hash_sha256=digest,
                confidence="medium",
                tags=["email", "group", "conversation"],
                metadata={
                    "group_id": group_id,
                    "group_mail": group_mail,
                    "unique_senders": [str(s) for s in senders][:10],
                    "has_attachments": bool(conv.get("hasAttachments", False)),
                },
            )
        )
    return evidence
