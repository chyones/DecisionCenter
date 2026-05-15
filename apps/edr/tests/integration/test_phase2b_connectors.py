"""Phase 2B Slice 2 — Connectors & APIs integration tests.

Covers the three new admin endpoints introduced for the locked Connectors &
APIs screen:

- ``GET    /admin/services``
- ``GET    /admin/services/{name}``
- ``POST   /admin/services/{name}/probe``

The tests mock PostgresStore and the per-service probe helpers so they run
in CI without a live infrastructure stack — mirroring the pattern in
``test_phase2b_admin_rbac.py`` and ``test_phase2a_backend.py``.

Acceptance criteria covered (UI_CONTRACT_v1.md §9.2):

- A-03: ``.env`` key presence shown; no credential values.
- A-04: ``[Test connection]`` is a read-only probe; pass/fail + latency in-band.
- A-05: n8n workflow status ``empty`` when ``nodes==[]``, ``deployed`` otherwise.

C-1 / C-6 absence are asserted by a regex sweep over every endpoint response.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.admin import services_catalog
from apps.edr.app import (
    get_admin_service,
    list_admin_services,
    probe_admin_service,
)
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claims(role: str | None, user_id: str = "user-admin") -> MagicMock:
    return MagicMock(user_id=user_id, role=role)


_NON_ADMIN_ROLES: list[str] = [
    Role.EXECUTIVE.value,
    Role.PROJECT_MANAGER.value,
    Role.FINANCE.value,
    Role.COMMERCIAL.value,
    Role.DOCUMENT_CONTROL.value,
    Role.PROCUREMENT.value,
    Role.LEGAL.value,
    Role.AUDITOR.value,
]


_INFRA_SERVICES = ("postgres", "redis", "qdrant", "minio", "langfuse", "n8n")
_WORKFLOW_SERVICES = ("sharepoint", "microsoft_graph", "owncloud", "odoo")


def _mock_store(
    *,
    latest: dict[str, dict[str, Any]] | None = None,
    recent: list[dict[str, Any]] | None = None,
) -> MagicMock:
    store = MagicMock()
    store.latest_connector_event_per_service = AsyncMock(return_value=latest or {})
    store.recent_connector_events = AsyncMock(return_value=recent or [])
    store.insert_connector_event = AsyncMock(return_value=1)
    return store


_CRED_SUBSTRING_RE = re.compile(
    r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
)


def _assert_no_credential_substring(blob: str) -> None:
    assert not _CRED_SUBSTRING_RE.search(
        blob
    ), f"credential substring leaked into response: {blob!r}"


def _serialise(obj: Any) -> str:
    """JSON-serialise a Pydantic-model-or-list so we can regex-scan."""
    if isinstance(obj, list):
        return json.dumps([o.model_dump(mode="json") for o in obj], default=str)
    return json.dumps(obj.model_dump(mode="json"), default=str)


# ---------------------------------------------------------------------------
# RBAC — all three endpoints reject every non-admin role (parametrised)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
async def test_list_services_denies_non_admin(role: str) -> None:
    with patch(
        "apps.edr.app.get_postgres_store", return_value=_mock_store()
    ), pytest.raises(HTTPException) as exc:
        await list_admin_services(claims=_claims(role=role))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
async def test_get_service_denies_non_admin(role: str) -> None:
    with patch(
        "apps.edr.app.get_postgres_store", return_value=_mock_store()
    ), pytest.raises(HTTPException) as exc:
        await get_admin_service(name="postgres", claims=_claims(role=role))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
async def test_probe_denies_non_admin(role: str) -> None:
    with patch(
        "apps.edr.app.get_postgres_store", return_value=_mock_store()
    ), pytest.raises(HTTPException) as exc:
        await probe_admin_service(name="postgres", claims=_claims(role=role))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_endpoints_reject_missing_claims_401() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        for fn in (list_admin_services,):
            with pytest.raises(HTTPException) as exc:
                await fn(claims=None)
            assert exc.value.status_code == 401
        with pytest.raises(HTTPException) as exc:
            await get_admin_service(name="postgres", claims=None)
        assert exc.value.status_code == 401
        with pytest.raises(HTTPException) as exc:
            await probe_admin_service(name="postgres", claims=None)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Happy path — admin can list and inspect services
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_services_returns_all_ten_for_admin() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        response = await list_admin_services(claims=_claims(role=Role.ADMIN.value))

    assert {s.name for s in response} == set(services_catalog.SERVICE_REGISTRY)
    # No event written → all statuses are "unknown".
    assert all(s.last_probe_status == "unknown" for s in response)
    # Workflow services emit workflow_status; infra services do not.
    for summary in response:
        if summary.name in _WORKFLOW_SERVICES:
            assert summary.workflow_status in ("deployed", "empty")
        else:
            assert summary.workflow_status is None


@pytest.mark.asyncio
async def test_list_services_surfaces_latest_event_status() -> None:
    latest = {
        "postgres": {
            "ts": datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc),
            "event_type": "connector.probe_success",
            "latency_ms": 12,
            "status_code": 200,
            "detail": "ok",
        },
        "redis": {
            "ts": datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc),
            "event_type": "connector.error",
            "latency_ms": 2003,
            "status_code": None,
            "detail": "ConnectionError@redis",
        },
    }
    with patch(
        "apps.edr.app.get_postgres_store",
        return_value=_mock_store(latest=latest),
    ):
        response = await list_admin_services(claims=_claims(role=Role.ADMIN.value))

    by_name = {s.name: s for s in response}
    assert by_name["postgres"].last_probe_status == "pass"
    assert by_name["postgres"].last_latency_ms == 12
    assert by_name["redis"].last_probe_status == "fail"
    assert by_name["redis"].last_latency_ms == 2003


@pytest.mark.asyncio
async def test_get_service_404_for_unknown_name() -> None:
    with patch(
        "apps.edr.app.get_postgres_store", return_value=_mock_store()
    ), pytest.raises(HTTPException) as exc:
        await get_admin_service(
            name="manager-of-coffee", claims=_claims(role=Role.ADMIN.value)
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# A-03 — env-key presence; no credential values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_service_returns_env_key_presence_only() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        detail = await get_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    # Every env key entry is the (name, present) shape — no value field.
    for entry in detail.env_keys:
        assert isinstance(entry, services_catalog.EnvKeyStatus)
        assert isinstance(entry.present, bool)

    # The "POSTGRES_PASSWORD" key must appear, with no value leaked.
    names = {e.name for e in detail.env_keys}
    assert "POSTGRES_PASSWORD" in names
    payload = _serialise(detail)
    _assert_no_credential_substring(payload)
    # The default fixture value "change-me" must never appear in the response.
    assert "change-me" not in payload


def test_env_key_status_rejects_extra_fields() -> None:
    # The Pydantic model is frozen with extra="forbid" — extra fields raise.
    with pytest.raises(Exception):
        services_catalog.EnvKeyStatus(name="X", present=True, value="leak")  # type: ignore[call-arg]


def test_is_present_is_false_for_missing_setting(monkeypatch) -> None:
    monkeypatch.setattr(
        services_catalog.settings, "langfuse_secret_key", None, raising=False
    )
    assert services_catalog._is_present("LANGFUSE_SECRET_KEY") is False
    monkeypatch.setattr(
        services_catalog.settings, "langfuse_secret_key", "x", raising=False
    )
    assert services_catalog._is_present("LANGFUSE_SECRET_KEY") is True


@pytest.mark.asyncio
async def test_list_services_response_has_no_credential_substring() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        response = await list_admin_services(claims=_claims(role=Role.ADMIN.value))
    _assert_no_credential_substring(_serialise(response))


# ---------------------------------------------------------------------------
# A-04 — read-only probe with pass/fail + latency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_pass_writes_probe_success_event() -> None:
    store = _mock_store()
    with patch(
        "apps.edr.admin.services_catalog._probe_postgres", return_value=None
    ), patch("apps.edr.app.get_postgres_store", return_value=store):
        result = await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    assert result.status == "pass"
    assert result.latency_ms >= 0
    assert result.status_code == 200
    store.insert_connector_event.assert_awaited()
    written = [call.kwargs for call in store.insert_connector_event.await_args_list]
    types = [w["event_type"] for w in written]
    assert types == ["connector.probe_success"]


@pytest.mark.asyncio
async def test_probe_fail_writes_error_event_and_returns_200_inband() -> None:
    store = _mock_store()

    def _explode() -> None:
        raise ConnectionError("connection refused")

    with patch(
        "apps.edr.admin.services_catalog._probe_postgres", side_effect=_explode
    ), patch("apps.edr.app.get_postgres_store", return_value=store):
        result = await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    assert result.status == "fail"
    assert result.status_code is None
    written = [call.kwargs for call in store.insert_connector_event.await_args_list]
    types = [w["event_type"] for w in written]
    assert types == ["connector.error"]


@pytest.mark.asyncio
async def test_probe_latency_spike_emits_both_events(monkeypatch) -> None:
    store = _mock_store()
    # Fake the monotonic helper so the probe appears to take 2100ms. We patch
    # ``services_catalog._now_monotonic`` rather than ``time.monotonic`` to
    # avoid polluting the event loop's internal clock.
    ticks = iter([1000.0, 1002.1])
    monkeypatch.setattr(
        services_catalog, "_now_monotonic", lambda: next(ticks)
    )

    with patch(
        "apps.edr.admin.services_catalog._probe_postgres", return_value=None
    ), patch("apps.edr.app.get_postgres_store", return_value=store):
        result = await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    assert result.status == "pass"
    assert result.latency_ms >= services_catalog.LATENCY_SPIKE_THRESHOLD_MS
    written = [call.kwargs for call in store.insert_connector_event.await_args_list]
    types = [w["event_type"] for w in written]
    assert types == ["connector.probe_success", "connector.latency_spike"]


@pytest.mark.asyncio
async def test_probe_404_for_unknown_service() -> None:
    with patch(
        "apps.edr.app.get_postgres_store", return_value=_mock_store()
    ), pytest.raises(HTTPException) as exc:
        await probe_admin_service(
            name="not-a-service", claims=_claims(role=Role.ADMIN.value)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_probe_does_not_touch_audit_log_table() -> None:
    """C-1/C-6 boundary: probe writes go to ``connector_events`` only — they
    never reach ``audit_log`` (which carries business-data columns)."""
    store = _mock_store()
    store.insert_audit = AsyncMock(return_value=None)

    with patch(
        "apps.edr.admin.services_catalog._probe_postgres", return_value=None
    ), patch("apps.edr.app.get_postgres_store", return_value=store):
        await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    store.insert_connector_event.assert_awaited()
    store.insert_audit.assert_not_awaited()


# ---------------------------------------------------------------------------
# A-05 — workflow status from local n8n JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_service_status_is_deployed_when_nodes_present() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        detail = await get_admin_service(
            name="sharepoint", claims=_claims(role=Role.ADMIN.value)
        )
    # The checked-in n8n/sharepoint_search.json has multiple nodes.
    assert detail.workflow_status == "deployed"
    assert (detail.workflow_node_count or 0) > 0


@pytest.mark.asyncio
async def test_workflow_service_status_is_empty_when_nodes_empty(
    tmp_path, monkeypatch
) -> None:
    fake_dir = tmp_path
    (fake_dir / "owncloud_list.json").write_text(
        json.dumps({"name": "owncloud_list", "nodes": []})
    )
    monkeypatch.setattr(services_catalog, "_WORKFLOWS_DIR", fake_dir)

    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        detail = await get_admin_service(
            name="owncloud", claims=_claims(role=Role.ADMIN.value)
        )
    assert detail.workflow_status == "empty"
    assert detail.workflow_node_count == 0


@pytest.mark.asyncio
async def test_infrastructure_service_has_no_workflow_status() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()):
        detail = await get_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )
    assert detail.workflow_status is None
    assert detail.workflow_node_count is None


# ---------------------------------------------------------------------------
# C-6 — credential leakage prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_response_redacts_exception_strings_with_credentials(
    monkeypatch,
) -> None:
    """If a driver embeds the connection string in its exception message,
    the sanitiser must drop the credential before it reaches the response or
    the persisted ``connector_events.detail`` row."""
    store = _mock_store()

    def _leaky_probe() -> None:
        raise ConnectionError(
            "could not connect: host=postgres user=admin password=hunter2 db=x"
        )

    with patch(
        "apps.edr.admin.services_catalog._probe_postgres", side_effect=_leaky_probe
    ), patch("apps.edr.app.get_postgres_store", return_value=store):
        result = await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    _assert_no_credential_substring(_serialise(result))
    assert "hunter2" not in result.detail
    persisted = store.insert_connector_event.await_args_list[0].kwargs["detail"]
    assert "hunter2" not in persisted
    _assert_no_credential_substring(persisted)


def test_safe_hostname_strips_userinfo() -> None:
    assert (
        services_catalog._safe_hostname("postgres://user:pass@host:5432/db") == "host"
    )
    assert services_catalog._safe_hostname("user:pass@host:9000") == "host"
    assert services_catalog._safe_hostname("host") == "host"
    assert services_catalog._safe_hostname(None) is None


def test_sanitize_detail_drops_long_tokens_and_kv_pairs() -> None:
    raw = "ConnectionError host=db Bearer abcdefghijklmnopqrstuv password=hunter2"
    out = services_catalog._sanitize_detail(raw)
    assert "abcdefghijklmnopqrstuv" not in out
    assert "hunter2" not in out


# ---------------------------------------------------------------------------
# C-1 — admin responses never carry report content
# ---------------------------------------------------------------------------


_FORBIDDEN_BUSINESS_KEYS = {"query", "markdown", "evidence", "excerpt"}


def _flatten_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _flatten_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item)
    return keys


@pytest.mark.asyncio
async def test_no_business_content_keys_in_any_endpoint_response() -> None:
    with patch("apps.edr.app.get_postgres_store", return_value=_mock_store()), patch(
        "apps.edr.admin.services_catalog._probe_postgres", return_value=None
    ):
        listed = await list_admin_services(claims=_claims(role=Role.ADMIN.value))
        detail = await get_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )
        probe = await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )

    for payload in (listed, detail, probe):
        keys = _flatten_keys(
            payload.model_dump(mode="json")
            if not isinstance(payload, list)
            else [p.model_dump(mode="json") for p in payload]
        )
        assert keys.isdisjoint(
            _FORBIDDEN_BUSINESS_KEYS
        ), f"forbidden C-1 key present: {keys & _FORBIDDEN_BUSINESS_KEYS}"


# ---------------------------------------------------------------------------
# Event write semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_handler_propagates_insert_failure() -> None:
    """If ``insert_connector_event`` raises, the handler does not silently
    swallow it. The admin sees an honest 500 rather than a "success" that
    was never persisted."""
    store = _mock_store()
    store.insert_connector_event = AsyncMock(side_effect=RuntimeError("pg down"))

    with patch(
        "apps.edr.admin.services_catalog._probe_postgres", return_value=None
    ), patch("apps.edr.app.get_postgres_store", return_value=store), pytest.raises(
        RuntimeError
    ):
        await probe_admin_service(
            name="postgres", claims=_claims(role=Role.ADMIN.value)
        )
