"""Node 8 - Odoo Facts Retrieval. Spec: Sections 4.4 and 16."""

from apps.edr.graph.state import DecisionState


async def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("odoo_status", "stubbed")
    return state.mark("node_08_odoo")
