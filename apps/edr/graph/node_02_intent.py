"""Node 2 - Intent Classifier. Spec: Section 16, Node 2."""

from apps.edr.graph.state import DecisionState


async def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("intent", "decision_report")
    return state.mark("node_02_intent")
