"""Evaluation runner tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.edr.evaluation.run import (
    _build_state,
    _compute_metrics,
    _load_cases,
    _resolve,
    _run_case,
)
from apps.edr.graph.state import DecisionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case(
    case_id: str = "test-001",
    category: str = "test",
    node: str = "node_13_quality_gate",
    state: dict | None = None,
    expect: dict | None = None,
    expect_error: bool | str | None = None,
) -> dict:
    case: dict = {
        "id": case_id,
        "category": category,
        "description": "Test case",
        "node": node,
        "state": state or {
            "request_id": "test-001",
            "user_id": "u-1",
            "role": "executive",
            "project_code": "PRJ-001",
            "query": "test",
        },
        "expect": expect or {},
    }
    if expect_error is not None:
        case["expect_error"] = expect_error
    return case


# ---------------------------------------------------------------------------
# State construction
# ---------------------------------------------------------------------------


def test_build_state_basic() -> None:
    case = _make_case(state={"request_id": "r1", "user_id": "u1", "query": "q"})
    state = _build_state(case)
    assert state.request_id == "r1"
    assert state.user_id == "u1"
    assert state.query == "q"


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------


def test_resolve_outputs() -> None:
    state = DecisionState(request_id="r1", user_id="u1", query="q")
    state.outputs["quality_gate"] = "passed"
    assert _resolve(state, "outputs.quality_gate") == "passed"
    assert _resolve(state, "quality_gate") == "passed"


def test_resolve_visited_nodes_count() -> None:
    state = DecisionState(request_id="r1", user_id="u1", query="q")
    state.visited_nodes = ["a", "b", "c"]
    assert _resolve(state, "visited_nodes_count") == 3


# ---------------------------------------------------------------------------
# Load cases
# ---------------------------------------------------------------------------


def test_load_cases_reads_jsonl(tmp_path: Path) -> None:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "a.jsonl").write_text(
        json.dumps({"id": "1", "category": "c1"}) + "\n"
        + json.dumps({"id": "2", "category": "c2"}) + "\n",
        encoding="utf-8",
    )
    cases = _load_cases(suite)
    assert len(cases) == 2
    assert cases[0]["id"] == "1"


# ---------------------------------------------------------------------------
# Run case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_case_qg_pass() -> None:
    case = _make_case(
        state={
            "request_id": "r1",
            "user_id": "u1",
            "role": "executive",
            "project_code": "PRJ-001",
            "query": "test",
            "evidence": [
                {
                    "evidence_id": "ev_001",
                    "source_type": "odoo",
                    "source_uri": "odoo://1",
                    "title": "Budget",
                    "excerpt": "1M",
                    "hash_sha256": "a" * 64,
                    "confidence": "high",
                }
            ],
            "report_json": {
                "request_id": "r1",
                "executive_summary": [
                    {"claim": "Budget is 1M.", "evidence_ids": ["ev_001"], "confidence": "high"}
                ],
                "financial_snapshot": {
                    "budget": {
                        "value": 1000000,
                        "currency": "AED",
                        "evidence_id": "ev_001",
                        "status": "available",
                    },
                    "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                    "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
                },
                "key_findings": [],
                "root_causes": [],
                "delay_analysis": [],
                "contractual_implications": [],
                "recommended_actions": [],
                "missing_data": [],
                "conflicts": [],
                "sources": [],
            },
        },
        expect={"quality_gate": "passed"},
    )
    result = await _run_case(case)
    assert result["passed"] is True
    assert result["error"] is None


@pytest.mark.asyncio
async def test_run_case_qg_fail_missing_evidence() -> None:
    case = _make_case(
        state={
            "request_id": "r1",
            "user_id": "u1",
            "role": "executive",
            "project_code": "PRJ-001",
            "query": "test",
            "evidence": [],
            "report_json": {
                "request_id": "r1",
                "executive_summary": [
                    {"claim": "Something.", "evidence_ids": [], "confidence": "medium"}
                ],
                "financial_snapshot": {
                    "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                    "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                    "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
                },
                "key_findings": [],
                "root_causes": [],
                "delay_analysis": [],
                "contractual_implications": [],
                "recommended_actions": [],
                "missing_data": [],
                "conflicts": [],
                "sources": [],
            },
        },
        expect={"quality_gate": "failed"},
    )
    result = await _run_case(case)
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_run_case_workflow_end_to_end() -> None:
    case = _make_case(
        node="workflow",
        state={
            "request_id": "e2e-1",
            "user_id": "u1",
            "role": "executive",
            "project_code": "PRJ-001",
            "query": "What is the project status?",
        },
        expect={"visited_nodes_count": 18, "outputs.rbac_status": "authorized"},
    )
    result = await _run_case(case)
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_run_case_unauthorized_project() -> None:
    case = _make_case(
        node="node_01_auth",
        state={
            "request_id": "r1",
            "user_id": "u1",
            "role": "executive",
            "project_code": "PRJ-UNKNOWN",
            "query": "test",
            "allowed_projects": ["PRJ-001"],
        },
        expect_error="RbacDeniedError",
    )
    result = await _run_case(case)
    assert result["passed"] is True
    assert "RbacDeniedError" in (result.get("error") or "")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_compute_metrics_all_pass() -> None:
    results = [
        {"id": "1", "category": "cat_a", "passed": True, "error": None, "failures": []},
        {"id": "2", "category": "cat_a", "passed": True, "error": None, "failures": []},
    ]
    metrics = _compute_metrics(results)
    assert metrics["total"] == 2
    assert metrics["passed"] == 2
    assert metrics["pass_rate"] == 1.0


def test_compute_metrics_with_unauthorized() -> None:
    results = [
        {"id": "1", "category": "unauthorized_project", "passed": False, "error": None, "failures": []},
        {"id": "2", "category": "unauthorized_mailbox", "passed": False, "error": None, "failures": []},
        {"id": "3", "category": "budget", "passed": True, "error": None, "failures": []},
    ]
    metrics = _compute_metrics(results)
    assert metrics["refusal_accuracy"] == 1.0
