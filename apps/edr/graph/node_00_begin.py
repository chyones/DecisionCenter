"""Node 0 - Begin. Spec: Section 16, Node 0."""

from apps.edr.graph.state import DecisionState


async def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("phase", "read_only")
    return state.mark("node_00_begin")
