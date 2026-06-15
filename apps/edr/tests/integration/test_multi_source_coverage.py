"""Mandatory multi-source project evidence coverage (2026-06-15).

Proves:
- every enabled source (Odoo, SharePoint, Email) is attempted;
- zero-evidence results are visible in the report's connector coverage, not hidden;
- SharePoint derives project keyword search terms so generic summaries still match;
- the Email source can never be silently skipped (always produces a coverage entry);
- Odoo financial fields are never invented (no budget/actual_cost on project.project);
- the quality gate distinguishes partial vs full evidence and does not silently pass.
"""

from __future__ import annotations

import asyncio
import json


from apps.edr.connectors import odoo as odoo_conn
from apps.edr.graph import (
    coverage,
    node_05_sharepoint,
    node_07_email,
    node_08_odoo,
    node_12_draft_json,
    node_13_quality_gate,
)
from apps.edr.graph.state import DecisionState
from apps.edr.schemas.evidence import EvidenceObject

PROJECT_NAME = "Construction of Civil Defense building in Al Marfa"

MAPPING = {
    "project_code": "PRJ-001",
    "project_name": PROJECT_NAME,
    "enabled_sources": ["email", "odoo", "sharepoint"],
    "sharepoint": {"site_id": "site", "drive_id": "drive"},
    "sharepoint_aliases": ["CivilDefenseCenterinAlMirfa"],
    "odoo": {
        "project_model": "project.project",
        "cost_model": "account.analytic.line",
        "project_external_id": "14602",
        "analytic_account_id": "21963",
        "project_name": PROJECT_NAME,
    },
    "microsoft": {"group": {"id": "grp-1", "mail": "proj@elrace.com", "mail_enabled": True}},
}


class _NoEmbed:
    """Disable embeddings/Qdrant in tests; nodes catch the failure gracefully."""

    def __init__(self, *a, **k):
        raise RuntimeError("embeddings disabled in test")


def _patch_mapping(monkeypatch, module, entry=MAPPING):
    class _M:
        @staticmethod
        def load():
            return _M()

        def get(self, code):
            return entry

    monkeypatch.setattr(module, "ProjectMapping", _M)


def _ev(source_type: str, eid: str, excerpt: str = "x") -> EvidenceObject:
    return EvidenceObject(
        evidence_id=eid, source_type=source_type, source_uri="u", title="t",
        excerpt=excerpt, hash_sha256="a" * 64, confidence="medium",
    )


def _state(role="executive"):
    return DecisionState(
        request_id="r-1", user_id="u-1", query="give me small sumary for this project",
        role=role, project_code="PRJ-001", allowed_projects=["PRJ-001"],
    )


# ---------------------------------------------------------------------------
# 1. All enabled sources are attempted
# ---------------------------------------------------------------------------


def test_all_enabled_sources_attempted(monkeypatch):
    async def fake_sp(payload):
        return [_ev("sharepoint", "sp-1")]

    async def fake_grp(group_id, group_mail=None, project_code=None, top=25):
        return [_ev("email", "eml-1")]

    async def fake_odoo(payload):
        model = payload.get("model")
        if model == "project.project":
            return [_ev("odoo", "odoo-proj")]
        return [_ev("odoo", "odoo-cost-1", "amount: -6500")]

    for mod in (node_05_sharepoint, node_07_email, node_08_odoo):
        _patch_mapping(monkeypatch, mod)
        monkeypatch.setattr(mod, "EmbeddingClient", _NoEmbed)
    monkeypatch.setattr(node_05_sharepoint, "search_sharepoint", fake_sp)
    monkeypatch.setattr(node_07_email, "search_group_conversations", fake_grp)
    monkeypatch.setattr(node_08_odoo, "read_odoo", fake_odoo)

    state = _state()
    asyncio.run(node_05_sharepoint.run(state))
    asyncio.run(node_07_email.run(state))
    asyncio.run(node_08_odoo.run(state))

    cov = state.outputs["source_coverage"]
    for src in ("odoo", "sharepoint", "email"):
        assert cov[src]["attempted"] is True, f"{src} not attempted"
        assert cov[src]["enabled"] is True
        assert cov[src]["status"] == "ok"
    summ = coverage.summary(state)
    assert summ["completeness"] == "full"
    assert summ["all_enabled_attempted"] is True


# ---------------------------------------------------------------------------
# 2. Zero-evidence result is visible (not hidden)
# ---------------------------------------------------------------------------


