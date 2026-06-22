"""Regression tests for Project Identity Contract and salary/payroll intent handling.

These tests verify the fixes for the human-rejected salary report:
- salary/payroll queries are classified as data-report, not management questions
- availability reports contain verified project identity and no fabricated table
- timeouts are surfaced as inconclusive, never as "no data"
- high-confidence claims are capped when evidence is partial/timeouts exist
"""

from __future__ import annotations

import pytest

from apps.edr.graph import coverage
from apps.edr.graph.intent import (
    classify_report_type,
    is_management_question,
    is_salary_payroll_query,
)
from apps.edr.graph.node_12_draft_json import run
from apps.edr.graph.node_13_quality_gate import run as qg_run
from apps.edr.graph.project_identity import ProjectIdentity, resolve_project_identity
from apps.edr.graph.state import DecisionState


SALARY_QUERY = "give me salary report by staff name and file id for this project"
MGMT_QUERY = "what is the biggest problem for this project"
DATA_QUERY = "give me a table of all log entries by id for this project"


def _make_state(query: str, project_code: str = "PRJ-001") -> DecisionState:
    return DecisionState(
        request_id="req-salary-001",
        user_id="user-001",
        query=query,
        role="executive",
        project_code=project_code,
        allowed_projects=[project_code],
        evidence=[
            {
                "evidence_id": "ev_sp_001",
                "source_type": "sharepoint",
                "title": "Project Progress Report June 2026",
                "excerpt": "Overall progress is on track with no salary data.",
                "source_uri": "https://sharepoint.example.com/progress.pdf",
                "confidence": "medium",
            },
            {
                "evidence_id": "ev_odoo_001",
                "source_type": "odoo",
                "title": "Construction of Civil Defense building in Al Marfa",
                "excerpt": "Project record for PRJ-001.",
                "source_uri": "https://erp.elrace.com/web#id=1&model=project.project",
                "confidence": "high",
            },
        ],
    )


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


def test_salary_query_classified_as_salary_payroll():
    assert classify_report_type(SALARY_QUERY) == "salary_payroll"
    assert is_salary_payroll_query(SALARY_QUERY)
    assert not is_management_question(SALARY_QUERY)


def test_management_query_classified_as_management_question():
    assert classify_report_type(MGMT_QUERY) == "management_question"
    assert is_management_question(MGMT_QUERY)
    assert not is_salary_payroll_query(MGMT_QUERY)


def test_data_query_classified_as_data_report():
    assert classify_report_type(DATA_QUERY) == "data_report"


# ---------------------------------------------------------------------------
# Project identity resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_project_identity_uses_verified_mapping():
    state = _make_state(SALARY_QUERY)
    identity = resolve_project_identity(state)
    assert identity.project_code == "PRJ-001"
    assert "Civil Defense building" in identity.project_name
    assert identity.identity_confidence in ("verified", "partial")


# ---------------------------------------------------------------------------
# Salary availability report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_salary_availability_report_is_generated_without_llm():
    state = _make_state(SALARY_QUERY)
    # Record coverage so the availability report can describe what was checked.
    coverage.record(
        state,
        "sharepoint",
        enabled=True,
        attempted=True,
        status="zero_no_match",
        evidence_count=1,
        reason="No salary records matched.",
    )
    coverage.record(
        state,
        "odoo",
        enabled=True,
        attempted=True,
        status="timeout",
        evidence_count=0,
        reason="Odoo retrieval exceeded 50s budget.",
    )
    coverage.record(
        state,
        "email",
        enabled=True,
        attempted=True,
        status="zero_no_match",
        evidence_count=0,
        reason="No salary records matched.",
    )

    state = await run(state)

    report = state.report_json
    assert report is not None
    assert report["report_type"] == "salary_payroll"
    assert report["project_identity"]["project_code"] == "PRJ-001"
    assert "Civil Defense building" in report["project_identity"]["project_name"]

    # No fabricated staff/file-id/salary table and no management-decision framing.
    mqa = report.get("management_question_answer") or {}
    assert not (mqa.get("executive_answer") or "").strip()
    assert report.get("root_causes") == []
    assert report.get("delay_analysis") == []
    assert report.get("contractual_implications") == []

    # Timed-out source reported as inconclusive, never "no data".
    missing_text = " ".join(report.get("missing_data", [])).lower()
    assert "timeout" in missing_text or "inconclusive" in missing_text
    assert "no data" not in missing_text
    assert "empty" not in missing_text

    # Required data / next steps are present.
    assert report.get("what_was_checked")
    assert report.get("required_data")


