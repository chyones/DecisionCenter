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


def test_full_report_numbered_contiguously_one_to_eleven():
    md = to_markdown(_base_report("general_project_status"))
    nums = _numbered(md)
    assert nums == list(range(1, 12)), nums  # 1..11, no gaps


def test_data_report_has_no_numbering_gap():
    md = to_markdown(_base_report("data_report"))
    nums = _numbered(md)
    # Root Causes / Delay / Contractual / Financial Snapshot suppressed ->
    # fewer sections, still contiguous.
    assert nums == list(range(1, len(nums) + 1)), nums
    assert "Root Causes" not in md
    assert "Delay Analysis" not in md
    assert "Financial Snapshot" not in md
    # exec(1), key findings(2), recommended actions(3), ...
    assert "## 3. Recommended Actions — Proposal Only" in md
    assert "## 7. Recommended Actions" not in md


def test_salary_report_has_no_numbering_gap():
    md = to_markdown(_base_report("salary_payroll"))
    nums = _numbered(md)
    assert nums == list(range(1, len(nums) + 1)), nums
    assert "Financial Snapshot" not in md
