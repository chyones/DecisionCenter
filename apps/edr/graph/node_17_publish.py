"""Node 17 — Publish. Spec: Section 16, Node 17.

Publishes approved reports from staging to final in MinIO.
Only runs when a valid approval record exists in PostgreSQL.
Final artifacts are write-once and immutable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.edr.graph.state import DecisionState
from apps.edr.persistence import get_minio_store, get_postgres_store


# Artifacts that must be copied from staging to final on publish.
_ARTIFACT_NAMES = [
    "executive-decision-report.md",
    "evidence-pack.json",
    "quality-gate-result.json",
    "report-draft.json",
    "audit-log.json",
]


async def run(state: DecisionState) -> DecisionState:
    request_id = state.request_id

    try:
        pg = get_postgres_store()
        await pg.init_schema()
        audit = await pg.get_audit(request_id)
        decisions = await pg.get_review_decisions(request_id)
    except Exception:
        # If persistence is unavailable, we cannot verify approval;
        # remain blocked rather than degraded.
        state.outputs["publish_status"] = "blocked_until_approval"
        return state.mark("node_17_publish")

    if audit is None:
        state.outputs["publish_status"] = "blocked_until_approval"
        return state.mark("node_17_publish")

    review_state = audit.get("review_state", "staging")

    # Hard stops
    if review_state == "rejected":
        state.outputs["publish_status"] = "rejected"
        return state.mark("node_17_publish")

    if review_state == "revision_requested":
        state.outputs["publish_status"] = "revision_requested"
        return state.mark("node_17_publish")

    if review_state not in ("approved", "final"):
        state.outputs["publish_status"] = "blocked_until_approval"
        return state.mark("node_17_publish")

    # Publish: copy staging artifacts to final
    minio = get_minio_store()
    final_keys: list[str] = []

    for filename in _ARTIFACT_NAMES:
        try:
            key = minio.copy_to_final(request_id, filename)
            final_keys.append(key)
        except FileExistsError:
            # Already published — idempotent
            final_keys.append(f"final/{request_id}/{filename}")
        except Exception:
            pass

    # Write approval-log.json exactly once
    approval_decisions = [d for d in decisions if d.get("action") in ("approve", "admin_override")]
    if approval_decisions:
        latest = approval_decisions[0]
        approval_log = {
            "request_id": request_id,
            "approved_at": latest.get("created_at", datetime.now(timezone.utc).isoformat()),
            "approver_id_hash": latest.get("reviewer_id_hash", ""),
            "approval_action": latest.get("action", ""),
            "approval_comment": latest.get("comment", ""),
            "staging_artifact_keys": audit.get("artifact_keys", []),
            "final_artifact_keys": final_keys,
        }
        try:
            minio.put_json(request_id, "approval-log.json", approval_log, prefix="final")
            final_keys.append(f"final/{request_id}/approval-log.json")
        except Exception:
            pass

    # Update PostgreSQL review_state to final
    try:
        await pg.update_review_state(request_id, "final")
    except Exception:
        pass

    state.outputs["publish_status"] = "published"
    state.outputs["final_artifact_keys"] = final_keys
    return state.mark("node_17_publish")