def test_zero_evidence_is_visible(monkeypatch):
    async def fake_sp_empty(payload):
        return []  # nothing matches any term

    _patch_mapping(monkeypatch, node_05_sharepoint)
    monkeypatch.setattr(node_05_sharepoint, "EmbeddingClient", _NoEmbed)
    monkeypatch.setattr(node_05_sharepoint, "search_sharepoint", fake_sp_empty)

    state = _state()
    asyncio.run(node_05_sharepoint.run(state))

    sp = state.outputs["source_coverage"]["sharepoint"]
    assert sp["attempted"] is True
    assert sp["evidence_count"] == 0
    assert sp["status"] == "zero_no_match"
    assert sp["reason"]  # a reason is recorded, not blank
    section = coverage.report_section(state)
    sp_row = next(r for r in section if r["source"] == "sharepoint")
    assert sp_row["evidence_count"] == 0 and sp_row["status"] == "zero_no_match"


# ---------------------------------------------------------------------------
# 3. SharePoint keyword fallback for generic summaries
# ---------------------------------------------------------------------------


def test_sharepoint_keyword_fallback_terms():
    terms = node_05_sharepoint.derive_search_terms(
        "give me small sumary for this project", MAPPING["sharepoint"], MAPPING, "PRJ-001"
    )
    # The generic query reduces to no keywords, so the first usable term is the
    # project name (or alias/code) — never an empty natural-language sentence.
    assert terms, "no search terms derived"
    assert PROJECT_NAME in terms
    assert terms[0] == PROJECT_NAME


def test_sharepoint_uses_fallback_when_query_matches_nothing(monkeypatch):
    calls: list[str] = []

    async def fake_sp(payload):
        term = payload["query"]
        calls.append(term)
        # Only the project name yields documents (mimics Graph drive search).
        return [_ev("sharepoint", "sp-1")] if term == PROJECT_NAME else []

    _patch_mapping(monkeypatch, node_05_sharepoint)
    monkeypatch.setattr(node_05_sharepoint, "EmbeddingClient", _NoEmbed)
    monkeypatch.setattr(node_05_sharepoint, "search_sharepoint", fake_sp)

    state = _state()
    asyncio.run(node_05_sharepoint.run(state))

    assert PROJECT_NAME in calls
    assert state.outputs["sharepoint_search_term_used"] == PROJECT_NAME
    assert state.outputs["source_coverage"]["sharepoint"]["evidence_count"] == 1


# ---------------------------------------------------------------------------
# 4. Email source cannot be silently skipped
# ---------------------------------------------------------------------------


def test_email_always_records_coverage_on_group_path(monkeypatch):
    async def fake_grp(group_id, group_mail=None, project_code=None, top=25):
        return [_ev("email", "eml-1"), _ev("email", "eml-2")]

    _patch_mapping(monkeypatch, node_07_email)
    monkeypatch.setattr(node_07_email, "EmbeddingClient", _NoEmbed)
    monkeypatch.setattr(node_07_email, "search_group_conversations", fake_grp)

    state = _state()
    asyncio.run(node_07_email.run(state))
    em = state.outputs["source_coverage"]["email"]
    assert em["attempted"] is True and em["evidence_count"] == 2
    assert state.outputs["email_path"] == "group_conversations"


def test_email_error_is_surfaced_not_hidden(monkeypatch):
    async def fake_grp_fail(group_id, group_mail=None, project_code=None, top=25):
        raise RuntimeError("graph 500")

    _patch_mapping(monkeypatch, node_07_email)
    monkeypatch.setattr(node_07_email, "EmbeddingClient", _NoEmbed)
    monkeypatch.setattr(node_07_email, "search_group_conversations", fake_grp_fail)

    state = _state()
    asyncio.run(node_07_email.run(state))
    em = state.outputs["source_coverage"]["email"]
    assert em["status"] == "error" and em["attempted"] is True
    # An enabled source that errored must block a silent pass.
    summ = coverage.summary(state)
    assert "email" in summ["connector_errors"]


def test_email_enabled_but_unmappable_is_blocked_with_reason(monkeypatch):
    entry = dict(MAPPING)
    entry["microsoft"] = {"group": {}}  # no group id/mail
    _patch_mapping(monkeypatch, node_07_email, entry)
    monkeypatch.setattr(node_07_email, "EmbeddingClient", _NoEmbed)

    state = _state(role="project_manager")  # PM can access own mailbox
    state.allowed_mailboxes = []  # no user/shared allowlist either
    asyncio.run(node_07_email.run(state))
    em = state.outputs["source_coverage"]["email"]
    assert em["enabled"] is True
    assert em["status"] == "blocked"
    assert "operator must map" in em["reason"]


def test_summary_always_includes_email_entry():
    # Even with no coverage recorded at all, the summary surfaces email.
    state = DecisionState(request_id="r", user_id="u", query="q")
    section = coverage.report_section(state)
    assert {r["source"] for r in section} == {"odoo", "sharepoint", "email"}


