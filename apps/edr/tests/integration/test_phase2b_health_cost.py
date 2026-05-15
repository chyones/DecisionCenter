"""Phase 2B Slice 3 — System Health + cost monitor integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403 on both endpoints
- Happy path: /admin/health/live returns services list with latencies
- Happy path: /admin/cost returns daily/monthly caps + breakdown
- C-1: no query / report content / evidence in responses
- C-6: no credential values in responses
- Cost warning / exceeded thresholds emit connector events
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from apps.edr.admin import services_catalog
from apps.edr.app import (
    CostResponse,
    HealthLiveResponse,
    _require_admin,
    _probe_with_latency,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.llm import _cost_tracker, reset_daily_cost
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — both endpoints deny every non-admin role (parametrised)
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_health_live_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_cost_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Health / live — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_live_returns_services(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    # Patch probes to be fast and deterministic
    def fake_probe(name: str) -> tuple[str, int]:
        return ("ok", 42)

    monkeypatch.setattr(
        "apps.edr.app._probe_with_latency",
        fake_probe,
    )

    # Patch sparkline buckets
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.connector_events_24h_buckets",
        AsyncMock(return_value=[{"avg_latency_ms": 10}, {"avg_latency_ms": 20}]),
    )

    from apps.edr.app import admin_health_live

    result = await admin_health_live(claims)
    assert isinstance(result, HealthLiveResponse)
    assert len(result.services) == len(services_catalog.SERVICE_REGISTRY)
    for svc in result.services:
        assert svc.status == "ok"
        assert svc.latency_ms == 42
        assert svc.sla_ms > 0
        assert isinstance(svc.sparkline_24h, list)
    assert result.checked_at


@pytest.mark.anyio
async def test_health_live_probe_error(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")

    def fake_probe_error(name: str) -> tuple[str, int]:
        return ("error", 0)

    monkeypatch.setattr(
        "apps.edr.app._probe_with_latency",
        fake_probe_error,
    )
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.connector_events_24h_buckets",
        AsyncMock(return_value=[]),
    )

    from apps.edr.app import admin_health_live

    result = await admin_health_live(claims)
    assert all(svc.status == "error" for svc in result.services)


# ---------------------------------------------------------------------------
# Cost — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cost_returns_caps_and_breakdown(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    reset_daily_cost()
    _cost_tracker.record_cost(1.5, model="claude-haiku")
    _cost_tracker.record_cost(3.0, model="claude-sonnet")

    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.monthly_cost_aggregate",
        AsyncMock(return_value=12.34),
    )
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.insert_cost_event",
        AsyncMock(return_value=1),
    )

    from apps.edr.app import admin_cost

    result = await admin_cost(claims)
    assert isinstance(result, CostResponse)
    assert result.daily_cost == 4.5
    assert result.daily_cap > 0
    assert result.monthly_cost == 12.34
    assert result.monthly_cap > 0
    models = {item.model for item in result.llm_breakdown}
    assert "claude-haiku" in models
    assert "claude-sonnet" in models
    assert result.warning is False
    assert result.exceeded is False


@pytest.mark.anyio
async def test_cost_warning_emits_event(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    reset_daily_cost()
    # Set cap low enough that 4.5 triggers warning (>= 80%)
    from apps.edr.config import settings

    original_cap = settings.daily_cost_cap_usd
    monkeypatch.setattr(settings, "daily_cost_cap_usd", 5.0)
    _cost_tracker.record_cost(4.5, model="claude-sonnet")

    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.monthly_cost_aggregate",
        AsyncMock(return_value=0.0),
    )
    insert_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.insert_cost_event",
        insert_mock,
    )

    from apps.edr.app import admin_cost

    result = await admin_cost(claims)
    assert result.warning is True
    assert result.exceeded is False
    insert_mock.assert_awaited_once()
    call_args = insert_mock.await_args
    # When monkeypatching a class method, self is passed positionally
    assert call_args.args[0] == "cost.daily_cap_warning"

    monkeypatch.setattr(settings, "daily_cost_cap_usd", original_cap)


@pytest.mark.anyio
async def test_cost_exceeded_emits_event(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    reset_daily_cost()
    from apps.edr.config import settings

    original_cap = settings.daily_cost_cap_usd
    monkeypatch.setattr(settings, "daily_cost_cap_usd", 5.0)
    _cost_tracker.record_cost(6.0, model="claude-sonnet")

    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.monthly_cost_aggregate",
        AsyncMock(return_value=0.0),
    )
    insert_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.insert_cost_event",
        insert_mock,
    )

    from apps.edr.app import admin_cost

    result = await admin_cost(claims)
    assert result.exceeded is True
    insert_mock.assert_awaited_once()
    call_args = insert_mock.await_args
    assert call_args.args[0] == "cost.daily_cap_exceeded"

    monkeypatch.setattr(settings, "daily_cost_cap_usd", original_cap)


# ---------------------------------------------------------------------------
# C-1 — no business content in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_live_no_business_content(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    monkeypatch.setattr(
        "apps.edr.app._probe_with_latency",
        lambda name: ("ok", 10),
    )
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.connector_events_24h_buckets",
        AsyncMock(return_value=[]),
    )

    from apps.edr.app import admin_health_live

    result = await admin_health_live(claims)
    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in health response"


@pytest.mark.anyio
async def test_cost_no_business_content(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    reset_daily_cost()
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.monthly_cost_aggregate",
        AsyncMock(return_value=0.0),
    )
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.insert_cost_event",
        AsyncMock(return_value=1),
    )

    from apps.edr.app import admin_cost

    result = await admin_cost(claims)
    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in cost response"


# ---------------------------------------------------------------------------
# C-6 — no credential values in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_live_no_credentials(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    monkeypatch.setattr(
        "apps.edr.app._probe_with_latency",
        lambda name: ("ok", 10),
    )
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.connector_events_24h_buckets",
        AsyncMock(return_value=[]),
    )

    from apps.edr.app import admin_health_live

    result = await admin_health_live(claims)
    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in health response"


@pytest.mark.anyio
async def test_cost_no_credentials(monkeypatch) -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    reset_daily_cost()
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.monthly_cost_aggregate",
        AsyncMock(return_value=0.0),
    )
    monkeypatch.setattr(
        "apps.edr.persistence.postgres_store.PostgresStore.insert_cost_event",
        AsyncMock(return_value=1),
    )

    from apps.edr.app import admin_cost

    result = await admin_cost(claims)
    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in cost response"


# ---------------------------------------------------------------------------
# _probe_with_latency unit behaviour
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_probe_with_latency_unknown_service() -> None:
    status, latency = _probe_with_latency("nonexistent")
    assert status == "unknown"
    assert latency == 0


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_health_live_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


def test_cost_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401