@pytest.mark.asyncio
async def test_salary_availability_report_qg_does_not_fail():
    state = _make_state(SALARY_QUERY)
    coverage.record(
        state,
        "sharepoint",
        enabled=True,
        attempted=True,
        status="zero_no_match",
        evidence_count=1,
        reason="No salary records matched.",
    )
    coverage.record(
        state,
        "odoo",
        enabled=True,
        attempted=True,
        status="timeout",
        evidence_count=0,
        reason="Odoo retrieval exceeded 50s budget.",
    )
    coverage.record(
        state,
        "email",
        enabled=True,
        attempted=True,
        status="zero_no_match",
        evidence_count=0,
        reason="No salary records matched.",
    )

    state = await run(state)
    state = await qg_run(state)

    assert state.outputs["quality_gate"] in ("passed", "needs_review")


# ---------------------------------------------------------------------------
# Quality gate intent/confidence rules
# ---------------------------------------------------------------------------


def _fake_report(report_type: str, mqa_answer: str = "", high_confidence: bool = False) -> dict:
    claim_conf = "high" if high_confidence else "low"
    return {
        "report_type": report_type,
        "project_identity": ProjectIdentity(
            project_code="PRJ-001",
            project_name="Test Project",
            identity_source="approved project registry",
            identity_confidence="verified",
        ).to_dict(),
        "executive_summary": [
            {"claim": "Summary", "evidence_ids": ["ev_1"], "confidence": claim_conf}
        ],
        "key_findings": [{"text": "Finding", "evidence_ids": ["ev_1"], "confidence": claim_conf}],
        "financial_snapshot": {
            "budget": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "actual_cost": {
                "value": None,
                "currency": "AED",
                "evidence_id": None,
                "status": "not_available",
            },
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "management_question_answer": {
            "executive_answer": mqa_answer,
            "why_biggest_problem": ["a", "b", "c"] if mqa_answer else [],
            "evidence_used": [],
            "business_impact": {
                "schedule_impact": "s",
                "cost_commercial_impact": "c",
                "operational_client_impact": "o",
            },
            "decision_required": "d" if mqa_answer else "",
            "recommended_action": {"specific_action": "a", "owner_role": "o", "timeframe": "t"}
            if mqa_answer
            else {},
            "risks_if_no_action": "r" if mqa_answer else "",
            "confidence": "high" if mqa_answer else "low",
            "missing_evidence_or_assumptions": "",
        },
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }


@pytest.mark.asyncio
async def test_qg_flags_mqa_on_salary_report():
    state = _make_state(SALARY_QUERY)
    state.report_json = _fake_report("salary_payroll", mqa_answer="The biggest problem is delay.")
    state = await qg_run(state)

    checks = state.outputs["quality_gate_result"]["checks"]
    intent_checks = [c for c in checks if c["claim_id"].startswith("intent.")]
    assert any(c["claim_id"] == "intent.management_question_answer" for c in intent_checks)


@pytest.mark.asyncio
async def test_qg_caps_high_confidence_when_timeout():
    state = _make_state(SALARY_QUERY)
    coverage.record(
        state,
        "odoo",
        enabled=True,
        attempted=True,
        status="timeout",
        evidence_count=0,
        reason="Odoo retrieval exceeded 50s budget.",
    )
    state.report_json = _fake_report(
        "management_question", mqa_answer="Problem", high_confidence=True
    )
    state = await qg_run(state)

    checks = {c["claim_id"]: c for c in state.outputs["quality_gate_result"]["checks"]}
    assert checks["confidence.cap_high_confidence"]["verdict"] == "needs_review"


@pytest.mark.asyncio
async def test_qg_rejects_no_data_for_timeout():
    state = _make_state(SALARY_QUERY)
    coverage.record(
        state,
        "odoo",
        enabled=True,
        attempted=True,
        status="timeout",
        evidence_count=0,
        reason="Odoo retrieval exceeded 50s budget.",
    )
    report = _fake_report("salary_payroll")
    report["missing_data"] = ["odoo: no data available"]
    state.report_json = report
    state = await qg_run(state)

    checks = {c["claim_id"]: c for c in state.outputs["quality_gate_result"]["checks"]}
    assert checks["semantics.timeout_as_no_data"]["verdict"] == "needs_review"
