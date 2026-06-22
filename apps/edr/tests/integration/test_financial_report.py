"""Block C tests — distinct project financial figures from Odoo (no mixing).

contract_value / estimate / actual_cost / committed_cost are sourced and
evidence-bound independently. Figures are populated only when a real Odoo
evidence_id backs them, and never fabricated. Committed cost is summed from
tagged extended-source evidence (purchase orders / PO lines) — verified here
with synthetic evidence; live data stays gated behind ODOO_EXTENDED_SOURCES_ENABLED.
"""

from __future__ import annotations

from apps.edr.exporters.markdown import to_markdown
from apps.edr.graph.node_13_quality_gate import _check_financials
from apps.edr.graph.node_12_draft_json import (
    _enforce_financial_categories,
    _extract_odoo_context,
)
from apps.edr.schemas.report import FinancialSnapshot


def _blank_fs() -> dict:
    return {
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        }
    }


def _project_record():
    return {
        "evidence_id": "odoo-project-project-14602",
        "source_type": "odoo",
        "source_uri": "https://erp/web#id=14602&model=project.project",
        "title": "Civil Defense building",
        "excerpt": "name: Civil Defense building",
        "metadata": {"model": "project.project", "f_wo_amount": 5000000.0, "f_estimation_amount": 4800000.0},
        "confidence": "high",
    }


def _po(eid, amount):
    return {
        "evidence_id": eid,
        "source_type": "odoo",
        "source_uri": f"https://erp/web#id={eid}&model=purchase.order",
        "title": f"PO {eid}",
        "excerpt": f"amount_total: {amount}",
        "metadata": {"model": "purchase.order", "odoo_category": "purchase_orders", "f_amount_total": amount},
        "confidence": "high",
    }


# --- C1: data layer ---------------------------------------------------------


def test_schema_accepts_distinct_figures():
    fs = FinancialSnapshot()
    assert hasattr(fs, "contract_value") and hasattr(fs, "estimate") and hasattr(fs, "committed_cost")


def test_contract_estimate_and_committed_from_odoo_evidence():
    odoo_ev = [_project_record(), _po("odoo-purchase-order-40181", 120000.0), _po("odoo-purchase-order-40155", 80000.0)]
    evidence_ids = {e["evidence_id"] for e in odoo_ev}
    ctx = _extract_odoo_context(odoo_ev)
    report = _blank_fs()
    _enforce_financial_categories(report, ctx, odoo_ev, evidence_ids)
    fs = report["financial_snapshot"]

    assert fs["contract_value"]["status"] == "available"
    assert fs["contract_value"]["value"] == 5000000.0
    assert fs["contract_value"]["evidence_id"] == "odoo-project-project-14602"
    assert fs["estimate"]["value"] == 4800000.0
    assert fs["committed_cost"]["status"] == "available"
    assert fs["committed_cost"]["value"] == 200000.0
    assert fs["committed_cost"]["evidence_id"] in {"odoo-purchase-order-40181", "odoo-purchase-order-40155"}
    assert fs["contract_value"]["value"] != fs["estimate"]["value"] != fs["committed_cost"]["value"]


def test_no_financial_evidence_stays_not_available():
    report = _blank_fs()
    ctx = _extract_odoo_context([])
    _enforce_financial_categories(report, ctx, [], set())
    fs = report["financial_snapshot"]
    for key in ("contract_value", "estimate", "committed_cost"):
        assert fs[key]["status"] == "not_available"
        assert fs[key]["value"] is None
        assert fs[key]["evidence_id"] is None


def test_committed_not_fabricated_when_evidence_id_absent_from_pack():
    odoo_ev = [_po("odoo-purchase-order-99999", 50000.0)]
    ctx = _extract_odoo_context(odoo_ev)
    report = _blank_fs()
    _enforce_financial_categories(report, ctx, odoo_ev, evidence_ids=set())
    assert report["financial_snapshot"]["committed_cost"]["status"] == "not_available"


# --- C2: renderer + quality gate -------------------------------------------


def _available(value, eid):
    return {"value": value, "currency": "AED", "evidence_id": eid, "status": "available"}


