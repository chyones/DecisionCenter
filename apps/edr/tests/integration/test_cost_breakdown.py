"""Incurred-cost breakdown — payroll / HR expenses / total incurred.

A financial query must not present a single analytic line as the project's whole
spend. Actual cost is broken into evidence-backed categories (analytic/journal,
payroll/staff, HR expenses for petty cash/vehicle/fuel) and a Total Incurred sum,
each bound to a real Odoo evidence_id and never fabricated. Categories the pack
does not contain stay not_available (honest partial evidence). Verified here with
synthetic extended-source evidence; live figures stay gated behind
ODOO_EXTENDED_SOURCES_ENABLED.
"""

from __future__ import annotations

from apps.edr.exporters.excel import to_excel
from apps.edr.exporters.markdown import to_markdown
from apps.edr.exporters.pdf import to_pdf
from apps.edr.exporters.powerpoint import to_powerpoint
from apps.edr.exporters.word import to_word
from apps.edr.graph.node_12_draft_json import (
    _enforce_financial_categories,
    _extract_odoo_context,
    _financial_snapshot_findings,
)
from apps.edr.graph.node_13_quality_gate import _check_financials
from apps.edr.schemas.report import FinancialSnapshot


def _project_record():
    return {
        "evidence_id": "odoo-project-project-14602",
        "source_type": "odoo",
        "source_uri": "https://erp/web#id=14602&model=project.project",
        "title": "Civil Defense building",
        "excerpt": "name: Civil Defense building",
        "metadata": {
            "model": "project.project",
            "f_wo_amount": 20580000.0,
            "f_estimation_amount": 19000000.0,
        },
        "confidence": "high",
    }


def _analytic(eid, amount, date="2026-03-01"):
    return {
        "evidence_id": eid,
        "source_type": "odoo",
        "source_uri": f"https://erp/web#id={eid}&model=account.analytic.line",
        "title": "Concrete",
        "excerpt": f"name: Concrete; amount: {amount}; date: {date}",
        "metadata": {"model": "account.analytic.line", "f_amount": amount, "f_date": date},
        "confidence": "high",
    }


def _payroll(eid, amount):
    return {
        "evidence_id": eid,
        "source_type": "odoo",
        "source_uri": f"https://erp/web#id={eid}&model=hr.payslip.cost.allocation",
        "title": "Payroll allocation",
        "excerpt": f"amount: {amount}",
        "metadata": {
            "model": "hr.payslip.cost.allocation",
            "odoo_category": "payroll_cost_allocation",
            "f_amount": amount,
        },
        "confidence": "high",
    }


def _expense(eid, amount, kind="petty cash"):
    return {
        "evidence_id": eid,
        "source_type": "odoo",
        "source_uri": f"https://erp/web#id={eid}&model=hr.expense",
        "title": f"HR expense {kind}",
        "excerpt": f"name: {kind}; total_amount: {amount}",
        "metadata": {
            "model": "hr.expense",
            "odoo_category": "hr_expenses",
            "f_total_amount": amount,
        },
        "confidence": "high",
    }


def _blank_fs() -> dict:
    return {
        "financial_snapshot": {
            "budget": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "actual_cost": {"value": None, "currency": "AED", "evidence_id": None, "status": "not_available"},
            "variance": {"value": None, "currency": "AED", "formula": None, "evidence_ids": []},
        }
    }


# --- schema -----------------------------------------------------------------


def test_schema_has_breakdown_fields():
    fs = FinancialSnapshot()
    for field in ("payroll_cost", "expense_cost", "total_incurred"):
        assert hasattr(fs, field), field


# --- aggregation ------------------------------------------------------------


def _build_with(ev):
    evidence_ids = {e["evidence_id"] for e in ev}
    ctx = _extract_odoo_context(ev)
    report = _blank_fs()
    # actual_cost is normally set by _enforce_financial_from_odoo; emulate it here
    # from the analytic sum so the breakdown has its analytic component.
    if ctx["has_amount"] and ctx["best_evidence_id"]:
        report["financial_snapshot"]["actual_cost"] = {
            "value": ctx["total_amount"],
            "currency": "AED",
            "evidence_id": ctx["best_evidence_id"],
            "status": "available",
        }
    _enforce_financial_categories(report, ctx, ev, evidence_ids)
    return report["financial_snapshot"], ctx


