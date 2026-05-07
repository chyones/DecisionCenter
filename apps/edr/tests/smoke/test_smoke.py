import asyncio

from apps.edr.graph.runner import NODE_COUNT, run_workflow
from apps.edr.graph.state import DecisionState


def test_workflow_has_18_nodes() -> None:
    assert NODE_COUNT == 18


def test_skeleton_workflow_visits_all_nodes() -> None:
    state = DecisionState(
        request_id="test",
        user_id="user",
        role="executive",
        project_code="PRJ-001",
        query="What is project status?",
    )
    result = asyncio.run(run_workflow(state))
    assert len(result.visited_nodes) == 18
    assert result.outputs["publish_status"] == "blocked_until_approval"
    assert result.outputs["rbac_status"] == "authorized"
