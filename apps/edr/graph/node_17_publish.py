"""Node 17 - Publish. Spec: Section 16, Node 17."""

from apps.edr.graph.state import DecisionState


def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("publish_status", "blocked_until_approval")
    return state.mark("node_17_publish")
