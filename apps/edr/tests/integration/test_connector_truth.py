"""Connector Status Truth model — integration tests.

Guards the core promise of the truth-status service: **the dashboard never
claims an unavailable or unconfigured dependency is working.**

Covered:
- Missing Odoo credentials ⇒ ``NOT_CONFIGURED`` (non-secret var names listed,
  secret presence false, blocks go-live).
- ownCloud is intentionally disabled ⇒ ``DISABLED``, blocks_go_live=False,
  regardless of credential presence.
- Fixture/mock data can never be ``LIVE_OK`` (it is ``MOCK_ONLY``).
- Persisted source-mapping evidence can verify SharePoint/Graph/Email without
  pretending it is a fresh ``LIVE_OK`` probe.
- A passing core/``/healthz`` probe does NOT imply external connector health.
- Configured-but-unprobed connectors are ``CONFIGURED_NOT_TESTED``, not green.
- Missing AI provider keys ⇒ report generation ``BLOCKED`` and never
  ``READY_FOR_UAT``.
- Endpoint is admin-only; responses carry no credential values (C-6).
- A real HTTP error response (e.g. 404) from a probe is ``CONNECTED_NO_DATA``,
  never ``CONFIGURED_NOT_TESTED`` (which implies the probe was never attempted).
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from apps.edr.admin import connector_status as cs
from apps.edr.app import (
    _extract_claims,
    admin_connectors_truth,
    admin_entra_revalidate_token,
)
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claims(role: str | None) -> MagicMock:
    return MagicMock(user_id="user-admin", role=role)


_CRED_SUBSTRING_RE = re.compile(
    r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
)


def _serialise(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), default=str)


def _all_truths(report: cs.ConnectorTruthReport) -> dict[str, cs.ConnectorTruth]:
    out: dict[str, cs.ConnectorTruth] = {}
    for grp in (
        report.core_platform,
        report.auth,
        report.external_connectors,
        report.ai_providers,
        report.edge,
    ):
        for t in grp:
            out[t.name] = t
    return out


@pytest.fixture
def odoo_unconfigured(monkeypatch):
    for attr in ("odoo_url", "odoo_database", "odoo_username", "odoo_api_key"):
        monkeypatch.setattr(cs.settings, attr, None, raising=False)


@pytest.fixture
def owncloud_unconfigured(monkeypatch):
    for attr in ("owncloud_username", "owncloud_password"):
        monkeypatch.setattr(cs.settings, attr, None, raising=False)


# ---------------------------------------------------------------------------
# Required: missing Odoo credentials ⇒ NOT_CONFIGURED
# ---------------------------------------------------------------------------


def test_missing_odoo_credentials_is_not_configured(odoo_unconfigured) -> None:
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=False)

    assert truth.state is cs.ConnectorState.NOT_CONFIGURED
    assert truth.configured is False
    # Non-secret required vars are surfaced by name; the secret is NOT named.
    assert "ODOO_URL" in truth.missing_required_config
    assert "ODOO_DATABASE" in truth.missing_required_config
    assert "ODOO_USERNAME" in truth.missing_required_config
    assert "ODOO_API_KEY" not in truth.missing_required_config  # secret never named
    assert truth.secret_present is False
    assert truth.live_data_ok is not True
    assert truth.data_source != "live"
    assert truth.blocks_go_live is True


# ---------------------------------------------------------------------------
# Required: ownCloud is intentionally disabled ⇒ DISABLED, not NOT_CONFIGURED
# ---------------------------------------------------------------------------


def test_owncloud_is_disabled_regardless_of_credentials(owncloud_unconfigured) -> None:
    # ownCloud disabled=True takes precedence over missing credentials.
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["owncloud"], run_probe=False)
    assert truth.state is cs.ConnectorState.DISABLED
    assert truth.blocks_go_live is False
    assert truth.required_for_go_live is False


def test_owncloud_disabled_even_with_credentials_present(monkeypatch) -> None:
    # Even if someone sets credentials, disabled=True always wins.
    monkeypatch.setattr(cs.settings, "owncloud_username", "user", raising=False)
    monkeypatch.setattr(cs.settings, "owncloud_password", "pass", raising=False)
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["owncloud"], run_probe=True)
    assert truth.state is cs.ConnectorState.DISABLED
    assert truth.blocks_go_live is False


def test_disabled_connector_never_in_blocking_list() -> None:
    report = cs.build_report(run_probes=False)
    assert "owncloud" not in report.blocking


def test_disabled_connector_missing_config_is_empty() -> None:
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["owncloud"], run_probe=False)
    assert truth.missing_required_config == []


@pytest.fixture
def odoo_configured(monkeypatch):
    """Patch settings so Odoo counts as configured. Probe must be mocked separately."""
    monkeypatch.setattr(cs.settings, "odoo_url", "https://odoo.example.com", raising=False)
    monkeypatch.setattr(cs.settings, "odoo_database", "prod", raising=False)
    monkeypatch.setattr(cs.settings, "odoo_username", "svc", raising=False)
    monkeypatch.setattr(cs.settings, "odoo_api_key", "x", raising=False)
    monkeypatch.setattr(cs.settings, "odoo_read_webhook", "/webhook/odoo-read", raising=False)
    monkeypatch.setattr(cs.settings, "n8n_base_url", "http://n8n:5678", raising=False)
    monkeypatch.setattr(cs.settings, "n8n_webhook_token", "tok", raising=False)


def _fake_evidence_response(count: int = 3) -> cs.ProbeFacts:
    """Successful probe facts simulating a real Odoo webhook returning evidence."""
    return cs.ProbeFacts(
        network_ok=True,
        auth_ok=True,
        permission_ok=True,
        live_data_ok=True,
        data_source="live",
        sample_count=count,
        evidence=f"Odoo webhook live: {count} evidence item(s) returned (source_type=odoo)",
    )


@pytest.fixture
def entra_configured(monkeypatch):
    monkeypatch.setattr(
        cs.settings,
        "entra_client_id",
        "a2160d26-acc0-4d8c-b815-3a377f1fb5bd",
        raising=False,
    )
    monkeypatch.setattr(
        cs.settings,
        "entra_tenant_id",
        "14a72467-3f25-4572-a535-3d5eddb00cc5",
        raising=False,
    )


def _write_entra_marker(path, *, expires_delta: timedelta, result: str = "PASS") -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "result": result,
        "validated_at": now.isoformat().replace("+00:00", "Z"),
        "token_expires_at": (now + expires_delta).isoformat().replace("+00:00", "Z"),
        "role": "admin",
        "me_role": "admin",
        "checks": {
            "oidc_discovery_ok": True,
            "jwks_ok": True,
            "issuer_ok": True,
            "audience_ok": True,
            "tenant_ok": True,
            "expiry_valid": True,
            "role_present": True,
            "me_role_ok": True,
        },
    }
    path.write_text(
        "<!-- connector_truth_entra_validation: "
        + json.dumps(payload, sort_keys=True)
        + " -->\n",
        encoding="utf-8",
    )


def test_fresh_entra_validation_marker_marks_auth_validated(
    entra_configured, monkeypatch, tmp_path
) -> None:
    marker = tmp_path / "ENTRA_CONNECTOR_TRUTH_REVALIDATION_2026-06-08.md"
    _write_entra_marker(marker, expires_delta=timedelta(minutes=30))
    monkeypatch.setattr(cs, "_ENTRA_VALIDATION_EVIDENCE_PATH", marker)
    monkeypatch.setattr(
        cs,
        "_probe_entra_oidc_jwks",
        lambda tenant, ts: cs.ProbeFacts(
            network_ok=True,
            live_data_ok=None,
            data_source="none",
            evidence="OIDC discovery and JWKS reachable",
            probed_at=ts,
            success_at=ts,
        ),
    )

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["entra_auth"], run_probe=True)

    assert truth.state is cs.ConnectorState.VALIDATED
    assert truth.data_source == "evidence"
    assert truth.auth_ok is True
    assert truth.permission_ok is True
    assert truth.live_data_ok is True
    assert truth.blocks_go_live is False
    assert "role=admin" in truth.evidence


def test_expired_entra_validation_marker_is_not_validated(
    entra_configured, monkeypatch, tmp_path
) -> None:
    marker = tmp_path / "ENTRA_CONNECTOR_TRUTH_REVALIDATION_2026-06-08.md"
    _write_entra_marker(marker, expires_delta=timedelta(minutes=-5))
    monkeypatch.setattr(cs, "_ENTRA_VALIDATION_EVIDENCE_PATH", marker)
    monkeypatch.setattr(
        cs,
        "_probe_entra_oidc_jwks",
        lambda tenant, ts: cs.ProbeFacts(
            network_ok=True,
            live_data_ok=None,
            data_source="none",
            evidence="OIDC discovery and JWKS reachable",
            probed_at=ts,
            success_at=ts,
        ),
    )

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["entra_auth"], run_probe=True)

    assert truth.state is cs.ConnectorState.PREVIOUSLY_VALIDATED_TOKEN_EXPIRED
    assert truth.state is not cs.ConnectorState.CONFIGURED_NOT_TESTED
    assert truth.blocks_go_live is True
    assert truth.state is not cs.ConnectorState.VALIDATED
    assert truth.data_source == "evidence"
    assert truth.live_data_ok is False


def test_configured_entra_without_validation_evidence_remains_configured_not_tested(
    entra_configured, monkeypatch, tmp_path
) -> None:
    marker = tmp_path / "missing-entra-validation-evidence.md"
    monkeypatch.setattr(cs, "_ENTRA_VALIDATION_EVIDENCE_PATH", marker)
    monkeypatch.setattr(
        cs,
        "_probe_entra_oidc_jwks",
        lambda tenant, ts: cs.ProbeFacts(
            network_ok=True,
            live_data_ok=None,
            data_source="none",
            evidence="OIDC discovery and JWKS reachable",
            probed_at=ts,
            success_at=ts,
        ),
    )

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["entra_auth"], run_probe=True)

    assert truth.state is cs.ConnectorState.CONFIGURED_NOT_TESTED
    assert truth.data_source == "none"
    assert truth.blocks_go_live is True


def test_missing_entra_config_is_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(cs.settings, "entra_client_id", None, raising=False)
    monkeypatch.setattr(cs.settings, "entra_tenant_id", None, raising=False)

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["entra_auth"], run_probe=True)

    assert truth.state is cs.ConnectorState.NOT_CONFIGURED
    assert truth.configured is False
    assert truth.blocks_go_live is True


def test_entra_revalidation_marker_never_stores_or_returns_raw_token(
    entra_configured, monkeypatch, tmp_path
) -> None:
    raw_token = "secret-header.payload.signature"
    marker = tmp_path / "entra-validation.md"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    monkeypatch.setattr(cs, "_ENTRA_VALIDATION_EVIDENCE_PATH", marker)

    class FakeValidator:
        def __init__(self, tenant_id: str, client_id: str) -> None:
            assert tenant_id == cs.settings.entra_tenant_id
            assert client_id == cs.settings.entra_client_id

        def validate(self, token: str) -> MagicMock:
            assert token == raw_token
            return MagicMock(role="admin")

    monkeypatch.setattr("apps.edr.auth.validator.EntraJWTValidator", FakeValidator)
    monkeypatch.setattr(
        "jwt.decode",
        lambda token, options: {"exp": int(expires_at.timestamp())},
    )

    result = cs.write_entra_validation_evidence_marker(raw_token, me_ok=True)
    stored = marker.read_text(encoding="utf-8")
    returned = json.dumps(result, sort_keys=True)

    assert raw_token not in stored
    assert raw_token not in returned
    assert set(result) == {
        "result",
        "validated_at",
        "token_expires_at",
        "role",
        "me_role",
        "checks",
    }
    assert result["role"] == "admin"
    assert result["checks"] == {
        "oidc_discovery_ok": True,
        "jwks_ok": True,
        "issuer_ok": True,
        "audience_ok": True,
        "tenant_ok": True,
        "expiry_valid": True,
        "role_present": True,
        "me_role_ok": True,
    }


def test_entra_revalidation_failure_never_returns_raw_token(
    entra_configured, monkeypatch
) -> None:
    raw_token = "secret-invalid-token"

    class FailingValidator:
        def __init__(self, tenant_id: str, client_id: str) -> None:
            pass

        def validate(self, token: str) -> MagicMock:
            raise ValueError(f"upstream rejected {token}")

    monkeypatch.setattr("apps.edr.auth.validator.EntraJWTValidator", FailingValidator)

    with pytest.raises(ValueError) as exc:
        cs.write_entra_validation_evidence_marker(raw_token, me_ok=False)

    assert raw_token not in str(exc.value)
    assert str(exc.value) == "Token validation failed"


def test_auth_dependency_failure_never_echoes_raw_token(
    entra_configured, monkeypatch
) -> None:
    raw_token = "secret-auth-header-token"

    class FailingValidator:
        def __init__(self, tenant_id: str, client_id: str) -> None:
            pass

        def validate(self, token: str) -> MagicMock:
            raise ValueError(f"upstream rejected {token}")

    monkeypatch.setattr("apps.edr.app.EntraJWTValidator", FailingValidator)

    with pytest.raises(HTTPException) as exc:
        _extract_claims(
            authorization=f"Bearer {raw_token}",
            x_user_role=None,
            x_user_id=None,
        )

    assert exc.value.status_code == 401
    assert raw_token not in str(exc.value.detail)
    assert exc.value.detail == "Invalid token"


def test_entra_revalidation_endpoint_never_returns_raw_token(monkeypatch) -> None:
    raw_token = "secret-browser-token"
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/connectors/entra/revalidate-current-token",
            "headers": [(b"authorization", f"Bearer {raw_token}".encode())],
        }
    )

    class GraphMeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: GraphMeResponse())

    def fake_write(token: str, *, me_ok: bool) -> dict[str, Any]:
        assert token == raw_token
        assert me_ok is True
        return {
            "result": "PASS",
            "validated_at": "2026-06-09T00:00:00Z",
            "token_expires_at": "2026-06-09T01:00:00Z",
            "role": "admin",
            "checks": {"me_role_ok": True},
        }

    monkeypatch.setattr(cs, "write_entra_validation_evidence_marker", fake_write)

    result = asyncio.run(
        admin_entra_revalidate_token(
            request=request,
            claims=_claims(Role.ADMIN.value),
        )
    )

    assert raw_token not in json.dumps(result, sort_keys=True)


def _verified_source_mapping_rows() -> list[dict[str, Any]]:
    return [
        {
            "project_code": "PRJ-001",
            "mapping_status": "complete",
            "enabled_sources": ["email", "odoo", "sharepoint"],
            "sharepoint": {
                "site_id": "elrace.sharepoint.com,a505675a-d15d-4981-a6c5-dfafce8e224c,26e3f61b-f187-4b70-a1d0-a0b0dccea161",
                "drive_id": "b!WmcFpV3RgUmmxd-vzo4iTBv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0",
            },
            "microsoft": {
                "group": {
                    "mail": "ConstructionofCivilDefenseCenterinAlMirfaAlDhafraRegion@elrace.com",
                    "mail_enabled": True,
                },
                "group_membership_status": "GROUP_MEMBERS_READ",
                "member_count": 17,
                "missing_permissions": [],
                "blockers": [],
            },
        },
        {
            "project_code": "PRJ-002",
            "mapping_status": "complete",
            "enabled_sources": ["email", "odoo", "sharepoint"],
            "sharepoint": {
                "site_id": "elrace.sharepoint.com,52b8cba7-6423-4af7-aded-5de04529abea,26e3f61b-f187-4b70-a1d0-a0b0dccea161",
                "drive_id": "b!p8u4UiNk90qt7V3gRSmr6hv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0",
            },
            "microsoft": {
                "group": {
                    "mail": "ConstructionofCivilDefenseCenterinIndustrialAreaofMadin@elrace.com",
                    "mail_enabled": True,
                },
                "group_membership_status": "GROUP_MEMBERS_READ",
                "member_count": 18,
                "missing_permissions": [],
                "blockers": [],
            },
        },
    ]


@pytest.fixture
def microsoft_connectors_configured(monkeypatch):
    monkeypatch.setattr(cs.settings, "n8n_base_url", "http://n8n:5678", raising=False)
    monkeypatch.setattr(cs.settings, "n8n_webhook_token", "tok", raising=False)
    monkeypatch.setattr(
        cs.settings, "sharepoint_search_webhook", "/webhook/sharepoint-search", raising=False
    )
    monkeypatch.setattr(
        cs.settings, "email_search_webhook", "/webhook/email-search", raising=False
    )


def test_configured_odoo_with_probe_skipped_is_not_green(odoo_configured, monkeypatch) -> None:
    """run_probe=False ⇒ CONFIGURED_NOT_TESTED (no live check done)."""
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=False)
    assert truth.configured is True
    assert truth.state is cs.ConnectorState.CONFIGURED_NOT_TESTED
    assert truth.live_data_ok is not True


def test_configured_odoo_live_probe_returns_live_ok(odoo_configured, monkeypatch) -> None:
    """When the Odoo webhook returns valid normalized evidence, state is LIVE_OK."""
    monkeypatch.setattr(cs, "_probe_odoo", _fake_evidence_response)

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=True)

    assert truth.configured is True
    assert truth.state is cs.ConnectorState.LIVE_OK
    assert truth.live_data_ok is True
    assert truth.data_source == "live"
    assert truth.sample_count == 3
    assert truth.blocks_go_live is False


def test_configured_odoo_empty_evidence_is_connected_no_data(odoo_configured, monkeypatch) -> None:
    """Webhook reachable but evidence list is empty ⇒ CONNECTED_NO_DATA, not LIVE_OK."""
    monkeypatch.setattr(
        cs, "_probe_odoo", lambda: cs.ProbeFacts(
            network_ok=True, auth_ok=True, live_data_ok=False, data_source="live",
            evidence="Odoo webhook reachable but returned empty evidence list",
        )
    )
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=True)

    assert truth.configured is True
    assert truth.state is cs.ConnectorState.CONNECTED_NO_DATA
    assert truth.live_data_ok is False
    assert truth.blocks_go_live is True


def test_odoo_http_error_is_connected_no_data_not_untested(odoo_configured, monkeypatch) -> None:
    """HTTP error (e.g. 404 webhook-not-found) from n8n must show CONNECTED_NO_DATA.

    Root cause fixed: probe ran and got a real response (network_ok=True) but
    auth_ok=None (not 401/403). The old _state_from_facts required auth_ok=True
    for CONNECTED_NO_DATA, so this fell through to CONFIGURED_NOT_TESTED — falsely
    implying the probe was never attempted. State must reflect what actually happened.
    """
    monkeypatch.setattr(
        cs, "_probe_odoo", lambda: cs.ProbeFacts(
            network_ok=True,
            auth_ok=None,
            live_data_ok=False,
            data_source="live",
            evidence="Odoo webhook HTTP 404: HTTPError",
            last_error_safe="HTTPError",
        )
    )
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=True)

    assert truth.state is cs.ConnectorState.CONNECTED_NO_DATA
    assert truth.state is not cs.ConnectorState.CONFIGURED_NOT_TESTED
    assert truth.blocks_go_live is True
    assert "404" in truth.evidence


def test_configured_odoo_network_failure_is_network_failed(odoo_configured, monkeypatch) -> None:
    """Webhook unreachable ⇒ NETWORK_FAILED, not LIVE_OK."""
    monkeypatch.setattr(
        cs, "_probe_odoo", lambda: cs.ProbeFacts(
            network_ok=False, live_data_ok=False, data_source="live",
            evidence="Odoo webhook unreachable: Connection refused",
            last_error_safe="Connection refused",
        )
    )
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=True)

    assert truth.state is cs.ConnectorState.NETWORK_FAILED
    assert truth.live_data_ok is False
    assert truth.blocks_go_live is True


def test_odoo_never_live_ok_from_n8n_healthz_alone(odoo_configured, monkeypatch) -> None:
    """A green n8n /healthz must NOT make Odoo LIVE_OK. Odoo needs its own evidence.

    This is the hard rule: _probe_n8n returning success must not bleed into the
    Odoo connector truth — only _probe_odoo returning live evidence qualifies.
    """
    # Make n8n probe succeed
    monkeypatch.setattr(
        cs, "_probe_n8n", lambda: cs.ProbeFacts(
            network_ok=True, live_data_ok=True, data_source="live", evidence="n8n healthz ok"
        )
    )
    # Odoo probe returns network failure
    monkeypatch.setattr(
        cs, "_probe_odoo", lambda: cs.ProbeFacts(
            network_ok=False, live_data_ok=False, data_source="live",
            evidence="odoo webhook unreachable",
        )
    )
    report = cs.build_report(run_probes=True)
    truths = _all_truths(report)

    assert truths["n8n"].state is cs.ConnectorState.LIVE_OK
    assert truths["odoo"].state is cs.ConnectorState.NETWORK_FAILED
    assert truths["odoo"].state is not cs.ConnectorState.LIVE_OK


def test_missing_odoo_credentials_is_not_configured_with_probe(odoo_unconfigured) -> None:
    """NOT_CONFIGURED when creds missing, even if run_probe=True (probe is skipped)."""
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=True)

    assert truth.state is cs.ConnectorState.NOT_CONFIGURED
    assert truth.configured is False
    assert "ODOO_URL" in truth.missing_required_config
    assert truth.live_data_ok is not True
    assert truth.blocks_go_live is True


def test_odoo_truth_response_never_leaks_secrets(odoo_configured, monkeypatch) -> None:
    """No secret value may appear in the ConnectorTruth response (C-6)."""
    monkeypatch.setattr(cs.settings, "odoo_api_key", "super-secret-odoo-key", raising=False)
    monkeypatch.setattr(cs.settings, "n8n_webhook_token", "n8n-secret-token", raising=False)
    monkeypatch.setattr(cs, "_probe_odoo", _fake_evidence_response)

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["odoo"], run_probe=True)
    blob = json.dumps(truth.model_dump(mode="json"), default=str)

    assert "super-secret-odoo-key" not in blob
    assert "n8n-secret-token" not in blob


# ---------------------------------------------------------------------------
# Required: fixture / mock data can never be LIVE_OK
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["mock", "fixture"])
def test_fixture_or_mock_data_cannot_be_live_ok(source: str) -> None:
    facts = cs.ProbeFacts(
        network_ok=True, auth_ok=True, live_data_ok=True, data_source=source
    )
    state = cs._state_from_facts(facts)
    assert state is cs.ConnectorState.MOCK_ONLY
    assert state is not cs.ConnectorState.LIVE_OK


def test_live_data_is_required_for_live_ok() -> None:
    # Reachable but no proven live data (live_data_ok=None) → not green.
    facts = cs.ProbeFacts(network_ok=True, data_source="live", live_data_ok=None)
    assert cs._state_from_facts(facts) is cs.ConnectorState.CONFIGURED_NOT_TESTED
    # Proven live data → green.
    facts_live = cs.ProbeFacts(network_ok=True, live_data_ok=True, data_source="live")
    assert cs._state_from_facts(facts_live) is cs.ConnectorState.LIVE_OK


def test_network_ok_with_live_data_ok_none_is_configured_not_tested() -> None:
    """network_ok=True but live_data_ok=None (probe ran but result is unknown) →
    CONFIGURED_NOT_TESTED. This covers entra-style probes that can't claim live_data_ok."""
    facts = cs.ProbeFacts(network_ok=True, live_data_ok=None, data_source="none")
    assert cs._state_from_facts(facts) is cs.ConnectorState.CONFIGURED_NOT_TESTED


