"""Slice 1 regression tests — deterministic Odoo financial extraction.

These pin the contract between the live n8n Odoo workflow output and
``node_12._extract_odoo_context``. The deployed workflow emits evidence whose
excerpt is ``"key: value; key: value"`` and whose metadata carries structured
``f_*`` fields. The previous extractor split the excerpt on ``" / "`` and so
produced ``has_amount=False`` on real data — the financial snapshot then always
rendered "Not available". These tests prevent that regression and lock the new
structured-metadata-first behaviour.
"""

from __future__ import annotations

from apps.edr.graph.node_12_draft_json import _extract_odoo_context


def _cost_line(
    eid: str,
    *,
    amount=None,
    date=None,
    name=None,
    excerpt: str = "",
    model: str = "account.analytic.line",
    uri: str | None = None,
) -> dict:
    meta: dict = {"model": model}
    if amount is not None:
        meta["f_amount"] = amount
    if date is not None:
        meta["f_date"] = date
    if name is not None:
        meta["f_name"] = name
    return {
        "evidence_id": eid,
        "source_type": "odoo",
        "source_uri": uri or f"https://erp/web#id={eid}&model={model}",
        "title": name or "",
        "excerpt": excerpt,
        "metadata": meta,
        "confidence": "high",
    }


def test_amount_from_structured_f_metadata():
    ev = [
        _cost_line("l1", amount=-15000.0, date="2026-03-01", name="Concrete"),
        _cost_line("l2", amount=-42000.0, date="2026-04-01", name="Steel"),
    ]
    ctx = _extract_odoo_context(ev)
    assert ctx["cost_count"] == 2
    assert ctx["has_amount"] is True
    assert ctx["total_amount"] == -57000.0
    assert ctx["categories"] == ["Concrete", "Steel"]
    assert ctx["latest_date"] == "2026-04-01"
    assert ctx["best_evidence_id"] == "l2"


def test_amount_from_live_semicolon_excerpt_without_metadata():
    # Older payloads carry no f_* metadata, only the "; "-joined excerpt — the
    # exact shape the previous " / " splitter failed on.
    ev = [
        {
            "evidence_id": "l1",
            "source_type": "odoo",
            "source_uri": "https://erp/web#id=1&model=account.analytic.line",
            "title": "",
            "excerpt": "name: Concrete supply; amount: -15000.0; date: 2026-03-01",
            "metadata": {},
            "confidence": "high",
        }
    ]
    ctx = _extract_odoo_context(ev)
    assert ctx["has_amount"] is True
    assert ctx["total_amount"] == -15000.0


def test_legacy_slash_excerpt_still_supported():
    ev = [
        {
            "evidence_id": "l1",
            "source_type": "odoo",
            "source_uri": "https://erp/web#id=1&model=account.analytic.line",
            "title": "",
            "excerpt": "Concrete / -15000.0 / 2026-03-01",
            "metadata": {},
            "confidence": "high",
        }
    ]
    ctx = _extract_odoo_context(ev)
    assert ctx["has_amount"] is True
    assert ctx["total_amount"] == -15000.0
    assert ctx["categories"] == ["Concrete"]


def test_analytic_account_identity_is_not_a_cost_line():
    # account.analytic.account is identity/balance, never a cost line.
    ev = [
        {
            "evidence_id": "acc1",
            "source_type": "odoo",
            "source_uri": "https://erp/web#id=21963&model=account.analytic.account",
            "title": "PRJ-001 cost center",
            "excerpt": "name: PRJ-001; balance: 12345.0",
            "metadata": {"model": "account.analytic.account", "f_balance": 12345.0},
            "confidence": "high",
        }
    ]
    ctx = _extract_odoo_context(ev)
    assert ctx["cost_count"] == 0
    assert ctx["has_amount"] is False
    assert len(ctx["project_records"]) == 1


def test_project_record_separated_and_contract_value_exposed():
    ev = [
        {
            "evidence_id": "p1",
            "source_type": "odoo",
            "source_uri": "https://erp/web#id=1&model=project.project",
            "title": "Civil Defense building",
            "excerpt": "name: Civil Defense building",
            "metadata": {
                "model": "project.project",
                "f_wo_amount": 5000000.0,
                "f_estimation_amount": 4800000.0,
            },
            "confidence": "high",
        },
        _cost_line("l1", amount=-15000.0, date="2026-03-01", name="Concrete"),
    ]
    ctx = _extract_odoo_context(ev)
    assert ctx["cost_count"] == 1
    assert len(ctx["project_records"]) == 1
    assert ctx["contract_value"] == 5000000.0
    assert ctx["contract_value_evidence_id"] == "p1"
    assert ctx["estimate"] == 4800000.0
    assert ctx["estimate_evidence_id"] == "p1"


def test_no_amounts_marks_total_unavailable():
    ev = [_cost_line("l1", name="Note", excerpt="name: Note; date: 2026-01-01")]
    ctx = _extract_odoo_context(ev)
    assert ctx["has_amount"] is False
    assert ctx["total_amount"] is None


def test_amounts_without_dates_still_pick_an_evidence_id():
    ev = [_cost_line("l1", amount=-100.0, name="Misc")]  # no date anywhere
    ctx = _extract_odoo_context(ev)
    assert ctx["has_amount"] is True
    assert ctx["total_amount"] == -100.0
    assert ctx["best_evidence_id"] == "l1"
