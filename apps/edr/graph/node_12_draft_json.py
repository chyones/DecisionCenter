"""Node 12 - Draft JSON Report. Spec: Sections 14 and 16."""

from apps.edr.graph.state import DecisionState


def run(state: DecisionState) -> DecisionState:
    state.outputs.setdefault("draft_report_status", "stubbed")
    return state.mark("node_12_draft_json")
