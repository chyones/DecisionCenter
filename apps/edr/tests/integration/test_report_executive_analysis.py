"""Regression tests for executive-analysis report quality.

Covers the management_question_answer contract and quality gate checks that
prevent search-summary reports from passing.
"""

from __future__ import annotations

from unittest import mock

import pytest

from apps.edr.exporters.markdown import to_markdown
from apps.edr.graph import node_12_draft_json, node_13_quality_gate
from apps.edr.graph.state import DecisionState


_FAKE_EVIDENCE = [
    {
        "evidence_id": "ev_000001",
        "source_type": "sharepoint",
        "source_uri": "/Projects/Marfa/Schedule_Rev3.pdf",
        "title": "Project Schedule Rev 3",
        "excerpt": (
            "Civil Defence Al Marfa project is 90 days behind the baseline schedule "
            "due to delayed approvals and subcontractor mobilisation issues."
        ),
        "hash_sha256": "a" * 64,
        "confidence": "high",
        "tags": ["delay", "schedule"],
    },
    {
        "evidence_id": "ev_000002",
        "source_type": "email",
        "source_uri": "email://inbox/123",
        "title": "RE: Al Marfa subcontractor no-show",
        "excerpt": (
            "The MEP subcontractor has not mobilised to site for three weeks; "
            "client is requesting an updated recovery plan by Sunday."
        ),
        "hash_sha256": "b" * 64,
        "confidence": "high",
        "tags": ["risk"],
    },
    {
        "evidence_id": "ev_000003",
        "source_type": "odoo",
        "source_uri": "odoo://project.project/42",
        "title": "Al Marfa Project Record",
        "excerpt": "Project: Construction of Civil Defense building in Al Marfa | Stage: Execution",
        "hash_sha256": "c" * 64,
        "confidence": "high",
    },
]


def _mock_llm_result():
    """Return a synthesized executive-decision report as the heavy LLM would."""
    return mock.AsyncMock(
        return_value=mock.MagicMock(
            content='''
{
  "request_id": "r-mqa-001",
  "project_code": "PRJ-MARFA",
  "query": "give me big problem for this project only one big",
  "language": "en",
  "executive_summary": [
    {
      "claim": "The biggest problem for the Civil Defence Al Marfa project is a 90-day schedule delay driven by delayed approvals and MEP subcontractor non-mobilisation, which now threatens client confidence and contractual milestones.",
      "evidence_ids": ["ev_000001", "ev_000002"],
      "confidence": "high"
    }
  ],
  "financial_snapshot": {
    "budget": {"value": null, "currency": "AED", "evidence_id": null, "status": "not_available"},
    "actual_cost": {"value": null, "currency": "AED", "evidence_id": null, "status": "not_available"},
    "variance": {"value": null, "currency": "AED", "formula": null, "evidence_ids": []}
  },
  "key_findings": [
    {
      "text": "The baseline schedule has slipped by 90 days, primarily due to approval delays and subcontractor mobilisation failures.",
      "evidence_ids": ["ev_000001"],
      "confidence": "high"
    },
    {
      "text": "The MEP subcontractor has not been on site for three weeks, increasing the risk of further slippage and client escalation.",
      "evidence_ids": ["ev_000002"],
      "confidence": "high"
    }
  ],
  "root_causes": [],
  "delay_analysis": [
    {
      "text": "Schedule Rev 3 records a 90-day delay against baseline.",
      "evidence_ids": ["ev_000001"],
      "confidence": "high"
    }
  ],
  "contractual_implications": [],
  "recommended_actions": [
    {
      "text": "Issue a formal notice to the MEP subcontractor and approve an accelerated recovery plan.",
      "evidence_ids": ["ev_000002"],
      "confidence": "medium"
    }
  ],
  "management_question_answer": {
    "executive_answer": "The single biggest problem is a 90-day schedule delay caused by approval bottlenecks and the MEP subcontractor's failure to mobilise.",
    "why_biggest_problem": [
      "Schedule Rev 3 shows a 90-day slip against the approved baseline (ev_000001).",
      "The MEP subcontractor has not mobilised for three weeks, blocking critical-path works (ev_000002).",
      "The client has requested an updated recovery plan, indicating reputational and contractual pressure (ev_000002).",
      "No budget or cost variance data is available to assess whether this can be recovered commercially."
    ],
    "evidence_used": [
      "SharePoint schedule revision: 90-day baseline slip.",
      "Email thread: MEP subcontractor no-show and client recovery-plan demand."
    ],
    "business_impact": {
      "schedule_impact": "90 days behind baseline; further slippage likely if MEP remains absent.",
      "cost_commercial_impact": "No verified cost data; delay damages and acceleration costs are unquantified.",
      "operational_client_impact": "Client confidence is eroding; a formal recovery plan has been demanded."
    },
    "decision_required": "Decide whether to terminate or formally warn the MEP subcontractor and approve a recovery plan.",
    "recommended_action": {
      "specific_action": "Issue a contractual warning letter to the MEP subcontractor and approve a 30-day recovery plan with daily milestone checkpoints.",
      "owner_role": "Project Director",
      "timeframe": "Within 48 hours"
    },
    "risks_if_no_action": "Further schedule slippage, potential liquidated damages, and client escalation to senior management.",
    "confidence": "high",
    "missing_evidence_or_assumptions": "Project budget and actual cost data are not available in the retrieved Odoo records."
  },
  "missing_data": [
    "Project budget (AED): not available in Odoo analytic line records",
    "Cost variance (budget vs actual): not calculable without a budget baseline"
  ],
  "conflicts": [],
  "sources": [
    {
      "source_id": "S1",
      "source_type": "sharepoint",
      "title": "Project Schedule Rev 3",
      "reference": "/Projects/Marfa/Schedule_Rev3.pdf",
      "date": null,
      "confidence": "high",
      "used_in": ["Key Findings", "Delay Analysis"]
    },
    {
      "source_id": "S2",
      "source_type": "email",
      "title": "RE: Al Marfa subcontractor no-show",
      "reference": "email://inbox/123",
      "date": null,
      "confidence": "high",
      "used_in": ["Key Findings"]
    }
  ],
  "quality_gate_status": "not_run"
}
''',
            cost_usd=0.01,
        )
    )