def test_evidence_source_is_verified_but_not_live_ok() -> None:
    """Persisted evidence is accepted only as its own state, never fake LIVE_OK."""
    facts = cs.ProbeFacts(
        network_ok=True,
        auth_ok=True,
        permission_ok=True,
        live_data_ok=True,
        data_source="evidence",
        evidence="current source mapping evidence",
    )

    assert cs._state_from_facts(facts) is cs.ConnectorState.VERIFIED_FROM_EVIDENCE
    assert cs._state_from_facts(facts) is not cs.ConnectorState.LIVE_OK


def test_verified_source_mapping_marks_sharepoint_verified(
    microsoft_connectors_configured, monkeypatch
) -> None:
    monkeypatch.setattr(cs, "_source_mapping_rows", _verified_source_mapping_rows)

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["sharepoint"], run_probe=True)

    assert truth.state is cs.ConnectorState.VERIFIED_FROM_EVIDENCE
    assert truth.data_source == "evidence"
    assert truth.sample_count == 2
    assert truth.blocks_go_live is False
    assert "PRJ-001" in truth.evidence
    assert "PRJ-002" in truth.evidence


def test_verified_group_membership_marks_graph_email_verified(
    microsoft_connectors_configured, monkeypatch
) -> None:
    monkeypatch.setattr(cs, "_source_mapping_rows", _verified_source_mapping_rows)

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["microsoft_graph"], run_probe=True)

    assert truth.state is cs.ConnectorState.VERIFIED_FROM_EVIDENCE
    assert truth.data_source == "evidence"
    assert truth.sample_count == 35
    assert truth.blocks_go_live is False
    assert "17 members" in truth.evidence
    assert "18 members" in truth.evidence


