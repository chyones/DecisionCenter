"""Load test integration tests."""

from __future__ import annotations

import pytest

from apps.edr.evaluation.load_test import _run_load, _run_single, _warmup


@pytest.mark.asyncio
async def test_run_single_completes_workflow() -> None:
    result = await _run_single("lt-001", "Project status?", "PRJ-001")
    assert result["error"] is None
    assert result["visited_nodes"] == 18
    assert result["rbac_status"] == "authorized"


@pytest.mark.asyncio
async def test_run_single_records_duration() -> None:
    result = await _run_single("lt-002", "Budget?", "PRJ-001")
    assert result["duration_ms"] > 0


@pytest.mark.asyncio
async def test_warmup_runs_without_error() -> None:
    await _warmup()


@pytest.mark.asyncio
async def test_run_load_respects_concurrency() -> None:
    results = await _run_load(concurrency=2, total=4)
    assert len(results) == 4
    for r in results:
        assert r["error"] is None
        assert r["visited_nodes"] == 18


@pytest.mark.asyncio
async def test_run_load_with_different_project() -> None:
    results = await _run_load(concurrency=1, total=2)
    assert len(results) == 2
    for r in results:
        assert r["error"] is None