def test_payroll_and_expense_summed_into_total_incurred():
    ev = [
        _project_record(),
        _analytic("odoo-account-analytic-line-1", -57636.55),
        _payroll("odoo-hr-payslip-cost-allocation-1", 4200000.0),
        _payroll("odoo-hr-payslip-cost-allocation-2", 1500000.0),
        _expense("odoo-hr-expense-1", 18000.0, "petrol"),
        _expense("odoo-hr-expense-2", 9000.0, "petty cash"),
    ]
    fs, _ = _build_with(ev)

    assert fs["payroll_cost"]["status"] == "available"
    assert fs["payroll_cost"]["value"] == 5700000.0
    assert fs["expense_cost"]["status"] == "available"
    assert fs["expense_cost"]["value"] == 27000.0
    # total = |analytic| + payroll + expenses
    assert fs["total_incurred"]["status"] == "available"
    assert fs["total_incurred"]["value"] == round(57636.55 + 5700000.0 + 27000.0, 2)
    # each figure is evidence-bound
    for k in ("payroll_cost", "expense_cost", "total_incurred"):
        assert fs[k]["evidence_id"]


def test_total_incurred_carries_double_count_caveat():
    ev = [
        _analytic("odoo-account-analytic-line-1", -57636.55),
        _payroll("odoo-hr-payslip-cost-allocation-1", 4200000.0),
    ]
    fs, _ = _build_with(ev)
    assert fs["total_incurred"]["status"] == "available"
    assert "note" in fs and "double-count" in fs["note"]
    assert "actual_cost" in fs["note"] and "payroll_cost" in fs["note"]


def test_single_category_total_has_no_caveat():
    # Only analytic cost present -> total equals actual, no double-count caveat.
    ev = [_analytic("odoo-account-analytic-line-1", -57636.55)]
    fs, _ = _build_with(ev)
    assert fs["total_incurred"]["status"] == "available"
    assert fs["total_incurred"]["value"] == 57636.55
    assert not fs.get("note")


def test_missing_categories_stay_not_available_partial_evidence():
    # The user's real spend exists in Odoo but only the analytic line was retrieved
    # this run: payroll/expenses must report not_available, never a fabricated zero.
    ev = [_project_record(), _analytic("odoo-account-analytic-line-1", -57636.55)]
    fs, _ = _build_with(ev)
    assert fs["payroll_cost"]["status"] == "not_available"
    assert fs["payroll_cost"]["value"] is None
    assert fs["expense_cost"]["status"] == "not_available"


def test_missing_payroll_resets_llm_supplied_value_even_with_valid_evidence_id():
    ev = [_project_record(), _analytic("odoo-account-analytic-line-1", -57636.55)]
    evidence_ids = {e["evidence_id"] for e in ev}
    ctx = _extract_odoo_context(ev)
    report = _blank_fs()
    report["financial_snapshot"]["actual_cost"] = {
        "value": 57636.55,
        "currency": "AED",
        "evidence_id": "odoo-account-analytic-line-1",
        "status": "available",
    }
    report["financial_snapshot"]["payroll_cost"] = {
        "value": 4200000.0,
        "currency": "AED",
        "evidence_id": "odoo-account-analytic-line-1",
        "status": "available",
    }

    _enforce_financial_categories(report, ctx, ev, evidence_ids=evidence_ids)

    fs = report["financial_snapshot"]
    assert fs["payroll_cost"]["status"] == "not_available"
    assert fs["payroll_cost"]["value"] is None
    assert fs["payroll_cost"]["evidence_id"] is None
    assert fs["total_incurred"]["value"] == 57636.55


