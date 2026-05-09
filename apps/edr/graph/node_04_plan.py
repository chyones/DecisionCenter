"""Node 4 — Retrieval Plan. Spec: Section 16, Node 4.

Decides which sources to query and records a reason per source.
"""

from __future__ import annotations

import json

from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm


def _build_prompt(query: str, intents: list[str], scope: dict) -> str:
    return (
        "You are a retrieval planner for a construction-project decision-support system.\n"
        "Decide which data sources to query based on the user's intent and scope.\n"
        "Available sources: sharepoint, owncloud, email, odoo, cad.\n"
        "CAD is disabled by default; only include it if the query explicitly asks for drawings.\n"
        "Record a concise reason for each selected source.\n\n"
        f"Query: {query}\n"
        f"Intents: {intents}\n"
        f"Scope: {scope}\n\n"
        "Return JSON only with this exact shape:\n"
        '{\n'
        '  "sources": ["sharepoint", "odoo"],\n'
        '  "reason": "string explaining the plan"\n'
        "}\n"
    )


async def run(state: DecisionState) -> DecisionState:
    intents = state.outputs.get("intent", ["general_project_status"])
    scope = state.outputs.get("scope", {})
    prompt = _build_prompt(state.query, intents, scope)

    result = await call_llm(
        prompt=prompt,
        tier="light",
        request_id=state.request_id,
        node_name="node_04_plan",
        expect_json=True,
        max_tokens=2_000,
    )

    state.cost_accumulated_usd += result.cost_usd
    state.outputs["node_04_cost_usd"] = result.cost_usd

    plan: dict = {"sources": ["sharepoint", "odoo"], "reason": "Fallback plan"}
    try:
        parsed = json.loads(result.content)
        if isinstance(parsed, dict):
            plan = parsed
    except Exception:
        pass

    # Normalize sources to a list of strings
    raw_sources = plan.get("sources", [])
    if isinstance(raw_sources, str):
        sources = [raw_sources]
    elif isinstance(raw_sources, list):
        sources = [s for s in raw_sources if isinstance(s, str)]
    else:
        sources = ["sharepoint", "odoo"]

    # Enforce CAD disabled by default (spec Section 4.5)
    if "cad" in sources:
        if "drawing" not in state.query.lower() and "cad" not in state.query.lower():
            sources.remove("cad")

    plan["sources"] = sources
    state.outputs["retrieval_plan"] = plan
    return state.mark("node_04_plan")
