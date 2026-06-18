"""Tests for the extended Odoo project source mapping (2026-06-16 audit).

Covers:
- The frozen source registry matches the audit's proven link paths.
- Denylisted/ambiguous paths can never be queried.
- Query construction uses the correct project vs analytic scope id and is
  injection-safe.
- node_08 extended retrieval is opt-in, tags evidence, records per-source
  counts, is graceful on per-source failure, and never weakens financials.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from apps.edr.connectors import odoo
from apps.edr.connectors import odoo_sources as src
from apps.edr.connectors.odoo_sources import AmbiguousOdooPathError
from apps.edr.graph import node_08_odoo
from apps.edr.graph.state import DecisionState
from apps.edr.schemas.evidence import EvidenceObject

PRJ1_CFG = {
    "project_model": "project.project",
    "cost_model": "account.analytic.line",
    "project_external_id": "14602",
    "analytic_account_id": "21963",
    "project_name": "Construction of Civil Defense building in Al Marfa",
}
PRJ2_CFG = {
    "project_model": "project.project",
    "cost_model": "account.analytic.line",
    "project_external_id": "14601",
    "analytic_account_id": "21960",
}

# The 19 business source categories required by the implementation brief,
# mapped to the registry keys that satisfy them.
REQUIRED_CATEGORIES = {
    "project_identity",
    "analytic_identity",
    "actual_cost",
    "account_move_lines",
    "vendor_bills",
    "purchase_orders",
    "purchase_order_lines",
    "material_requests",
    "material_request_lines",
    "mr_analysis_links",
    "stock_pickings",
    "stock_moves",
    "hr_expenses",
    "payroll_headers",
    "payroll_lines",
    "payroll_cost_allocation",
    "payslip_inputs",
    "worked_days",
    "staff_employees",
    "staff_list",
    "project_attachments",
    "po_rfq_attachments",
}


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------


def test_registry_covers_all_required_categories() -> None:
    have = {s.category for s in src.ODOO_SOURCES}
    assert REQUIRED_CATEGORIES <= have, REQUIRED_CATEGORIES - have


def test_registry_keys_are_unique() -> None:
    keys = [s.key for s in src.ODOO_SOURCES]
    assert len(keys) == len(set(keys))


def test_no_registry_source_uses_a_denylisted_path() -> None:
    for s in src.ODOO_SOURCES:
        assert (s.model, s.link_path) not in src.DENYLISTED_PATHS, s.key
        # Must not raise:
        src.assert_path_allowed(s.model, s.link_path)


def test_link_scope_is_project_or_analytic() -> None:
    for s in src.ODOO_SOURCES:
        assert s.link_scope in ("project", "analytic"), s.key


def test_confidence_is_high_or_medium() -> None:
    for s in src.ODOO_SOURCES:
        assert s.confidence in ("high", "medium"), s.key


def test_inline_handled_sources_excluded_from_active() -> None:
    active_keys = {s.key for s in src.active_sources()}
    # project identity + actual cost are retrieved by the inline node_08 path
    assert "project_identity" not in active_keys
    assert "actual_cost" not in active_keys


def test_active_sources_can_exclude_medium() -> None:
    high_only = src.active_sources(include_medium=False)
    assert all(s.confidence == "high" for s in high_only)
    assert "staff_list" not in {s.key for s in high_only}
    assert "staff_list" in {s.key for s in src.active_sources(include_medium=True)}


# ---------------------------------------------------------------------------
# Denylist enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model,path", sorted(src.DENYLISTED_PATHS))
def test_assert_path_allowed_blocks_each_denylisted_path(model: str, path: str) -> None:
    with pytest.raises(AmbiguousOdooPathError):
        src.assert_path_allowed(model, path)


def test_required_denylisted_paths_present() -> None:
    required = {
        ("purchase.order", "project_id_mr"),
        ("purchase.order.line", "order_id.project_id_mr"),
        ("stock.picking", "purchase_id.project_id_mr"),
        ("account.move", "project"),
        ("account.payment", "project"),
        ("sale.order", "project_ids"),
        ("fleet.vehicle", "project_id"),
        ("ir.attachment", "mpr_id.project_id"),
        ("hr.payslip.cost.allocation", "cost_center_id"),
    }
    assert required <= src.DENYLISTED_PATHS


# ---------------------------------------------------------------------------
# Query construction (proven scope + injection-safe)
# ---------------------------------------------------------------------------


def test_project_scoped_source_uses_project_external_id() -> None:
    s = src.source_by_key("material_requests")
    assert s is not None
    model, domain, fields, limit = odoo.build_source_query(s, PRJ1_CFG)
    assert model == "material.purchase.requisition"
    assert json.loads(domain) == [["project_id", "=", 14602]]
    assert "project_id" in json.loads(fields)


def test_analytic_scoped_source_uses_analytic_account_id() -> None:
    s = src.source_by_key("purchase_orders")
    assert s is not None
    model, domain, fields, limit = odoo.build_source_query(s, PRJ1_CFG)
    assert model == "purchase.order"
    # purchase.order.project_id resolves to the ANALYTIC id, not the project id
    assert json.loads(domain) == [["project_id", "=", 21963]]


def test_dotted_link_paths_build_correctly() -> None:
    cases = {
        "payroll_lines": ("hr.payslip.line", "slip_id.project_id", 14601),
        "payslip_inputs": ("hr.payslip.input", "payslip_id.project_id", 14601),
        "po_rfq_attachments": ("ir.attachment", "lead_id_po.project_id", 21960),
        "stock_moves": ("stock.move", "purchase_line_id.account_analytic_id", 21960),
    }
    for key, (model, path, expected_id) in cases.items():
        s = src.source_by_key(key)
        assert s is not None
        m, domain, _, _ = odoo.build_source_query(s, PRJ2_CFG)
        assert m == model
        assert json.loads(domain) == [[path, "=", expected_id]], key


def test_build_source_query_returns_none_when_id_missing() -> None:
    s = src.source_by_key("purchase_orders")  # needs analytic id
    assert s is not None
    assert odoo.build_source_query(s, {"project_external_id": "14602"}) is None


def test_build_source_query_returns_none_for_non_numeric_id() -> None:
    s = src.source_by_key("material_requests")
    assert s is not None
    assert odoo.build_source_query(s, {"project_external_id": "not-a-number"}) is None


def test_build_all_source_queries_marks_unmapped() -> None:
    # No analytic id → every analytic-scoped source is unmapped (query None)
    specs = odoo.build_all_source_queries({"project_external_id": "14602"})
    by_key = {s["key"]: s for s in specs}
    assert by_key["purchase_orders"]["query"] is None  # analytic scope, no id
    assert by_key["material_requests"]["query"] is not None  # project scope, has id


def test_query_domain_is_injection_safe() -> None:
    # A hostile analytic id is non-numeric → rejected (None), never interpolated.
    s = src.source_by_key("account_move_lines")
    assert s is not None
    hostile = '21963"], ["1","=","1"]] ; --'
    assert odoo.build_source_query(s, {"analytic_account_id": hostile}) is None


# ---------------------------------------------------------------------------
# node_08 extended retrieval behaviour
# ---------------------------------------------------------------------------


def _ev(model: str, rid: str) -> EvidenceObject:
    return EvidenceObject(
        evidence_id=f"odoo-{model.replace('.', '-')}-{rid}",
        source_type="odoo",
        source_uri=f"https://erp/web#id={rid}&model={model}",
        title=f"{model} #{rid}",
        project_code="PRJ-001",
        excerpt="amount: -100.0; date: 2026-01-01",
        hash_sha256="a" * 64,
        confidence="high",
        tags=["odoo", model],
        metadata={"model": model, "record_id": int(rid)},
    )


class _FakeMapping:
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg

    @staticmethod
    def load() -> "_FakeMapping":  # patched in per-test
        raise NotImplementedError

    def get(self, project_code: str) -> dict:
        return {"enabled_sources": ["odoo"], "odoo": self._cfg}


def _run_node(monkeypatch: pytest.MonkeyPatch, *, extended: bool, cfg: dict,
              read_impl) -> DecisionState:
    fake = _FakeMapping(cfg)
    monkeypatch.setattr(node_08_odoo.ProjectMapping, "load", lambda: fake)
    monkeypatch.setattr(node_08_odoo, "read_odoo", read_impl)
    monkeypatch.setattr(node_08_odoo.settings, "odoo_extended_sources_enabled", extended)
    # Qdrant/embeddings are best-effort; force them to no-op cleanly
    monkeypatch.setattr(node_08_odoo, "EmbeddingClient", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no embed")))
    state = DecisionState(
        request_id="r-ext", user_id="u-1", role=None,
        project_code="PRJ-001", query="give me everything",
        allowed_odoo_ids=["14602"],
    )
    asyncio.run(node_08_odoo.run(state))
    return state


def test_extended_disabled_by_default_keeps_narrow_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_read(payload: dict) -> list:
        calls.append(payload)
        if payload["model"] == "project.project":
            return [_ev("project.project", "14602")]
        if payload["model"] == "account.analytic.line":
            return [_ev("account.analytic.line", "1")]
        return []

    state = _run_node(monkeypatch, extended=False, cfg=PRJ1_CFG, read_impl=fake_read)
    models = {c["model"] for c in calls}
    assert models == {"project.project", "account.analytic.line"}
    assert state.outputs["odoo_extended_status"] == "disabled"
    assert "odoo_source_counts" not in state.outputs


def test_extended_enabled_queries_all_active_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_read(payload: dict) -> list:
        calls.append(payload)
        # Return one record for every model queried
        return [_ev(payload["model"], "1")]

    state = _run_node(monkeypatch, extended=True, cfg=PRJ1_CFG, read_impl=fake_read)

    queried_models = {c["model"] for c in calls}
    # Inline models
    assert "project.project" in queried_models
    assert "account.analytic.line" in queried_models
    # A representative spread of extended models
    for model in ("purchase.order", "material.purchase.requisition",
                  "stock.picking", "account.move", "hr.payslip",
                  "project.attachment", "ir.attachment"):
        assert model in queried_models, model

    counts = state.outputs["odoo_source_counts"]
    # Every active source returned exactly one row
    assert counts["purchase_orders"] == 1
    assert counts["payroll_lines"] == 1
    assert state.outputs["odoo_extended_status"] == "ok"
    assert state.outputs["odoo_extended_total"] == len(src.active_sources())


def test_extended_tags_evidence_with_category(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read(payload: dict) -> list:
        return [_ev(payload["model"], "1")]

    state = _run_node(monkeypatch, extended=True, cfg=PRJ1_CFG, read_impl=fake_read)
    po = [e for e in state.evidence if e["metadata"].get("model") == "purchase.order"]
    assert po, "no purchase.order evidence"
    assert po[0]["metadata"]["odoo_source_key"] == "purchase_orders"
    assert po[0]["metadata"]["odoo_category"] == "purchase_orders"
    assert "purchase_orders" in po[0]["tags"]
    # Tagged metadata must still validate as flat EvidenceObject metadata
    EvidenceObject.model_validate(po[0])


def test_extended_is_graceful_on_single_source_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read(payload: dict) -> list:
        if payload["model"] == "purchase.order":
            raise RuntimeError("n8n 500")
        return [_ev(payload["model"], "1")]

    state = _run_node(monkeypatch, extended=True, cfg=PRJ1_CFG, read_impl=fake_read)
    statuses = state.outputs["odoo_source_status"]
    assert statuses["purchase_orders"].startswith("error:")
    # Other sources still succeeded
    assert statuses["material_requests"] == "ok"
    assert state.outputs["odoo_status"].startswith("ok")


def test_extended_is_graceful_on_single_source_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(node_08_odoo, "ODOO_EXTENDED_SOURCE_TIMEOUT_S", 0.01)
    monkeypatch.setattr(node_08_odoo, "ODOO_NODE_BUDGET_S", 1.0)

    async def fake_read(payload: dict) -> list:
        if payload["model"] == "purchase.order":
            await asyncio.sleep(0.05)
        return [_ev(payload["model"], "1")]

    state = _run_node(monkeypatch, extended=True, cfg=PRJ1_CFG, read_impl=fake_read)
    statuses = state.outputs["odoo_source_status"]
    assert statuses["purchase_orders"] == "timeout"
    assert statuses["material_requests"] == "ok"
    assert state.outputs["odoo_extended_status"] == "timeout"
    assert state.outputs["odoo_status"].startswith("partial_timeout")


def test_extended_does_not_change_financial_gating(monkeypatch: pytest.MonkeyPatch) -> None:
    # No analytic cost lines → financial must remain unavailable even though
    # extended sources return data. Quality-gate inputs are not weakened.
    async def fake_read(payload: dict) -> list:
        if payload["model"] == "account.analytic.line":
            return []  # no posted cost lines
        if payload["model"] == "project.project":
            return [_ev("project.project", "14602")]
        return [_ev(payload["model"], "1")]

    state = _run_node(monkeypatch, extended=True, cfg=PRJ1_CFG, read_impl=fake_read)
    assert state.outputs["odoo_financial_available"] is False
    assert "financial data not available" in state.outputs["odoo_financial_note"]


def test_extended_unmapped_source_recorded_not_queried(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mapping without analytic id → analytic-scoped sources are unmapped.
    cfg = {"project_model": "project.project", "project_external_id": "14602"}
    calls: list[dict] = []

    async def fake_read(payload: dict) -> list:
        calls.append(payload)
        return [_ev(payload["model"], "1")]

    state = _run_node(monkeypatch, extended=True, cfg=cfg, read_impl=fake_read)
    statuses = state.outputs["odoo_source_status"]
    assert statuses["purchase_orders"] == "unmapped"  # analytic id missing
    assert all(c["model"] != "purchase.order" for c in calls)
    # project-scoped sources still queried
    assert any(c["model"] == "material.purchase.requisition" for c in calls)
