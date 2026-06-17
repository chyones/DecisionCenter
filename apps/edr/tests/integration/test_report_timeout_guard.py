"""The synchronous /reports/staging request must return a controlled 504 when the
report workflow exceeds REPORT_SYNC_TIMEOUT_S, instead of being killed opaquely by
the reverse proxy. Smallest-safe-protection guard — no pipeline logic changes."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from apps.edr import app as appmod
from apps.edr.auth.validator import JWTClaims


@pytest.mark.anyio
async def test_stage_report_returns_504_when_workflow_exceeds_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(appmod, "REPORT_SYNC_TIMEOUT_S", 0.05)

    async def slow_workflow(state):  # never returns within the budget
        await asyncio.sleep(1.0)
        return state

    monkeypatch.setattr(appmod, "run_workflow", slow_workflow)

    # project_code=None skips the source-mapping DB check, isolating the guard.
    req = appmod.ReportRequest(
        user_id="u-1", query="give me one big problem", project_code=None,
        output_formats=["md", "docx", "xlsx", "pdf", "pptx"],
    )
    claims = JWTClaims(user_id="u-1", role="executive")

    with pytest.raises(HTTPException) as exc:
        await appmod.stage_report(req, claims)
    assert exc.value.status_code == 504
    assert "synchronous request budget" in exc.value.detail


@pytest.mark.anyio
async def test_stage_report_passes_through_when_workflow_is_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(appmod, "REPORT_SYNC_TIMEOUT_S", 5.0)

    class _Result:
        request_id = "r-1"
        visited_nodes = ["node_00_begin"]
        outputs = {"exported_reports": {"md": "k/r-1.md"}, "quality_gate": "passed"}

    async def fast_workflow(state):
        return _Result()

    monkeypatch.setattr(appmod, "run_workflow", fast_workflow)

    req = appmod.ReportRequest(
        user_id="u-1", query="q", project_code=None, output_formats=["md"],
    )
    claims = JWTClaims(user_id="u-1", role="executive")
    resp = await appmod.stage_report(req, claims)
    assert resp["request_id"] == "r-1"
    assert resp["exported_formats"] == ["md"]