def test_existing_connector_truth_states_remain_unchanged(
    odoo_configured,
    microsoft_connectors_configured,
    monkeypatch,
) -> None:
    monkeypatch.setattr(cs, "_probe_odoo", _fake_evidence_response)
    monkeypatch.setattr(cs, "_source_mapping_rows", _verified_source_mapping_rows)
    for attr in ("anthropic_api_key", "voyage_api_key", "cohere_api_key"):
        monkeypatch.setattr(cs.settings, attr, None, raising=False)

    states = {
        name: cs.classify(cs.CONNECTOR_SPEC_BY_NAME[name], run_probe=True).state
        for name in (
            "odoo",
            "sharepoint",
            "microsoft_graph",
            "owncloud",
            "anthropic",
            "voyage",
            "cohere",
        )
    }

    assert states == {
        "odoo": cs.ConnectorState.LIVE_OK,
        "sharepoint": cs.ConnectorState.VERIFIED_FROM_EVIDENCE,
        "microsoft_graph": cs.ConnectorState.VERIFIED_FROM_EVIDENCE,
        "owncloud": cs.ConnectorState.DISABLED,
        "anthropic": cs.ConnectorState.NOT_CONFIGURED,
        "voyage": cs.ConnectorState.NOT_CONFIGURED,
        "cohere": cs.ConnectorState.NOT_CONFIGURED,
    }


