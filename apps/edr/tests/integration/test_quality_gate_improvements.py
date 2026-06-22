"""Block E tests — quality-gate improvements.

- Raw filenames are not accepted as analysis (findings/summary).
- document_search reports must not carry financial or management sections.
"""

from __future__ import annotations

from apps.edr.graph.node_13_quality_gate import (
    _check_intent_correctness,
    _check_irrelevant_sections,
    _check_raw_filename_findings,
)


def test_raw_filename_finding_flagged():
    report = {"key_findings": [{"text": "BOQ Revision 4.xlsx", "evidence_ids": ["e1"]}]}
    checks = _check_raw_filename_findings(report)
    assert any(c.claim_id.endswith(".raw_filename") and c.verdict == "needs_review" for c in checks)


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
    assert any(c.claim_id.endswith(".raw_filename") and c.verdict == "needs_review" for c in checks)


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
