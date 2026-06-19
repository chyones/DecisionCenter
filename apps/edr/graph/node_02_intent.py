"""Node 2 — Intent Classifier. Spec: Section 16, Node 2.

Classifies the query into one or more intent categories using the light tier.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.edr.graph.intent import classify_report_type
from apps.edr.graph.state import DecisionState
from apps.edr.llm import call_llm

_PROMPT_PATH = Path(__file__).parents[1] / "prompts" / "intent_classifier.md"

_INTENT_CATEGORIES = [
    "budget_actual",
    "delay",
    "contract_risk",
    "claim",
    "procurement",
    "document_control",
    "payment",
    "variation",
    "general_project_status",
]


def _build_prompt(query: str) -> str:
    base = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""
    categories = "\n".join(f"- {c}" for c in _INTENT_CATEGORIES)
    return (
        f"{base}\n\n"
        f"Allowed categories:\n{categories}\n\n"
        f"Query: {query}\n\n"
        f"Return JSON only with this exact shape:\n"
        f'{{"intents": ["category1", "category2"]}}\n'
        f"Do not answer the question."
    )


async def run(state: DecisionState) -> DecisionState:
    prompt = _build_prompt(state.query)
    result = await call_llm(
        prompt=prompt,
        tier="light",
        request_id=state.request_id,
        node_name="node_02_intent",
        expect_json=True,
        max_tokens=2_000,
    )

    state.cost_accumulated_usd += result.cost_usd
    state.outputs["node_02_cost_usd"] = result.cost_usd

    intents: list[str] = ["general_project_status"]
    try:
        data = json.loads(result.content)
        raw = data.get("intents", [])
        if isinstance(raw, list):
            intents = [i for i in raw if isinstance(i, str)]
        elif isinstance(raw, str):
            intents = [raw]
    except Exception:
        pass

    # Ensure at least one valid intent
    if not intents:
        intents = ["general_project_status"]

    state.outputs["intent"] = intents
    state.outputs["report_type"] = classify_report_type(state.query)
    return state.mark("node_02_intent")
