"""Node 7 - Email Retrieval. Spec: Sections 4.3, 10, and 16."""

from apps.edr.config import settings
from apps.edr.connectors.email import search_email
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore


async def run(state: DecisionState) -> DecisionState:
    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_own_mailbox:
            state.outputs["email_status"] = "rbac_denied"
            return state.mark("node_07_email")

    # Spec Section 10: only mailboxes in the project allowlist may be searched.
    # Without an allowlist, fall back to denying access — never search a mailbox
    # that has not been explicitly approved for this project.
    allowed = [mb.lower() for mb in state.allowed_mailboxes]
    user_mailbox = (state.user_id or "").lower()
    if not allowed:
        state.outputs["email_status"] = "denied_no_allowlist"
        return state.mark("node_07_email")
    if user_mailbox not in allowed:
        state.outputs["email_status"] = "denied_mailbox_not_in_allowlist"
        return state.mark("node_07_email")

    try:
        payload: dict = {
            "query": state.query,
            "project_code": state.project_code,
            "user_mailbox": state.user_id,
            "allowed_mailboxes": state.allowed_mailboxes,
            "access_token": "",
        }
        evidence = await search_email(payload)
        state.evidence.extend([e.model_dump() for e in evidence])
        state.outputs["email_status"] = f"ok ({len(evidence)} items)"

        try:
            embedder = EmbeddingClient(settings.voyage_api_key)
            store = EvidenceStore()
            store.ensure_collection(state.project_code)
            texts = [e.excerpt for e in evidence]
            vectors = await embedder.embed(texts)
            for ev, vec in zip(evidence, vectors):
                store.insert(
                    state.project_code,
                    ev.evidence_id,
                    vec,
                    ev.model_dump(),
                )
            state.outputs["email_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["email_qdrant_status"] = f"error: {exc}"
    except Exception as exc:
        state.outputs["email_status"] = f"error: {exc}"

    return state.mark("node_07_email")