def test_markdown_renders_distinct_financial_rows():
    report = {
        "report_type": "financial",
        "project_identity": {"project_name": "Test", "project_code": "PRJ-001"},
        "financial_snapshot": {
            "contract_value": _available(5000000.0, "ev_p"),
            "estimate": _available(4800000.0, "ev_p"),
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": _available(57000.0, "ev_a"),
            "committed_cost": _available(200000.0, "ev_po"),
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        },
        "executive_summary": [], "key_findings": [], "recommended_actions": [],
        "conflicts": [], "missing_data": [], "sources": [], "connector_coverage": [],
        "quality_gate_status": "passed",
    }
    md = to_markdown(report)
    for label in ("Contract Value", "Estimate", "Actual Cost", "Committed Cost"):
        assert label in md, label
    assert "5,000,000.00 AED" in md


def test_qg_binds_each_available_financial_figure():
    report = {
        "financial_snapshot": {
            "contract_value": _available(5000000.0, "missing-id"),  # not in pack
            "estimate": _available(4800000.0, "ev_proj"),
            "committed_cost": _available(200000.0, "ev_po"),
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        }
    }
    by = {c.claim_id: c.verdict for c in _check_financials(report, evidence_ids={"ev_proj", "ev_po"})}
    assert by.get("financial_snapshot.contract_value") == "unsupported"
    assert "financial_snapshot.estimate" not in by
    assert "financial_snapshot.committed_cost" not in by


def test_qg_skips_inconclusive_financial_figure():
    report = {
        "financial_snapshot": {
            "contract_value": {"value": None, "currency": "AED", "evidence_id": None, "status": "inconclusive"},
        }
    }
    checks = _check_financials(report, evidence_ids=set())
    assert not any(c.claim_id == "financial_snapshot.contract_value" for c in checks)


def test_financial_fallback_summary_is_evidence_bound():
    """Odoo-only fallback (no docs/email, no LLM) still yields a bound exec summary."""
    from apps.edr.graph.node_12_draft_json import _build_report_from_evidence
    from apps.edr.graph.project_identity import resolve_project_identity
    from apps.edr.graph.state import DecisionState

    analytic = {
        "evidence_id": "odoo-account-analytic-line-9", "source_type": "odoo", "title": "Concrete",
        "excerpt": "name: Concrete; amount: -57000.0; date: 2026-03-01",
        "source_uri": "https://erp/web#id=9&model=account.analytic.line",
        "metadata": {"model": "account.analytic.line", "f_amount": -57000.0, "f_date": "2026-03-01"},
        "confidence": "high",
    }
    ev = [_project_record(), analytic, _po("odoo-purchase-order-40181", 120000.0)]
    s = DecisionState(
        request_id="r", user_id="u", query="what is the actual cost and budget variance",
        role="executive", project_code="PRJ-001", allowed_projects=["PRJ-001"],
        evidence=[dict(e) for e in ev],
    )
    rep = _build_report_from_evidence(s, resolve_project_identity(s))
    es = rep["executive_summary"]
    assert es, "Odoo-only financial fallback must still produce an executive summary"
    ids = {e["evidence_id"] for e in ev}
    assert es[0]["evidence_ids"] and all(eid in ids for eid in es[0]["evidence_ids"])
    assert "financial figures" in es[0]["claim"].lower()


def test_variance_derived_from_estimate_and_actual():
    report = _blank_fs()
    report["financial_snapshot"]["actual_cost"] = _available(-57000.0, "ev_a")  # signed cost
    ev = [_project_record()]  # estimate 4.8M bound to the project record
    ctx = _extract_odoo_context(ev)
    _enforce_financial_categories(report, ctx, ev, {"odoo-project-project-14602", "ev_a"})
    var = report["financial_snapshot"]["variance"]
    assert var["value"] == round(4800000.0 - 57000.0, 2)
    assert var["formula"] == "estimate - actual_cost"
    assert set(var["evidence_ids"]) == {"odoo-project-project-14602", "ev_a"}


def test_variance_not_derived_without_both_inputs():
    report = _blank_fs()  # actual_cost not_available
    ev = [_project_record()]
    ctx = _extract_odoo_context(ev)
    _enforce_financial_categories(report, ctx, ev, {"odoo-project-project-14602"})
    assert report["financial_snapshot"]["variance"]["value"] is None