def test_incomplete_group_membership_stays_configured_not_tested(
    microsoft_connectors_configured, monkeypatch
) -> None:
    rows = _verified_source_mapping_rows()
    rows[0]["microsoft"]["member_count"] = 0
    monkeypatch.setattr(cs, "_source_mapping_rows", lambda: rows)

    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["microsoft_graph"], run_probe=True)

    assert truth.state is cs.ConnectorState.CONFIGURED_NOT_TESTED
    assert truth.blocks_go_live is True
    assert truth.state is not cs.ConnectorState.LIVE_OK


# ---------------------------------------------------------------------------
# Required: healthz / core health does NOT imply connector health
# ---------------------------------------------------------------------------


def test_core_probe_success_does_not_make_connectors_live(monkeypatch, odoo_unconfigured) -> None:
    """A green core platform (postgres reachable, like /healthz checks) must not
    bleed into the external connectors. Odoo stays NOT_CONFIGURED."""
    monkeypatch.setattr(
        cs, "_probe_postgres", lambda: cs.ProbeFacts(
            network_ok=True, live_data_ok=True, data_source="live", evidence="tcp ok"
        )
    )
    report = cs.build_report(run_probes=True)
    truths = _all_truths(report)
    assert truths["postgres"].state is cs.ConnectorState.LIVE_OK
    assert truths["odoo"].state is cs.ConnectorState.NOT_CONFIGURED


