"""Node 17 — Publish. Spec: Section 16, Node 17.

Publishes approved reports from staging to final in MinIO.
Only runs when a valid approval record exists in PostgreSQL.
Final artifacts are write-once and immutable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apps.edr.graph.state import DecisionState
from apps.edr.persistence import get_minio_store, get_postgres_store

logger = logging.getLogger(__name__)


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
        logger.exception("publish: persistence unavailable for %s", request_id)
        state.outputs["publish_status"] = "blocked_until_approval"
        state.outputs["publish_errors"] = ["persistence unavailable"]
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
    publish_errors: list[str] = []

    for filename in _ARTIFACT_NAMES:
        try:
            key = minio.copy_to_final(request_id, filename)
            final_keys.append(key)
        except FileExistsError:
            # Already published — idempotent
            final_keys.append(f"final/{request_id}/{filename}")
        except Exception as exc:
            logger.exception("publish: failed to copy %s for %s", filename, request_id)
            publish_errors.append(f"copy_to_final failed: {filename}: {exc.__class__.__name__}")

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
        except Exception as exc:
            logger.exception("publish: failed to write approval-log.json for %s", request_id)
            publish_errors.append(f"approval-log.json write failed: {exc.__class__.__name__}")

    # Update PostgreSQL review_state to final
    try:
        await pg.update_review_state(request_id, "final")
    except Exception as exc:
        logger.exception("publish: failed to update review_state for %s", request_id)
        publish_errors.append(f"review_state update failed: {exc.__class__.__name__}")

    state.outputs["publish_status"] = "published"
    state.outputs["final_artifact_keys"] = final_keys
    if publish_errors:
        state.outputs["publish_errors"] = publish_errors
    return state.mark("node_17_publish")
