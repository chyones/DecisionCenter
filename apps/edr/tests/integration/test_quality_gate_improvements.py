"""Block E tests — quality-gate improvements.

- Raw filenames are not accepted as analysis (findings/summary).
- document_search reports must not carry financial or management sections.
"""

from __future__ import annotations

import asyncio

from apps.edr.graph.node_13_quality_gate import (
    _check_intent_correctness,
    _check_irrelevant_sections,
    _check_raw_filename_findings,
    run,
)
from apps.edr.graph.state import DecisionState


def test_raw_filename_finding_flagged():
    report = {"key_findings": [{"text": "BOQ Revision 4.xlsx", "evidence_ids": ["e1"]}]}
    checks = _check_raw_filename_findings(report)
    assert any(c.claim_id.endswith(".raw_filename") and c.verdict == "unsupported" for c in checks)


def test_synthesized_finding_not_flagged():
    report = {
        "key_findings": [
            {"text": "Four successive BOQ revisions indicate ongoing scope changes.", "evidence_ids": ["e1"]}
        ]
    }
    assert _check_raw_filename_findings(report) == []


def test_embedded_filename_in_finding_is_flagged():
    # A finding that embeds a filename (even if "framed") is not analysis -> flagged.
    report = {
        "key_findings": [
            {"text": "Retrieved sharepoint evidence pending analyst review: BOQ Revision 4.xlsx", "evidence_ids": ["e1"]}
        ]
    }
    checks = _check_raw_filename_findings(report)
    assert any(c.claim_id.endswith(".raw_filename") and c.verdict == "unsupported" for c in checks)


def test_raw_filename_in_visible_body_fails_quality_gate():
    state = DecisionState(
        request_id="r",
        user_id="u",
        query="تقرير عن مصاريف المشروع",
        role="executive",
        project_code="PRJ-001",
        evidence=[
            {
                "evidence_id": "ev_sp_1",
                "source_type": "sharepoint",
                "source_uri": "sp://boq",
                "title": "BOQ Revision 4.xlsx",
                "excerpt": "BOQ Revision 4.xlsx",
                "hash_sha256": "a" * 64,
                "confidence": "medium",
            }
        ],
        report_json={
            "request_id": "r",
            "report_type": "financial",
            "project_identity": {
                "project_code": "PRJ-001",
                "project_name": "Civil Defense building",
                "identity_source": "approved project registry",
                "identity_confidence": "verified",
            },
            "executive_summary": [
                {"claim": "Financial evidence reviewed.", "evidence_ids": ["ev_sp_1"], "confidence": "medium"}
            ],
            "financial_snapshot": {
                "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
                "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
            },
            "key_findings": [
                {"text": "BOQ Revision 4.xlsx", "evidence_ids": ["ev_sp_1"], "confidence": "medium"}
            ],
            "root_causes": [],
            "delay_analysis": [],
            "contractual_implications": [],
            "recommended_actions": [],
            "missing_data": [],
            "conflicts": [],
            "sources": [],
        },
    )
    result = asyncio.run(run(state))
    assert result.outputs["quality_gate"] == "failed"


def test_framed_text_without_filename_not_flagged():
    report = {
        "key_findings": [
            {"text": "Synthesis pending analyst review of the retrieved project documents.", "evidence_ids": ["e1"]}
        ]
    }
    assert _check_raw_filename_findings(report) == []


def test_document_search_financial_section_flagged():
    report = {
        "report_type": "document_search",
        "financial_snapshot": {"contract_value": {"status": "available", "value": 1.0, "evidence_id": "e1"}},
    }
    checks = _check_irrelevant_sections(report, "find the drawing document")
    assert any(c.claim_id == "intent.irrelevant_sections" for c in checks)


def test_document_search_mqa_flagged():
    report = {
        "report_type": "document_search",
        "management_question_answer": {"executive_answer": "The biggest problem is X"},
    }
    checks = _check_intent_correctness(report, "find the drawing document")
    assert any(c.claim_id == "intent.management_question_answer" for c in checks)


def test_document_search_clean_no_flags():
    report = {
        "report_type": "document_search",
        "financial_snapshot": {},
        "management_question_answer": {},
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
    }
    assert _check_irrelevant_sections(report, "find the drawing document") == []
    assert _check_intent_correctness(report, "find the drawing document") == []