def test_healthz_ok_shape_is_independent_of_connector_truth(monkeypatch) -> None:
    """The /healthz contract only covers app+postgres+redis+qdrant+minio; it must
    not be read as connector health. The truth report classifies connectors
    separately and keeps Odoo/ownCloud out of the core_platform list."""
    report = cs.build_report(run_probes=False)
    core_names = {t.name for t in report.core_platform}
    assert core_names == {"postgres", "redis", "qdrant", "minio"}
    connector_names = {t.name for t in report.external_connectors}
    assert {"odoo", "owncloud", "sharepoint", "microsoft_graph"} <= connector_names
    # No external connector is hiding in the core list.
    assert core_names.isdisjoint(connector_names)


# ---------------------------------------------------------------------------
# Required: missing AI keys ⇒ report generation BLOCKED, never READY_FOR_UAT
# ---------------------------------------------------------------------------


def test_missing_ai_keys_block_report_generation(monkeypatch) -> None:
    for attr in ("anthropic_api_key", "voyage_api_key", "cohere_api_key"):
        monkeypatch.setattr(cs.settings, attr, None, raising=False)
    report = cs.build_report(run_probes=False)
    assert report.report_generation == "BLOCKED"
    assert report.readiness != "READY_FOR_UAT"
    truths = _all_truths(report)
    assert truths["anthropic"].state is cs.ConnectorState.NOT_CONFIGURED
    assert truths["anthropic"].blocks_go_live is True


