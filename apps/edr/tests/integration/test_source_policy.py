"""Block D tests — source policy + disabled-source isolation.

- Each project source has a documented purpose (SharePoint=docs, Email=comms,
  Odoo=financials/identity/cost/procurement/payroll).
- Disabled sources never affect completeness, connector errors, or the
  not-attempted set (coverage derives those from enabled sources only).
- Per-type source hints: financial -> Odoo, document_search -> SharePoint.
"""

from __future__ import annotations

from apps.edr.graph import coverage
from apps.edr.graph import report_policy as rp
from apps.edr.graph.state import DecisionState


def test_source_purpose_documents_each_project_source():
    for src in ("sharepoint", "email", "odoo"):
        assert src in rp.SOURCE_PURPOSE and rp.SOURCE_PURPOSE[src].strip()


def _state() -> DecisionState:
    return DecisionState(request_id="r", user_id="u", query="q", project_code="PRJ-001")


def test_disabled_sources_do_not_affect_completeness():
    s = _state()
    coverage.record(s, "sharepoint", enabled=True, attempted=True, status="ok", evidence_count=2, reason="")
    coverage.record(s, "email", enabled=False, attempted=False, status="not_enabled", evidence_count=0, reason="")
    coverage.record(s, "odoo", enabled=False, attempted=False, status="not_enabled", evidence_count=0, reason="")
    summ = coverage.summary(s)
    # Only the one enabled source counts, and it has evidence -> full.
    assert summ["completeness"] == "full"
    assert summ["connector_errors"] == []
    assert summ["not_attempted_sources"] == []


def test_disabled_source_error_is_not_counted():
    s = _state()
    coverage.record(s, "sharepoint", enabled=True, attempted=True, status="ok", evidence_count=1, reason="")
    coverage.record(s, "odoo", enabled=False, attempted=True, status="error", evidence_count=0, reason="boom")
    summ = coverage.summary(s)
    assert "odoo" not in summ["connector_errors"]
    assert summ["completeness"] == "full"


def test_per_type_source_hints():
    assert rp.policy_for("financial").sources_required == ("odoo",)
    assert rp.policy_for("document_search").sources_required == ("sharepoint",)
