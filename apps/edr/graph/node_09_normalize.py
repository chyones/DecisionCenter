"""Node 9 - Normalize and Deduplicate. Spec: Sections 12 and 16."""

from apps.edr.graph.state import DecisionState


def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("evidence_count", len(state.evidence))
    return state.mark("node_09_normalize")
