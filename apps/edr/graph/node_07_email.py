"""Node 7 - Email Retrieval. Spec: Sections 4.3, 10, and 16.

Project correspondence lives in the project's Microsoft 365 *group* mailbox.
A Unified group mailbox is not a user principal, so the per-user webhook
(``/users/{mailbox}/messages``) 404s for it; this node reads
``/groups/{id}/conversations`` directly via Graph when the project maps a
mail-enabled group. The legacy per-user/shared-mailbox webhook path is kept as a
fallback for projects that map an explicit user/shared mailbox allowlist.

RBAC: project *group* correspondence is project evidence (gated like SharePoint,
``can_access_sharepoint``). Searching a caller's *personal* mailbox is gated by
``can_access_own_mailbox``.
"""

from apps.edr.config import settings
from apps.edr.connectors.email import search_email, search_group_conversations
from apps.edr.graph import coverage
from apps.edr.graph.financial_evidence import filter_financial_evidence, financial_search_query
from apps.edr.graph.intent import classify_report_type
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore


def _enabled(mapping: dict) -> bool:
    return "email" in set(mapping.get("enabled_sources", []))


def _perms(role: str | None):
    if not role:
        return None
    return ROLE_PERMISSIONS.get(Role(role))


def _financial_filter_if_needed(state: DecisionState, evidence: list) -> tuple[list, int]:
    """Return evidence narrowed to financial context for financial reports."""
    if classify_report_type(state.query) != "financial":
        return evidence, len(evidence)
    raw_dicts = [e.model_dump() for e in evidence]
    kept = filter_financial_evidence(raw_dicts, query=state.query)
    kept_ids = {e["evidence_id"] for e in kept}
    return [e for e in evidence if e.evidence_id in kept_ids], len(raw_dicts)


async def _index(state: DecisionState, evidence: list) -> None:
    """Supplementary Qdrant indexing; never drops evidence on failure."""
    try:
        embedder = EmbeddingClient(settings.voyage_api_key)
        store = EvidenceStore()
        store.ensure_collection(state.project_code)
        texts = [e.excerpt for e in evidence]
        vectors = await embedder.embed(texts)
        for ev, vec in zip(evidence, vectors):
            store.insert(state.project_code, ev.evidence_id, vec, ev.model_dump())
        state.outputs["email_qdrant_status"] = "inserted"
    except Exception as exc:
        state.outputs["email_qdrant_status"] = f"error: {exc}"


async def run(state: DecisionState) -> DecisionState:
    try:
        mapping = ProjectMapping.load().get(state.project_code)
    except Exception:
        mapping = {}
    enabled = _enabled(mapping)
    perms = _perms(state.role)

    group = mapping.get("microsoft", {}).get("group", {})
    group_id = group.get("id")
    group_mail = group.get("mail")
    group_mail_enabled = bool(group.get("mail_enabled"))

    # Preferred path: project Microsoft 365 group mailbox conversations.
    if enabled and group_id and group_mail_enabled:
        # Group correspondence is project evidence -> gate like SharePoint.
        if perms and not perms.can_access_sharepoint:
            state.outputs["email_status"] = "rbac_denied"
            coverage.record(state, "email", enabled=enabled, attempted=False,
                            status="rbac_denied", evidence_count=0,
                            reason="Role not permitted to access project evidence.")
            return state.mark("node_07_email")
        try:
            evidence = await search_group_conversations(
                group_id=group_id, group_mail=group_mail, project_code=state.project_code
            )
            evidence, raw_count = _financial_filter_if_needed(state, evidence)
            state.evidence.extend([e.model_dump() for e in evidence])
            state.outputs["email_status"] = f"ok ({len(evidence)} items)"
            state.outputs["email_path"] = "group_conversations"
            if evidence:
                cov_status, cov_reason = "ok", ""
            else:
                cov_status = "zero_no_match"
                if classify_report_type(state.query) == "financial" and raw_count:
                    cov_reason = (
                        f"Group mailbox {group_mail} had conversations, but none matched "
                        "the financial evidence policy after filtering."
                    )
                else:
                    cov_reason = f"Group mailbox {group_mail} has no conversations."
            coverage.record(state, "email", enabled=enabled, attempted=True,
                            status=cov_status, evidence_count=len(evidence), reason=cov_reason)
            await _index(state, evidence)
            return state.mark("node_07_email")
        except Exception as exc:
            state.outputs["email_status"] = f"error: {exc}"
            coverage.record(state, "email", enabled=enabled, attempted=True,
                            status="error", evidence_count=0,
                            reason=f"Group conversations read failed: {exc}")
            return state.mark("node_07_email")

    # Fallback path: explicit user/shared mailbox allowlist via the n8n webhook.
    if perms and not perms.can_access_own_mailbox:
        state.outputs["email_status"] = "rbac_denied"
        coverage.record(state, "email", enabled=enabled, attempted=False,
                        status="rbac_denied", evidence_count=0,
                        reason="Role not permitted to access mailbox evidence.")
        return state.mark("node_07_email")

    allowed = [mb.lower() for mb in state.allowed_mailboxes]
    user_mailbox = (state.user_id or "").lower()
    if not allowed:
        state.outputs["email_status"] = "denied_no_allowlist"
        status = "blocked" if enabled else "not_enabled"
        reason = (
            "Email enabled but project has no mail-enabled group and no user/shared "
            "mailbox allowlist; operator must map a group id or shared mailbox."
            if enabled else "Email not enabled for this project."
        )
        coverage.record(state, "email", enabled=enabled, attempted=False,
                        status=status, evidence_count=0, reason=reason)
        return state.mark("node_07_email")
    if user_mailbox not in allowed:
        state.outputs["email_status"] = "denied_mailbox_not_in_allowlist"
        coverage.record(state, "email", enabled=enabled, attempted=False,
                        status="rbac_denied", evidence_count=0,
                        reason="Caller mailbox not in project allowlist.")
        return state.mark("node_07_email")

    try:
        payload: dict = {
            "query": financial_search_query(state.query)
            if classify_report_type(state.query) == "financial"
            else state.query,
            "project_code": state.project_code,
            "user_mailbox": state.user_id,
            "allowed_mailboxes": state.allowed_mailboxes,
        }
        evidence = await search_email(payload)
        evidence, raw_count = _financial_filter_if_needed(state, evidence)
        state.evidence.extend([e.model_dump() for e in evidence])
        state.outputs["email_status"] = f"ok ({len(evidence)} items)"
        state.outputs["email_path"] = "user_mailbox"
        cov_status = "ok" if evidence else "zero_no_match"
        if evidence:
            cov_reason = ""
        elif classify_report_type(state.query) == "financial" and raw_count:
            cov_reason = "Mailbox search returned messages, but none matched the financial evidence policy after filtering."
        else:
            cov_reason = "Mailbox search returned no messages."
        coverage.record(state, "email", enabled=enabled, attempted=True,
                        status=cov_status, evidence_count=len(evidence), reason=cov_reason)
        await _index(state, evidence)
    except Exception as exc:
        state.outputs["email_status"] = f"error: {exc}"
        coverage.record(state, "email", enabled=enabled, attempted=True,
                        status="error", evidence_count=0,
                        reason=f"Email connector error: {exc}")

    return state.mark("node_07_email")
