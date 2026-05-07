"""Node 10 - Evidence Sufficiency Check. Spec: Section 16, Node 10."""

from collections import Counter

from apps.edr.graph.state import DecisionState

_FINANCIAL_KEYWORDS = {
    "budget",
    "cost",
    "payment",
    "invoice",
    "contract value",
    "actual cost",
}


async def run(state: DecisionState) -> DecisionState:
    evidence = state.evidence
    counts = Counter(str(e.get("source_type", "unknown")) for e in evidence)

    query_lower = state.query.lower()
    is_financial = any(kw in query_lower for kw in _FINANCIAL_KEYWORDS)
    has_odoo = counts.get("odoo", 0) > 0

    missing: list[str] = []
    if is_financial and not has_odoo:
        missing.append("odoo")

    if missing:
        sufficiency = "insufficient"
    elif len(evidence) == 0:
        sufficiency = "insufficient"
    else:
        sufficiency = "sufficient"

    source_type_count = len(counts)
    complexity = "high" if source_type_count > 3 and len(evidence) > 20 else "normal"

    state.outputs["evidence_sufficiency"] = sufficiency
    state.outputs["missing_source"] = missing
    state.outputs["evidence_by_source"] = dict(counts)
    state.outputs["complexity"] = complexity

    return state.mark("node_10_sufficiency")
