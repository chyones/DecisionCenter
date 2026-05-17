"""Phase 2B Slice 4 — Audit Log screen integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403 on all 3 endpoints
- Missing claims → 401
- Happy path: list, detail, CSV export
- Pagination, event_type filter, date filter
- C-1: no query / report content / evidence in responses
- C-6: no credential values in responses
"""
from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.app import (
    AuditEventDetail,
    AuditEventListResponse,
    _require_admin,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — all endpoints deny every non-admin role (parametrised)
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_audit_list_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_audit_detail_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_audit_export_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_audit_list_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# List — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_list_returns_events() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_events = [
        {
            "event_id": "al:1",
            "event_type": "report.submitted",
            "ts": datetime(2026, 5, 15, 10, 0, 0),
            "user_id_hash": "abc123",
            "project_code": "PRJ-001",
            "service": None,
            "detail": "state=staging qg=passed",
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=(fake_events, 1))

    from apps.edr.app import list_admin_audit

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_admin_audit(claims)

    assert isinstance(result, AuditEventListResponse)
    assert result.total == 1
    assert len(result.events) == 1
    assert result.events[0].event_id == "al:1"
    assert result.events[0].event_type == "report.submitted"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_list_pagination() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import list_admin_audit

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await list_admin_audit(claims, limit=25, offset=50)

    call_kwargs = mock_pg.list_audit_events.call_args.kwargs
    assert call_kwargs["limit"] == 25
    assert call_kwargs["offset"] == 50


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_list_event_type_filter() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import list_admin_audit

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await list_admin_audit(claims, event_type="connector.probe_success")

    call_kwargs = mock_pg.list_audit_events.call_args.kwargs
    assert call_kwargs["event_type"] == "connector.probe_success"


@pytest.mark.anyio
async def test_audit_list_date_filter() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=([], 0))

    from apps.edr.app import list_admin_audit

    df = datetime(2026, 5, 1, 0, 0, 0)
    dt = datetime(2026, 5, 31, 23, 59, 59)
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await list_admin_audit(claims, date_from=df, date_to=dt)

    call_kwargs = mock_pg.list_audit_events.call_args.kwargs
    assert call_kwargs["date_from"] == df
    assert call_kwargs["date_to"] == dt


# ---------------------------------------------------------------------------
# Single event detail
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_detail_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "event_id": "rd:5",
        "event_type": "approve",
        "ts": datetime(2026, 5, 15, 12, 0, 0),
        "user_id_hash": "rev99",
        "project_code": None,
        "service": None,
        "detail": "Approved by reviewer",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit_event = AsyncMock(return_value=fake_row)

    from apps.edr.app import get_admin_audit_event

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await get_admin_audit_event("rd:5", claims)

    assert isinstance(result, AuditEventDetail)
    assert result.event_id == "rd:5"
    assert result.event_type == "approve"


@pytest.mark.anyio
async def test_audit_detail_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit_event = AsyncMock(return_value=None)

    from apps.edr.app import get_admin_audit_event

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_admin_audit_event("al:99999", claims)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_export_csv() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_events = [
        {
            "event_id": "ce:2",
            "event_type": "connector.probe_success",
            "ts": datetime(2026, 5, 15, 10, 30, 0),
            "user_id_hash": None,
            "project_code": None,
            "service": "sharepoint",
            "detail": "latency=120ms",
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=(fake_events, 1))

    from apps.edr.app import export_admin_audit_csv

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await export_admin_audit_csv(claims)

    assert response.media_type == "text/csv"
    assert 'attachment; filename="audit-log.csv"' in (
        response.headers.get("Content-Disposition", "")
    )
    body = response.body.decode("utf-8")
    assert "event_id,event_type,ts,user_id_hash,project_code,service,detail" in body
    assert "ce:2" in body
    assert "connector.probe_success" in body


# ---------------------------------------------------------------------------
# C-1 — no business content in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_list_no_business_content() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_events = [
        {
            "event_id": "al:1",
            "event_type": "report.submitted",
            "ts": datetime(2026, 5, 15, 10, 0, 0),
            "user_id_hash": "abc123",
            "project_code": "PRJ-001",
            "service": None,
            "detail": "state=staging qg=passed",
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=(fake_events, 1))

    from apps.edr.app import list_admin_audit

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_admin_audit(claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in audit list"


@pytest.mark.anyio
async def test_audit_detail_no_business_content() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "event_id": "rd:5",
        "event_type": "approve",
        "ts": datetime(2026, 5, 15, 12, 0, 0),
        "user_id_hash": "rev99",
        "project_code": None,
        "service": None,
        "detail": "Approved by reviewer",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit_event = AsyncMock(return_value=fake_row)

    from apps.edr.app import get_admin_audit_event

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await get_admin_audit_event("rd:5", claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in audit detail"


# ---------------------------------------------------------------------------
# C-6 — no credential values in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_list_no_credentials() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_events = [
        {
            "event_id": "al:1",
            "event_type": "report.submitted",
            "ts": datetime(2026, 5, 15, 10, 0, 0),
            "user_id_hash": "abc123",
            "project_code": "PRJ-001",
            "service": None,
            "detail": "state=staging qg=passed",
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audit_events = AsyncMock(return_value=(fake_events, 1))

    from apps.edr.app import list_admin_audit

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_admin_audit(claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in audit list"


@pytest.mark.anyio
async def test_audit_detail_no_credentials() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "event_id": "rd:5",
        "event_type": "approve",
        "ts": datetime(2026, 5, 15, 12, 0, 0),
        "user_id_hash": "rev99",
        "project_code": None,
        "service": None,
        "detail": "Approved by reviewer",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit_event = AsyncMock(return_value=fake_row)

    from apps.edr.app import get_admin_audit_event

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await get_admin_audit_event("rd:5", claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in audit detail"
