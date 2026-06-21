"""Block C tests — distinct project financial figures from Odoo (no mixing).

contract_value / estimate / actual_cost / committed_cost are sourced and
evidence-bound independently. Figures are populated only when a real Odoo
evidence_id backs them, and never fabricated. Committed cost is summed from
tagged extended-source evidence (purchase orders / PO lines) — verified here
with synthetic evidence; live data stays gated behind ODOO_EXTENDED_SOURCES_ENABLED.
"""

from __future__ import annotations

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
    assert fs["estimate"]["evidence_id"] == "odoo-project-project-14602"

    # Committed = sum of PO amount_total, bound to a real PO evidence_id.
    assert fs["committed_cost"]["status"] == "available"
    assert fs["committed_cost"]["value"] == 200000.0
    assert fs["committed_cost"]["evidence_id"] in {"odoo-purchase-order-40181", "odoo-purchase-order-40155"}

    # Figures are kept distinct — never merged into one number.
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
    # PO present in the prompt list but its id is NOT in the validated evidence pack.
    odoo_ev = [_po("odoo-purchase-order-99999", 50000.0)]
    ctx = _extract_odoo_context(odoo_ev)
    report = _blank_fs()
    _enforce_financial_categories(report, ctx, odoo_ev, evidence_ids=set())
    assert report["financial_snapshot"]["committed_cost"]["status"] == "not_available"