def test_readiness_not_ready_when_core_or_edge_unproven(monkeypatch) -> None:
    # No live probes → core/edge cannot be LIVE_OK → never READY_FOR_UAT.
    report = cs.build_report(run_probes=False)
    assert report.readiness in ("NOT_READY", "PARTIAL_READY")
    assert report.readiness != "READY_FOR_UAT"


# ---------------------------------------------------------------------------
# Endpoint: admin-only + C-6 (no credential values)
# ---------------------------------------------------------------------------


_NON_ADMIN = [
    Role.EXECUTIVE.value,
    Role.PROJECT_MANAGER.value,
    Role.AUDITOR.value,
]


@pytest.mark.parametrize("role", _NON_ADMIN)
def test_truth_endpoint_denies_non_admin(role: str) -> None:
    with pytest.raises(HTTPException) as exc:
        admin_connectors_truth(claims=_claims(role), probe=False)
    assert exc.value.status_code == 403


def test_truth_endpoint_rejects_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        admin_connectors_truth(claims=None, probe=False)
    assert exc.value.status_code == 401


def test_truth_endpoint_response_has_no_credential_values(monkeypatch) -> None:
    # Configure secrets so any accidental value-leak would show up.
    monkeypatch.setattr(cs.settings, "odoo_api_key", "super-secret-odoo-key", raising=False)
    monkeypatch.setattr(cs.settings, "n8n_webhook_token", "n8n-secret-token", raising=False)
    monkeypatch.setattr(cs.settings, "anthropic_api_key", "sk-ant-secret", raising=False)

    report = admin_connectors_truth(claims=_claims(Role.ADMIN.value), probe=False)
    blob = _serialise(report)
    assert "super-secret-odoo-key" not in blob
    assert "n8n-secret-token" not in blob
    assert "sk-ant-secret" not in blob
    assert not _CRED_SUBSTRING_RE.search(blob), f"credential substring leaked: {blob!r}"


def test_truth_endpoint_separates_core_from_connectors() -> None:
    report = admin_connectors_truth(claims=_claims(Role.ADMIN.value), probe=False)
    assert {t.name for t in report.core_platform} == {"postgres", "redis", "qdrant", "minio"}
    assert any(t.name == "odoo" for t in report.external_connectors)
    assert any(t.name == "entra_auth" for t in report.auth)
    assert any(t.group == "edge" for t in report.edge)
