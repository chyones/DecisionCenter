"""Node 4 - Retrieval Plan. Spec: Section 16, Node 4."""

from apps.edr.graph.state import DecisionState


def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("retrieval_plan", ["sharepoint", "odoo"])
    return state.mark("node_04_plan")
