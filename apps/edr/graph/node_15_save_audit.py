"""Node 15 — Save and Audit. Spec: Sections 16 and 30.

Persists four staging artifacts to MinIO and an audit row to PostgreSQL.
Connection failures are caught so the workflow can complete in test
environments where the services are not running.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.edr.graph.state import DecisionState
from apps.edr.llm import get_token_usage
from apps.edr.persistence import get_minio_store, get_postgres_store, hash_user_id
from apps.edr.schemas.audit import AuditArtifact

# Intents that do NOT require human approval before download.
_DRAFT_ONLY_INTENTS: set[str] = {"document_control"}


def _requires_approval(state: DecisionState) -> bool:
    """Determine whether this report requires human approval.

    Approval is required for financial reports, loss analysis, legal/contract
    risk reports, executive final reports, and claims/disputes reports.
    Draft-only outputs (document search results, simple summaries) may stay
    non-final.
    """
    intents: list[str] = state.outputs.get("intent", [])
    if not intents:
        return True
    # If ALL intents are draft-only, no approval required.
    if all(i in _DRAFT_ONLY_INTENTS for i in intents):
        return False
    return True


async def run(state: DecisionState) -> DecisionState:
    request_id = state.request_id
    user_id_hash = hash_user_id(state.user_id)
    quality_gate_status = state.outputs.get("quality_gate", "needs_review")
    requires_approval = _requires_approval(state)

    # ------------------------------------------------------------------
    # 1. Prepare stores (degrade gracefully if services are unreachable)
    # ------------------------------------------------------------------
    try:
        minio = get_minio_store()
        pg = get_postgres_store()
    except Exception as exc:
        state.outputs["audit_status"] = f"degraded: {exc}"
        return state.mark("node_15_save_audit")

    # ------------------------------------------------------------------
    # 2. Build artifacts
    # ------------------------------------------------------------------

    # 2a. Report exports (all generated formats; md is primary)
    raw_exports: dict[str, bytes] = state.outputs.get("report_exports_raw", {})
    report_keys: list[str] = []
    if raw_exports:
        for fmt, content in raw_exports.items():
            if isinstance(content, bytes):
                mime = "application/octet-stream"
                if fmt == "md":
                    mime = "text/markdown; charset=utf-8"
                elif fmt == "docx":
                    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif fmt == "xlsx":
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif fmt == "pdf":
                    mime = "application/pdf"
                elif fmt == "pptx":
                    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                try:
                    key = minio.put_bytes(
                        request_id,
                        f"executive-decision-report.{fmt}",
                        content,
                        content_type=mime,
                    )
                    report_keys.append(key)
                except Exception:
                    pass
    else:
        # Placeholder when gate blocked export
        placeholder = (
            f"# No Report Generated\n\n"
            f"Quality gate status: **{quality_gate_status}**.\n\n"
            f"Request ID: {request_id}\n"
        ).encode("utf-8")
        try:
            key = minio.put_bytes(
                request_id,
                "executive-decision-report.md",
                placeholder,
                content_type="text/markdown; charset=utf-8",
            )
            report_keys.append(key)
        except Exception:
            pass

    # 2b. Evidence pack (full evidence list from state)
    evidence_pack = {"request_id": request_id, "evidence": state.evidence}

    # 2c. Quality gate result
    qg_result = state.outputs.get("quality_gate_result", {})
    if not isinstance(qg_result, dict):
        qg_result = {}

    # 2d. Audit log (metadata only — no confidential source content)
    token_counts = get_token_usage(request_id)
    cost_total_usd = state.cost_accumulated_usd

    audit_artifact = AuditArtifact(
        request_id=request_id,
        user_id_hash=user_id_hash,
        timestamp=datetime.now(timezone.utc).isoformat(),
        query=state.query,
        authorized_projects=state.allowed_projects,
        authorized_mailboxes=state.allowed_mailboxes,
        blocked_sources=state.outputs.get("blocked_sources", []),
        tools_called=state.outputs.get("tools_called", []),
        tool_budgets_used=state.outputs.get("tool_budgets_used", {}),
        retrieval_loops=state.loop_count,
        quality_gate_status=quality_gate_status,
        final_status="staging",
        token_counts=token_counts,
        cost_total_usd=cost_total_usd,
        artifact_keys=[],
    )

    # ------------------------------------------------------------------
    # 3. Persist remaining artifacts to MinIO
    # ------------------------------------------------------------------
    ev_key: str | None = None
    qg_key: str | None = None
    audit_key: str | None = None
    try:
        ev_key = minio.put_json(request_id, "evidence-pack.json", evidence_pack)
    except Exception:
        pass
    try:
        qg_key = minio.put_json(request_id, "quality-gate-result.json", qg_result)
    except Exception:
        pass

    artifact_keys = report_keys + ([ev_key] if ev_key else []) + ([qg_key] if qg_key else [])

    # Update artifact keys in audit artifact before persisting it
    audit_artifact.artifact_keys = artifact_keys
    try:
        audit_key = minio.put_json(request_id, "audit-log.json", audit_artifact.model_dump())
        artifact_keys.append(audit_key)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 4. Persist to PostgreSQL
    # ------------------------------------------------------------------
    try:
        await pg.init_schema()
        await pg.insert_audit(
            request_id=request_id,
            user_id_hash=user_id_hash,
            project_code=state.project_code,
            query=state.query,
            quality_gate_status=quality_gate_status,
            token_counts=token_counts,
            cost_total_usd=cost_total_usd,
            artifact_keys=artifact_keys,
            requires_approval=requires_approval,
        )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 5. Update state
    # ------------------------------------------------------------------
    state.outputs["audit_status"] = "persisted"
    state.outputs["artifact_keys"] = artifact_keys
    state.outputs["audit_user_id_hash"] = user_id_hash
    state.outputs["requires_approval"] = requires_approval
    return state.mark("node_15_save_audit")
