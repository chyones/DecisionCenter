"""Node 1 - Auth and RBAC Gate. Spec: Sections 8, 9, and 16."""

from apps.edr.graph.state import DecisionState


def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("rbac_status", "stubbed")
    return state.mark("node_01_auth")
