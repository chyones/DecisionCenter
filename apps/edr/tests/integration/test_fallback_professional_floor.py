"""Slice 2b/2c regression tests — deterministic fallback stays professional.

When no LLM synthesis is available, the fallback builders must NOT present raw
excerpts or filenames as conclusions ("the most prominent issue is: BOQ Rev4.xlsx").
They must state honestly that synthesis did not complete, keep evidence cited,
and the salary availability report must list the sources it actually checked.
"""

from __future__ import annotations

from apps.edr.graph import coverage
from apps.edr.graph.node_12_draft_json import (
    _build_report_from_evidence,
    _build_salary_availability_report,
    _enrich_management_question_answer,
)
from apps.edr.graph.project_identity import resolve_project_identity
from apps.edr.graph.state import DecisionState

_DOC_EV = {
    "evidence_id": "ev_sp_1",
    "source_type": "sharepoint",
    "title": "BOQ Revision 4.xlsx",
    "excerpt": "BOQ Revision 4 structural works Q1 2026",
    "source_uri": "https://sp/boq4.xlsx",
    "confidence": "medium",
}


def _state(query: str, evidence: list[dict]) -> DecisionState:
    return DecisionState(
        request_id="r",
        user_id="u",
        query=query,
        role="executive",
        project_code="PRJ-001",
        allowed_projects=["PRJ-001"],
        evidence=evidence,
    )


def test_fallback_summary_does_not_present_raw_evidence_as_conclusion():
    s = _state("what is the biggest problem for this project", [dict(_DOC_EV)])
    rep = _build_report_from_evidence(s, resolve_project_identity(s))
    _enrich_management_question_answer(rep, s)

    claim = rep["executive_summary"][0]["claim"]
    assert "could not be completed" in claim
    assert "BOQ Revision 4.xlsx" not in claim
    assert "most prominent issue is:" not in claim.lower()
    assert rep["executive_summary"][0]["evidence_ids"] == ["ev_sp_1"]

    mqa = rep["management_question_answer"]
    assert "could not be completed" in mqa["executive_answer"]
    assert "BOQ Revision 4.xlsx" not in mqa["executive_answer"]
    assert not any("BOQ" in b for b in mqa["why_biggest_problem"])


def test_fallback_key_findings_are_neutral_not_raw_excerpt():
    s = _state("status", [dict(_DOC_EV)])
    rep = _build_report_from_evidence(s, resolve_project_identity(s))
    kf = rep["key_findings"][0]
    assert kf["text"].startswith("Retrieved sharepoint evidence")
    assert kf["confidence"] == "low"
    assert kf["evidence_ids"] == ["ev_sp_1"]


def test_salary_availability_report_cites_checked_sources():
    s = _state("give me salary report by staff name and file id", [dict(_DOC_EV)])
    for src in ("sharepoint", "odoo", "email"):
        coverage.record(
            s, src, enabled=True, attempted=True, status="zero_no_match",
            evidence_count=(1 if src == "sharepoint" else 0), reason="no match",
        )
    rep = _build_salary_availability_report(s, resolve_project_identity(s))
    assert rep["sources"], "salary availability report must cite the evidence it checked"
    assert rep["sources"][0]["source_id"] == "ev_sp_1"
