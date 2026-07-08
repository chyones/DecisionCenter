"""Regression tests for the professional report output work.

Covers:
* query-language detection (Arabic vs English reports);
* per-claim salvage of LLM drafts (one bad claim no longer discards the draft);
* financial reports keeping the LLM narrative alongside Odoo-led figures;
* the executive-first markdown layout (localized headings, suppressed empty
  sections, low-confidence-only markers, governance appendix at the end).
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from apps.edr.exporters.markdown import to_markdown
from apps.edr.graph import node_12_draft_json
from apps.edr.graph.intent import detect_language
from apps.edr.graph.node_12_draft_json import (
    _force_financial_odoo_synthesis,
    _salvage_llm_claims,
)
from apps.edr.graph.project_identity import resolve_project_identity
from apps.edr.graph.state import DecisionState


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def test_detect_language_arabic_query():
    assert detect_language("تقرير عن مصاريف المشروع بطريقة مفصلة") == "ar"


def test_detect_language_english_query():
    assert detect_language("what is the biggest problem for this project") == "en"


def test_detect_language_mixed_query_with_project_code():
    assert detect_language("تقرير مالي عن PRJ-001") == "ar"


def test_detect_language_empty_query():
    assert detect_language("") == "en"


# ---------------------------------------------------------------------------
# Salvage: keep the valid LLM claims, drop only the invalid ones
# ---------------------------------------------------------------------------


def _draft_with_one_bad_claim() -> dict:
    return {
        "executive_summary": [
            {"claim": "Real analytical summary.", "evidence_ids": ["ev_1"], "confidence": "high"}
        ],
        "key_findings": [
            {"text": "Valid finding.", "evidence_ids": ["ev_1"], "confidence": "medium"},
            {"text": "Hallucinated finding.", "evidence_ids": ["ev_unknown"], "confidence": "high"},
        ],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [
            {"text": "Do something concrete.", "evidence_ids": ["ev_2"], "confidence": "medium"}
        ],
    }


def test_salvage_drops_only_invalid_claims():
    report = _draft_with_one_bad_claim()
    dropped = _salvage_llm_claims(report, {"ev_1", "ev_2"})
    assert dropped["key_findings"] == 1
    assert [f["text"] for f in report["key_findings"]] == ["Valid finding."]
    assert len(report["executive_summary"]) == 1
    assert len(report["recommended_actions"]) == 1


def test_salvage_drops_placeholder_claims():
    report = {
        "executive_summary": [
            {"claim": "synthesized insight from evidence", "evidence_ids": ["ev_1"]}
        ],
        "key_findings": [],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
    }
    _salvage_llm_claims(report, {"ev_1"})
    assert report["executive_summary"] == []


@pytest.mark.asyncio
async def test_run_keeps_llm_draft_when_one_claim_is_invalid():
    """One invalid evidence id must not force the whole draft to fallback."""
    evidence = [
        {
            "evidence_id": "ev_000001",
            "source_type": "sharepoint",
            "source_uri": "/Projects/X/doc.pdf",
            "title": "Progress Notes",
            "excerpt": "Approvals for phase 2 are pending with the consultant since March.",
            "confidence": "high",
        },
    ]
    llm_report = {
        "request_id": "r-salvage-1",
        "project_code": "PRJ-001",
        "query": "project status?",
        "language": "en",
        "executive_summary": [
            {
                "claim": "Phase 2 approvals are the current bottleneck for the project.",
                "evidence_ids": ["ev_000001"],
                "confidence": "high",
            }
        ],
        "key_findings": [
            {
                "text": "Consultant approvals for phase 2 have been pending since March.",
                "evidence_ids": ["ev_000001"],
                "confidence": "high",
            },
            {
                "text": "Fabricated claim citing unknown evidence.",
                "evidence_ids": ["ev_does_not_exist"],
                "confidence": "high",
            },
        ],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "management_question_answer": {"executive_answer": ""},
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }
    state = DecisionState(
        request_id="r-salvage-1",
        user_id="u-1",
        role="executive",
        project_code="PRJ-001",
        query="project status?",
        evidence=evidence,
    )
    fake = mock.AsyncMock(
        return_value=mock.MagicMock(content=json.dumps(llm_report), cost_usd=0.0)
    )
    with mock.patch("apps.edr.graph.node_12_draft_json.call_llm", fake):
        result = await node_12_draft_json.run(state)

    assert result.outputs["draft_report_source"] == "llm"
    assert result.outputs["draft_salvage_dropped"] == {"key_findings": 1}
    findings = [f["text"] for f in result.report_json["key_findings"]]
    assert "Fabricated claim citing unknown evidence." not in findings
    assert "Consultant approvals for phase 2 have been pending since March." in findings
    claims = [c["claim"] for c in result.report_json["executive_summary"]]
    assert claims == ["Phase 2 approvals are the current bottleneck for the project."]


# ---------------------------------------------------------------------------
# Financial reports: Odoo-led figures + preserved LLM narrative
# ---------------------------------------------------------------------------


def _financial_report_with_narrative() -> dict:
    return {
        "financial_snapshot": {
            "contract_value": {
                "value": 5_000_000.0,
                "currency": "AED",
                "evidence_id": "odoo-project-project-14602",
                "status": "available",
            },
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {
                "value": -57_000.0,
                "currency": "AED",
                "evidence_id": "odoo-line-1",
                "status": "available",
            },
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "executive_summary": [
            {
                "claim": "Spending is concentrated in early civil works; procurement has not started.",
                "evidence_ids": ["odoo-line-1"],
                "confidence": "medium",
            }
        ],
        "key_findings": [
            {
                "text": "Costs to date are dominated by concrete supply for the raft foundation.",
                "evidence_ids": ["odoo-line-1"],
                "confidence": "medium",
            },
            {
                "text": "Total spend is 57,000.00 AED so far.",
                "evidence_ids": ["odoo-line-1"],
                "confidence": "medium",
            },
        ],
    }


def test_financial_summary_with_llm_computed_total_is_replaced():
    """A summary asserting its own (wrong) total must not survive next to the snapshot."""
    report = _financial_report_with_narrative()
    report["executive_summary"] = [
        {
            "claim": "Total recorded expenses reached 98,367.61 AED across 19 analytic lines.",
            "evidence_ids": ["odoo-line-1"],
            "confidence": "medium",
        }
    ]
    state = DecisionState(
        request_id="r-fin-2",
        user_id="u-1",
        role="executive",
        project_code="PRJ-001",
        query="expense report",
        evidence=[],
    )
    identity = resolve_project_identity(state)
    _force_financial_odoo_synthesis(
        report, state, {"project_records": [], "has_amount": False}, identity
    )
    claims = " ".join(c.get("claim", "") for c in report["executive_summary"])
    assert "98,367.61" not in claims


def test_financial_summary_matching_snapshot_amount_survives():
    report = _financial_report_with_narrative()
    report["executive_summary"] = [
        {
            "claim": "Actual cost to date stands at 57,000.00 AED against a 5,000,000.00 AED contract.",
            "evidence_ids": ["odoo-line-1"],
            "confidence": "medium",
        }
    ]
    state = DecisionState(
        request_id="r-fin-3",
        user_id="u-1",
        role="executive",
        project_code="PRJ-001",
        query="expense report",
        evidence=[],
    )
    identity = resolve_project_identity(state)
    _force_financial_odoo_synthesis(report, state, {"project_records": []}, identity)
    assert report["executive_summary"][0]["claim"].startswith("Actual cost to date")


def test_markdown_cost_rows_render_as_magnitudes():
    """Odoo stores costs negative; the executive table must not show a minus sign."""
    report = _renderable_report()
    report["financial_snapshot"]["actual_cost"] = {
        "value": -130_648.30,
        "currency": "AED",
        "evidence_id": "e1",
        "status": "available",
    }
    md = to_markdown(report)
    assert "| 130,648.30 AED |" in md
    assert "-130,648.30" not in md


def test_financial_synthesis_keeps_llm_narrative():
    report = _financial_report_with_narrative()
    state = DecisionState(
        request_id="r-fin-1",
        user_id="u-1",
        role="executive",
        project_code="PRJ-001",
        query="expense report",
        evidence=[],
    )
    identity = resolve_project_identity(state)
    _force_financial_odoo_synthesis(report, state, {"project_records": []}, identity)

    texts = [f["text"] for f in report["key_findings"]]
    # Odoo-led figure findings first…
    assert texts[0].startswith("Odoo shows contract value")
    # …then the LLM narrative finding without its own amount.
    assert "Costs to date are dominated by concrete supply for the raft foundation." in texts
    # LLM findings asserting their own currency amounts are dropped (figures stay Odoo-led).
    assert "Total spend is 57,000.00 AED so far." not in texts
    # The real LLM executive summary is preserved, not replaced by the fallback.
    assert report["executive_summary"][0]["claim"].startswith("Spending is concentrated")


# ---------------------------------------------------------------------------
# Markdown layout
# ---------------------------------------------------------------------------


def _renderable_report(language: str = "en") -> dict:
    return {
        "request_id": "r-md-1",
        "project_code": "PRJ-001",
        "project_identity": {"project_name": "Test Project", "project_code": "PRJ-001"},
        "query": "q",
        "language": language,
        "report_type": "financial",
        "executive_summary": [
            {"claim": "Summary claim.", "evidence_ids": ["e1"], "confidence": "medium"}
        ],
        "financial_snapshot": {
            "contract_value": {
                "value": 5_000_000.0,
                "currency": "AED",
                "evidence_id": "e1",
                "status": "available",
            },
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [
            {"text": "High-confidence finding.", "evidence_ids": ["e1"], "confidence": "high"},
            {"text": "Low-confidence finding.", "evidence_ids": ["e1"], "confidence": "low"},
        ],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "conflicts": [],
        "missing_data": [],
        "sources": [
            {
                "source_id": "e1",
                "source_type": "odoo",
                "title": "RCC-PO-33107: .",
                "reference": "https://erp/web#id=1",
                "date": "2026-06-23",
                "confidence": "high",
            }
        ],
        "connector_coverage": [
            {"source": "odoo", "enabled": True, "attempted": True, "evidence_count": 3, "status": "ok"}
        ],
        "quality_gate_status": "passed",
        "evidence_completeness": "partial",
    }


def test_markdown_body_leads_with_summary_and_ends_with_governance():
    md = to_markdown(_renderable_report())
    assert md.index("## 1. Executive Summary") < md.index("## 2. Financial Snapshot — Odoo")
    # Plumbing renders once, at the end, in the governance appendix.
    assert "## Appendix — Report Governance" in md
    assert md.index("## 1. Executive Summary") < md.index("## Appendix — Report Governance")
    assert "Request ID" in md.split("## Appendix — Report Governance")[1]
    assert "Data Source Coverage" in md
    # No plumbing before the executive summary.
    head = md.split("## 1. Executive Summary")[0]
    assert "Request ID" not in head
    assert "Connector Coverage" not in head
    assert "Quality Gate" not in head


def test_markdown_financial_table_hides_unavailable_rows():
    md = to_markdown(_renderable_report())
    assert "| Contract Value | 5,000,000.00 AED | e1 |" in md
    assert "| Budget | Not available" not in md
    assert "Not available in Odoo: Estimate, Budget," in md


def test_markdown_confidence_marker_only_for_low():
    md = to_markdown(_renderable_report())
    assert "High-confidence finding. — [e1]" in md
    assert "Low-confidence finding. *(low confidence — analyst review advised)* — [e1]" in md
    assert "*(Confidence: medium)*" not in md
    assert "*(Confidence: high)*" not in md


def test_markdown_source_title_artifact_cleaned():
    md = to_markdown(_renderable_report())
    assert "RCC-PO-33107: ." not in md
    assert "RCC-PO-33107" in md


def test_markdown_arabic_headings_and_type_name():
    md = to_markdown(_renderable_report(language="ar"))
    assert md.startswith("# التقرير المالي — Test Project — PRJ-001")
    assert "## 1. الملخص التنفيذي" in md
    assert "## 2. الموقف المالي — Odoo" in md
    assert "## الملحق — حوكمة التقرير" in md
    assert "قيمة العقد" in md
    # English section headings must not leak into an Arabic report body.
    assert "## 1. Executive Summary" not in md
