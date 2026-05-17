"""Phase 2B Slice 8 — Dashboard integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403
- Missing claims → 401
- Happy path — all 5 sources mocked; DashboardSummary shape validated
- Services count — all probes ok → services_ok == services_total
- Degraded service — one probe returns error → services_ok == services_total - 1
- Today counts — dashboard_counts_today returns {7, 2}; assert propagated
- Recent events — list_audit_events returns 3 rows; assert len(recent_events) == 3
- C-1: no query / report content / evidence in response
- C-6: no credential values in response
"""
from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.app import (
    DashboardSummary,
    _require_admin,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — parametrised over 8 non-admin roles
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_dashboard_summary_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_dashboard_summary_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Happy path — monkeypatch all 5 sources
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_summary_happy_path(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 42)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 3))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 5, "failed_qg_today": 1}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=12.34)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    assert isinstance(result, DashboardSummary)
    assert result.services_ok == result.services_total
    assert result.approvals_pending == 3
    assert result.requests_today == 5
    assert result.failed_qg_today == 1
    assert result.monthly_cost == 12.34
    assert result.checked_at != ""


# ---------------------------------------------------------------------------
# Services count — all probes ok
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_services_all_ok(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 10)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 0, "failed_qg_today": 0}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=0.0)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    assert result.services_ok == result.services_total
    assert all(s.status == "ok" for s in result.services)


# ---------------------------------------------------------------------------
# Degraded service — one probe returns error
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_degraded_service(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    call_count = 0

    def fake_probe(name: str) -> tuple[str, int]:
        nonlocal call_count
        call_count += 1
        if name == "postgres":
            return ("error", 0)
        return ("ok", 10)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 0, "failed_qg_today": 0}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=0.0)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    assert result.services_ok == result.services_total - 1
    assert any(s.status == "error" and s.name == "postgres" for s in result.services)


# ---------------------------------------------------------------------------
# Today counts
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_today_counts(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 10)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 7, "failed_qg_today": 2}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=0.0)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    assert result.requests_today == 7
    assert result.failed_qg_today == 2


# ---------------------------------------------------------------------------
# Recent events — 3 rows returned
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_recent_events(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 10)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    fake_rows = [
        {
            "event_id": "al:1",
            "event_type": "report.staged",
            "ts": datetime(2026, 5, 18, 10, 0, 0),
            "user_id_hash": "abc",
            "project_code": "PRJ-001",
            "service": None,
            "detail": "detail-1",
        },
        {
            "event_id": "al:2",
            "event_type": "report.approved",
            "ts": datetime(2026, 5, 18, 11, 0, 0),
            "user_id_hash": "def",
            "project_code": "PRJ-002",
            "service": None,
            "detail": "detail-2",
        },
        {
            "event_id": "ce:1",
            "event_type": "connector.probe_success",
            "ts": datetime(2026, 5, 18, 12, 0, 0),
            "user_id_hash": None,
            "project_code": None,
            "service": "sharepoint",
            "detail": "detail-3",
        },
    ]

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 0, "failed_qg_today": 0}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=0.0)
    mock_pg.list_audit_events = AsyncMock(return_value=(fake_rows, 3))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    assert len(result.recent_events) == 3
    assert result.recent_events[0].event_id == "al:1"
    assert result.recent_events[2].service == "sharepoint"


# ---------------------------------------------------------------------------
# C-1 — no business content
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_summary_no_business_content(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 10)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 0, "failed_qg_today": 0}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=0.0)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content in dashboard summary"


# ---------------------------------------------------------------------------
# C-6 — no credential values
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_summary_no_credentials(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 10)

    monkeypatch.setattr("apps.edr.app._probe_with_latency", fake_probe)

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))
    mock_pg.dashboard_counts_today = AsyncMock(
        return_value={"requests_today": 0, "failed_qg_today": 0}
    )
    mock_pg.monthly_cost_aggregate = AsyncMock(return_value=0.0)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import admin_dashboard_summary

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_dashboard_summary(claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in dashboard summary"
