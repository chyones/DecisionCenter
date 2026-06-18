import logging

import pytest

from apps.edr.graph import runner
from apps.edr.graph.state import DecisionState


@pytest.mark.asyncio
async def test_run_workflow_logs_stage_timing(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    async def fake_node(state: DecisionState) -> DecisionState:
        return state.mark("fake_node")

    monkeypatch.setattr(runner, "NODES", (fake_node,))
    state = DecisionState(request_id="r-timing", user_id="u-1", query="q")

    caplog.set_level(logging.INFO, logger="apps.edr.graph.runner")

    result = await runner.run_workflow(state)

    assert result.visited_nodes == ["fake_node"]
    messages = [record.getMessage() for record in caplog.records]
    assert any("workflow_stage_start request_id=r-timing" in msg for msg in messages)
    assert any("workflow_stage_end request_id=r-timing" in msg for msg in messages)