# ---------------------------------------------------------------------------
# 5. Odoo financial fields are not invented
# ---------------------------------------------------------------------------


def test_odoo_project_query_never_requests_invented_fields():
    domain, fields = odoo_conn.build_project_query(MAPPING["odoo"], "PRJ-001")
    flds = json.loads(fields)
    assert "budget" not in flds and "actual_cost" not in flds
    assert json.loads(domain) == [["id", "=", 14602]]


def test_odoo_cost_query_uses_analytic_model_or_none():
    model, domain, fields = odoo_conn.build_cost_query(MAPPING["odoo"])
    assert model == "account.analytic.line"
    assert json.loads(domain) == [["account_id", "=", 21963]]
    assert json.loads(fields) == odoo_conn.COST_FIELDS
    # No verified analytic account -> None (caller states "not available").
    assert odoo_conn.build_cost_query({"project_external_id": "14602"}) is None


def test_financial_note_when_no_verified_cost(monkeypatch):
    valid_report = {
        "request_id": "r-1", "project_code": "PRJ-001", "query": "q", "language": "en",
        "executive_summary": [{"claim": "c", "evidence_ids": ["odoo-proj"], "confidence": "high"}],
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "key_findings": [], "root_causes": [], "delay_analysis": [],
        "contractual_implications": [], "recommended_actions": [], "missing_data": [],
        "conflicts": [], "sources": [],
    }

    class _R:
        content = json.dumps(valid_report)
        cost_usd = 0.0

    async def fake_llm(*a, **k):
        return _R()

    monkeypatch.setattr(node_12_draft_json, "call_llm", fake_llm)
    state = _state()
    state.evidence = [{"evidence_id": "odoo-proj", "source_type": "odoo"}]
    state.outputs["odoo_financial_available"] = False
    asyncio.run(node_12_draft_json.run(state))

    fs = state.report_json["financial_snapshot"]
    assert fs["note"] == "financial data not available in verified Odoo evidence"
    assert fs["budget"]["status"] == "not_available"
    assert fs["actual_cost"]["status"] == "not_available"
    # connector coverage embedded in the report
    assert "connector_coverage" in state.report_json


# ---------------------------------------------------------------------------
# 6. Quality gate: partial vs full, and no silent pass
# ---------------------------------------------------------------------------


def _gate_state(cov: dict, evidence_ids=("sp-1",)):
    state = _state()
    state.evidence = [{"evidence_id": e, "source_type": "sharepoint"} for e in evidence_ids]
    state.report_json = {
        "key_findings": [{"text": "t", "evidence_ids": list(evidence_ids), "confidence": "high"}],
        "financial_snapshot": {}, "sources": [], "conflicts": [],
    }
    state.outputs["source_coverage"] = cov
    return state


def test_quality_gate_full_passes():
    cov = {s: {"enabled": True, "attempted": True, "status": "ok", "evidence_count": 3, "reason": ""}
           for s in ("odoo", "sharepoint", "email")}
    state = _gate_state(cov)
    asyncio.run(node_13_quality_gate.run(state))
    assert state.outputs["evidence_completeness"] == "full"
    assert state.outputs["quality_gate"] == "passed"


def test_quality_gate_connector_error_not_silent_pass():
    cov = {
        "odoo": {"enabled": True, "attempted": True, "status": "ok", "evidence_count": 3, "reason": ""},
        "sharepoint": {"enabled": True, "attempted": True, "status": "ok", "evidence_count": 3, "reason": ""},
        "email": {"enabled": True, "attempted": True, "status": "error", "evidence_count": 0, "reason": "graph 500"},
    }
    state = _gate_state(cov)
    asyncio.run(node_13_quality_gate.run(state))
    assert state.outputs["evidence_completeness"] == "partial"
    assert state.outputs["quality_gate"] == "needs_review"  # must not silently pass


def test_quality_gate_documented_block_is_partial_but_allowed():
    cov = {
        "odoo": {"enabled": True, "attempted": True, "status": "ok", "evidence_count": 3, "reason": ""},
        "sharepoint": {"enabled": True, "attempted": True, "status": "ok", "evidence_count": 3, "reason": ""},
        "email": {"enabled": True, "attempted": False, "status": "blocked", "evidence_count": 0, "reason": "operator must map group"},
    }
    state = _gate_state(cov)
    asyncio.run(node_13_quality_gate.run(state))
    assert state.outputs["evidence_completeness"] == "partial"
    # documented block does not force needs_review by itself (claims still valid)
    assert state.outputs["quality_gate"] == "passed"