@pytest.mark.asyncio
async def test_management_question_produces_decision_memo() -> None:
    """A 'one big problem' query must yield a structured decision memo, not a summary."""
    state = DecisionState(
        request_id="r-mqa-001",
        user_id="u-1",
        role="executive",
        project_code="PRJ-MARFA",
        query="give me big problem for this project only one big",
    )
    state.evidence = _FAKE_EVIDENCE

    with mock.patch("apps.edr.graph.node_12_draft_json.call_llm", _mock_llm_result()):
        result = await node_12_draft_json.run(state)

    report = result.report_json or {}
    mqa = report.get("management_question_answer", {})

    assert mqa.get("executive_answer"), "executive_answer must name the biggest problem"
    assert "90-day" in mqa["executive_answer"] or "schedule" in mqa["executive_answer"]

    why = mqa.get("why_biggest_problem", [])
    assert 3 <= len(why) <= 5, "why_biggest_problem must contain 3-5 bullets"

    impact = mqa.get("business_impact", {})
    assert impact.get("schedule_impact")
    assert impact.get("cost_commercial_impact")
    assert impact.get("operational_client_impact")

    assert mqa.get("decision_required"), "decision_required must be present"
    action = mqa.get("recommended_action", {})
    assert action.get("specific_action"), "recommended_action.specific_action must be present"
    assert action.get("owner_role"), "recommended_action.owner_role must be present"
    assert mqa.get("risks_if_no_action"), "risks_if_no_action must be present"
    assert mqa.get("confidence") in ("high", "medium", "low")

    # Quality gate should pass for this synthesized answer.
    qg_result = await node_13_quality_gate.run(result)
    assert qg_result.outputs["quality_gate"] == "passed"


