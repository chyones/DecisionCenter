"""Node 3 — Scope Resolver. Spec: Section 16, Node 3.

Extracts structured scope from the query using the light tier.
"""

from __future__ import annotations

import json

from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm


def _build_prompt(query: str, inputs: dict) -> str:
    return (
        "You are a scope extractor for a construction-project decision-support system.\n"
        "Extract the following fields from the query.\n"
        "If a field is missing, set it to null and add the field name to 'missing'.\n"
        "Do not guess or invent values.\n\n"
        "Fields:\n"
        "- project_code\n"
        "- contract_no\n"
        "- vendor\n"
        "- date_range\n"
        "- document_type\n"
        "- mailbox_scope\n\n"
        f"Query: {query}\n\n"
        "Return JSON only with this exact shape:\n"
        '{\n'
        '  "project_code": "string or null",\n'
        '  "contract_no": "string or null",\n'
        '  "vendor": "string or null",\n'
        '  "date_range": "string or null",\n'
        '  "document_type": "string or null",\n'
        '  "mailbox_scope": "string or null",\n'
        '  "missing": ["field_name"]\n'
        "}\n"
    )


async def run(state: DecisionState) -> DecisionState:
    prompt = _build_prompt(state.query, state.inputs)
    result = await call_llm(
        prompt=prompt,
        tier="light",
        request_id=state.request_id,
        node_name="node_03_scope",
        expect_json=True,
        max_tokens=2_000,
    )

    state.cost_accumulated_usd += result.cost_usd
    state.outputs["node_03_cost_usd"] = result.cost_usd

    scope: dict = {"missing": []}
    try:
        scope = json.loads(result.content)
        if not isinstance(scope, dict):
            scope = {"missing": []}
    except Exception:
        pass

    # Merge with any explicit inputs already provided by the API layer
    for key in ("project_code", "contract_no", "vendor", "date_range", "document_type", "mailbox_scope"):
        if state.inputs.get(key) and not scope.get(key):
            scope[key] = state.inputs[key]

    state.outputs["scope"] = scope
    return state.mark("node_03_scope")