def test_breakdown_not_fabricated_when_evidence_id_absent_from_pack():
    # Amount present on evidence object, but its id is not in the validated pack.
    ev = [_payroll("odoo-hr-payslip-cost-allocation-9", 4200000.0)]
    ctx = _extract_odoo_context(ev)
    report = _blank_fs()
    _enforce_financial_categories(report, ctx, ev, evidence_ids=set())
    assert report["financial_snapshot"]["payroll_cost"]["status"] == "not_available"
    assert report["financial_snapshot"]["total_incurred"]["status"] == "not_available"


# --- variance ---------------------------------------------------------------


def test_variance_uses_total_incurred_when_breakdown_present():
    ev = [
        _project_record(),  # estimate 19,000,000
        _analytic("odoo-account-analytic-line-1", -57636.55),
        _payroll("odoo-hr-payslip-cost-allocation-1", 4200000.0),
    ]
    fs, _ = _build_with(ev)
    var = fs["variance"]
    assert var["formula"] == "estimate - total_incurred"
    assert var["value"] == round(19000000.0 - (57636.55 + 4200000.0), 2)


def test_variance_uses_total_incurred_when_actual_cost_absent():
    ev = [
        _project_record(),  # estimate 19,000,000
        _payroll("odoo-hr-payslip-cost-allocation-1", 4200000.0),
    ]
    fs, _ = _build_with(ev)
    var = fs["variance"]
    assert fs["actual_cost"]["status"] == "not_available"
    assert fs["total_incurred"]["status"] == "available"
    assert var["formula"] == "estimate - total_incurred"
    assert var["value"] == 14800000.0


# --- findings + render + QG -------------------------------------------------


def test_findings_mention_payroll_expenses_and_total():
    ev = [
        _analytic("odoo-account-analytic-line-1", -57636.55),
        _payroll("odoo-hr-payslip-cost-allocation-1", 4200000.0),
        _expense("odoo-hr-expense-1", 27000.0, "fuel"),
    ]
    fs, ctx = _build_with(ev)
    report = {"financial_snapshot": fs}
    text = " ".join(f["text"] for f in _financial_snapshot_findings(report, ctx))
    assert "payroll / staff cost" in text
    assert "expenses (petty cash, vehicle, fuel)" in text
    assert "total incurred" in text


def test_all_exporters_render_breakdown_rows():
    ev = [
        _analytic("odoo-account-analytic-line-1", -57636.55),
        _payroll("odoo-hr-payslip-cost-allocation-1", 4200000.0),
        _expense("odoo-hr-expense-1", 27000.0, "fuel"),
    ]
    fs, _ = _build_with(ev)
    report = {
        "report_type": "financial",
        "project_identity": {"project_name": "Test", "project_code": "PRJ-001"},
        "financial_snapshot": fs,
        "executive_summary": [], "key_findings": [], "recommended_actions": [],
        "conflicts": [], "missing_data": [], "sources": [], "connector_coverage": [],
        "quality_gate_status": "passed",
    }
    md = to_markdown(report)
    for label in ("Payroll / Staff", "HR Expenses", "Total Incurred"):
        assert label in md, label
    # binary exporters must build without error and be non-empty
    assert to_word(report) and to_pdf(report) and to_powerpoint(report) and to_excel(report)


def test_qg_binds_payroll_expense_and_total():
    report = {
        "financial_snapshot": {
            "payroll_cost": {"value": 4200000.0, "currency": "AED", "evidence_id": "missing", "status": "available"},
            "expense_cost": {"value": 27000.0, "currency": "AED", "evidence_id": "ev_e", "status": "available"},
            "total_incurred": {"value": 4227000.0, "currency": "AED", "evidence_id": "ev_e", "status": "available"},
        }
    }
    by = {c.claim_id: c.verdict for c in _check_financials(report, evidence_ids={"ev_e"})}
    assert by.get("financial_snapshot.payroll_cost") == "unsupported"
    assert "financial_snapshot.expense_cost" not in by
    assert "financial_snapshot.total_incurred" not in by
