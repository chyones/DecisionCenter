"""Node 13 - Quality Gate. Spec: Sections 15, 17, and 16."""

from apps.edr.graph.state import DecisionState


async def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("quality_gate", "needs_review")
    return state.mark("node_13_quality_gate")
