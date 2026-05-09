"""Node 16 — Human Review. Spec: Section 16, Node 16.

Reads the current review state from PostgreSQL and exposes it in the
workflow outputs so downstream nodes can act on it.
"""
from __future__ import annotations

from apps.edr.graph.state import DecisionState
from apps.edr.persistence import get_postgres_store


async def run(state: DecisionState) -> DecisionState:
    request_id = state.request_id

    try:
        pg = get_postgres_store()
        await pg.init_schema()
        audit = await pg.get_audit(request_id)
        decisions = await pg.get_review_decisions(request_id)
    except Exception:
        audit = None
        decisions = []

    if audit:
        review_state = audit.get("review_state", "staging")
    else:
        review_state = "staging"

    # Map review_state to human_review_status
    status_map = {
        "staging": "pending",
        "needs_review": "pending",
        "approved": "approved",
        "rejected": "rejected",
        "revision_requested": "revision_requested",
        "final": "approved",
    }

    state.outputs["human_review_status"] = status_map.get(review_state, "pending")
    state.outputs["review_state"] = review_state
    state.outputs["review_decisions_count"] = len(decisions)

    return state.mark("node_16_review")
