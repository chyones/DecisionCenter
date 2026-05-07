"""Node 3 - Scope Resolver. Spec: Section 16, Node 3."""

from apps.edr.graph.state import DecisionState


async def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("scope", state.inputs)
    return state.mark("node_03_scope")
