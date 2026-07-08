"""Slice 2 regression tests — markdown section numbering is contiguous.

Previously the renderer hard-coded section numbers (## 1 .. ## 11). When a
report type suppressed Root Causes / Delay / Contractual (salary, data reports),
the remaining sections kept their literal numbers and the document jumped 3 -> 7.
These tests lock contiguous numbering for every report type.
"""

from __future__ import annotations

import re

from apps.edr.exporters.markdown import to_markdown

_HEADING_NO = re.compile(r"^## (\d+)\. ", re.MULTILINE)


def _numbered(md: str) -> list[int]:
    return [int(n) for n in _HEADING_NO.findall(md)]


def _base_report(report_type: str) -> dict:
    return {
        "request_id": "r1",
        "project_code": "PRJ-001",
        "project_identity": {"project_name": "Test Project", "project_code": "PRJ-001"},
        "query": "q",
        "report_type": report_type,
        "executive_summary": [{"claim": "x", "evidence_ids": ["e1"], "confidence": "low"}],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [{"text": "f", "evidence_ids": ["e1"], "confidence": "low"}],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "conflicts": [],
        "missing_data": [],
        "sources": [],
        "connector_coverage": [],
        "quality_gate_status": "passed",
    }


def test_full_report_numbered_contiguously_no_gaps():
    md = to_markdown(_base_report("general_project_status"))
    nums = _numbered(md)
    # Executive-first layout: empty sections are suppressed entirely, so this
    # minimal fixture renders exec summary(1), financial snapshot(2), key
    # findings(3) — contiguous, with the pipeline metadata in the governance
    # appendix rather than numbered body sections.
    assert nums == [1, 2, 3], nums
    assert "## 1. Executive Summary" in md
    assert "## 2. Financial Snapshot — Odoo" in md
    assert "## 3. Key Findings" in md
    # Empty sections never render placeholder filler.
    assert "Recommended Actions" not in md
    assert "Conflicting Evidence" not in md
    assert "_No recommended actions._" not in md
    # Plumbing lives in the governance appendix, after the body.
    assert "## Appendix — Report Governance" in md
    assert md.index("## 1. Executive Summary") < md.index("## Appendix — Report Governance")
    assert "Quality Gate Status" not in md  # no numbered QG body section


def test_data_report_has_no_numbering_gap():
    md = to_markdown(_base_report("data_report"))
    nums = _numbered(md)
    # Root Causes / Delay / Contractual / Financial Snapshot suppressed ->
    # fewer sections, still contiguous.
    assert nums == list(range(1, len(nums) + 1)), nums
    assert "Root Causes" not in md
    assert "Delay Analysis" not in md
    assert "Financial Snapshot" not in md
    # Empty recommended actions section is suppressed, not rendered as filler.
    assert "Recommended Actions" not in md


def test_salary_report_has_no_numbering_gap():
    md = to_markdown(_base_report("salary_payroll"))
    nums = _numbered(md)
    assert nums == list(range(1, len(nums) + 1)), nums
    assert "Financial Snapshot" not in md
