"""Node 11 — Self-Correction Loop. Spec: Section 16, Node 11.

Performs bounded self-correction (max 3 loops) inside the linear runner.
When evidence is insufficient, the node generates a corrective plan and
attempts one targeted re-retrieval before yielding.
"""

from __future__ import annotations

import json

from apps.edr.connectors.odoo import read_odoo
from apps.edr.connectors.sharepoint import search_sharepoint
from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm
from apps.edr.rbac.project_mapping import ProjectMapping

_MAX_LOOPS = 3


def _build_prompt(state: DecisionState) -> str:
    missing = state.outputs.get("missing_source", [])
    sufficiency = state.outputs.get("evidence_sufficiency", "unknown")
    evidence_count = len(state.evidence)
    return (
        "You are a self-correction planner for a construction-project decision-support system.\n"
        "Evidence sufficiency check returned the following:\n"
        f"- Sufficiency: {sufficiency}\n"
        f"- Missing sources: {missing}\n"
        f"- Current evidence count: {evidence_count}\n"
        f"- Original query: {state.query}\n"
        f"- Loop number: {state.loop_count + 1} / {_MAX_LOOPS}\n\n"
        "Allowed corrective actions:\n"
        "- partial re-retrieval\n"
        "- narrowed query\n"
        "- different keyword set\n"
        "- source retry\n\n"
        "Return JSON only with this exact shape:\n"
        '{\n'
        '  "action": "retry_with_narrowed_query | source_retry | stop",\n'
        '  "new_query": "string or null",\n'
        '  "target_sources": ["sharepoint", "odoo", "email", "owncloud"],\n'
        '  "reason": "string"\n'
        "}\n"
    )


async def _try_retrieval(state: DecisionState, plan: dict) -> int:
    """Attempt one targeted re-retrieval based on the corrective plan.

    Returns the number of new evidence items added.
    """
    targets = plan.get("target_sources", [])
    new_count = 0

    if "sharepoint" in targets and state.project_code:
        try:
            mapping = ProjectMapping.load().get(state.project_code)
            sp_config = mapping.get("sharepoint", {})
            payload = {
                "query": plan.get("new_query") or state.query,
                "project_code": state.project_code,
                "site_id": sp_config.get("site_id"),
                "drive_id": sp_config.get("drive_id"),
                "access_token": "",
            }
            evidence = await search_sharepoint(payload)
            state.evidence.extend([e.model_dump() for e in evidence])
            new_count += len(evidence)
        except Exception:
            pass

    if "odoo" in targets and state.project_code:
        try:
            mapping = ProjectMapping.load().get(state.project_code)
            odoo_config = mapping.get("odoo", {})
            import json as _json

            odoo_project_id = odoo_config.get("project_external_id") or state.project_code
            domain = _json.dumps([["project_external_id", "=", odoo_project_id]])
            fields = _json.dumps(["name", "budget", "actual_cost"])
            payload = {
                "project_code": state.project_code,
                "model": odoo_config.get("project_model", "project.project"),
                "domain": domain,
                "fields": fields,
                "allowed_odoo_ids": state.allowed_odoo_ids,
            }
            evidence = await read_odoo(payload)
            state.evidence.extend([e.model_dump() for e in evidence])
            new_count += len(evidence)
        except Exception:
            pass

    return new_count


async def run(state: DecisionState) -> DecisionState:
    loops = state.loop_count
    sufficiency = state.outputs.get("evidence_sufficiency", "unknown")

    # Hard stop if budget reached
    if loops >= _MAX_LOOPS:
        state.outputs["self_correction_status"] = "stopped_max_loops"
        state.outputs["self_correction_loops"] = loops
        return state.mark("node_11_self_correct")

    if sufficiency == "sufficient":
        state.outputs["self_correction_status"] = "not_needed"
        state.outputs["self_correction_loops"] = loops
        return state.mark("node_11_self_correct")

    # Generate corrective plan using light LLM
    prompt = _build_prompt(state)
    result = await call_llm(
        prompt=prompt,
        tier="light",
        request_id=state.request_id,
        node_name="node_11_self_correct",
        expect_json=True,
        max_tokens=2_000,
    )

    state.cost_accumulated_usd += result.cost_usd
    state.outputs["node_11_cost_usd"] = result.cost_usd

    plan: dict = {"action": "stop", "new_query": None, "target_sources": [], "reason": ""}
    try:
        parsed = json.loads(result.content)
        if isinstance(parsed, dict):
            plan = parsed
    except Exception:
        pass

    action = plan.get("action", "stop")
    if action == "stop" or loops >= _MAX_LOOPS - 1:
        state.outputs["self_correction_status"] = "stopped"
        state.outputs["self_correction_loops"] = loops + 1
        state.loop_count = loops + 1
        return state.mark("node_11_self_correct")

    # Attempt one re-retrieval
    try:
        added = await _try_retrieval(state, plan)
    except Exception:
        added = 0

    state.loop_count = loops + 1
    state.outputs["self_correction_loops"] = state.loop_count
    state.outputs["self_correction_status"] = "retried"
    state.outputs["self_correction_added"] = added
    state.outputs["self_correction_plan"] = plan

    return state.mark("node_11_self_correct")