@pytest.mark.asyncio
async def test_management_question_not_raw_evidence_dump() -> None:
    """The report must not present raw excerpts as findings when asked for one problem."""
    state = DecisionState(
        request_id="r-mqa-002",
        user_id="u-1",
        role="executive",
        project_code="PRJ-MARFA",
        query="give me big problem for this project only one big",
    )
    state.evidence = _FAKE_EVIDENCE

    with mock.patch("apps.edr.graph.node_12_draft_json.call_llm", _mock_llm_result()):
        result = await node_12_draft_json.run(state)

    report = result.report_json or {}
    md = to_markdown(report)

    assert "Management Question — Answer" in md
    assert "Executive answer:" in md
    assert "Recommended action:" in md
    assert "Business impact:" in md

    # No raw evidence dumps in the executive answer.
    mqa = report.get("management_question_answer", {})
    assert "evidence_id" not in mqa.get("executive_answer", "")
    assert "evidence review" not in mqa.get("executive_answer", "").lower()

    # Markdown must not read like a catalogue.
    assert "90-day" in md or "schedule delay" in md
    assert "No evidence" not in md


@pytest.mark.asyncio
async def test_quality_gate_flags_search_summary_report() -> None:
    """A report whose executive summary is just 'evidence review' must not pass."""
    state = DecisionState(
        request_id="r-mqa-003",
        user_id="u-1",
        role="executive",
        project_code="PRJ-MARFA",
        query="give me big problem for this project only one big",
    )
    state.evidence = _FAKE_EVIDENCE
    state.report_json = {
        "request_id": "r-mqa-003",
        "project_code": "PRJ-MARFA",
        "query": "give me big problem for this project only one big",
        "executive_summary": [
            {
                "claim": (
                    "Project PRJ-MARFA evidence review: 1 document(s) and 1 email(s) retrieved. "
                    "Key finding: excerpt from schedule. Automated executive synthesis was incomplete."
                ),
                "evidence_ids": ["ev_000001"],
                "confidence": "low",
            }
        ],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [
            {
                "text": "Civil Defence Al Marfa project is 90 days behind the baseline schedule due to delayed approvals and subcontractor mobilisation issues.",
                "evidence_ids": ["ev_000001"],
                "confidence": "high",
            }
        ],
        "root_causes": [],
        "delay_analysis": [],
        "contractual_implications": [],
        "recommended_actions": [],
        "management_question_answer": {
            "executive_answer": "",
            "why_biggest_problem": [],
            "evidence_used": [],
            "business_impact": {
                "schedule_impact": "",
                "cost_commercial_impact": "",
                "operational_client_impact": "",
            },
            "decision_required": "",
            "recommended_action": {
                "specific_action": "",
                "owner_role": "",
                "timeframe": "",
            },
            "risks_if_no_action": "",
            "confidence": "low",
            "missing_evidence_or_assumptions": "",
        },
        "missing_data": [],
        "conflicts": [],
        "sources": [],
    }

    result = await node_13_quality_gate.run(state)
    assert result.outputs["quality_gate"] != "passed"


@pytest.mark.asyncio
async def test_non_management_query_does_not_require_mqa() -> None:
    """A generic status query should not fail quality gate solely due to missing MQA."""
    state = DecisionState(
        request_id="r-mqa-004",
        user_id="u-1",
        role="executive",
        project_code="PRJ-MARFA",
        query="What is the project status?",
    )
    state.evidence = [
        {
            "evidence_id": "ev_000001",
            "source_type": "sharepoint",
            "source_uri": "/doc.pdf",
            "title": "Status report",
            "excerpt": "Project is on track.",
            "hash_sha256": "a" * 64,
            "confidence": "high",
        }
    ]
    state.report_json = {
        "request_id": "r-mqa-004",
        "project_code": "PRJ-MARFA",
        "query": "What is the project status?",
        "project_identity": {
            "project_code": "PRJ-MARFA",
            "project_name": "Construction of Civil Defense building in Al Marfa",
            "identity_source": "approved project registry",
            "identity_confidence": "verified",
            "missing_identity_evidence": [],
            "conflict_notes": [],
        },
        "executive_summary": [
            {
                "claim": "The project is currently on track based on the latest status report.",
                "evidence_ids": ["ev_000001"],
                "confidence": "high",
            }
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
    }

    result = await node_13_quality_gate.run(state)
    assert result.outputs["quality_gate"] == "passed"
