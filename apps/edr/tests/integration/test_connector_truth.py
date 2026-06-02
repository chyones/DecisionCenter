"""Connector Status Truth model — integration tests.

Guards the core promise of the truth-status service: **the dashboard never
claims an unavailable or unconfigured dependency is working.**

Covered:
- Missing Odoo credentials ⇒ ``NOT_CONFIGURED`` (non-secret var names listed,
  secret presence false, blocks go-live).
- Missing ownCloud credentials ⇒ ``NOT_CONFIGURED``.
- Fixture/mock data can never be ``LIVE_OK`` (it is ``MOCK_ONLY``).
- A passing core/``/healthz`` probe does NOT imply external connector health.
- Configured-but-unprobed connectors are ``CONFIGURED_NOT_TESTED``, not green.
- Missing AI provider keys ⇒ report generation ``BLOCKED`` and never
  ``READY_FOR_UAT``.
- Endpoint is admin-only; responses carry no credential values (C-6).
"""
from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from apps.edr.admin import connector_status as cs
from apps.edr.app import admin_connectors_truth
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


def test_missing_owncloud_credentials_is_not_configured(owncloud_unconfigured) -> None:
    truth = cs.classify(cs.CONNECTOR_SPEC_BY_NAME["owncloud"], run_probe=False)
    assert truth.state is cs.ConnectorState.NOT_CONFIGURED
    assert truth.configured is False
    assert "OWNCLOUD_USERNAME" in truth.missing_required_config
    assert truth.blocks_go_live is True


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
    # Reachable but no proven live data → not green.
    facts = cs.ProbeFacts(network_ok=True, data_source="live", live_data_ok=None)
    assert cs._state_from_facts(facts) is cs.ConnectorState.CONFIGURED_NOT_TESTED
    # Proven live data → green.
    facts_live = cs.ProbeFacts(network_ok=True, live_data_ok=True, data_source="live")
    assert cs._state_from_facts(facts_live) is cs.ConnectorState.LIVE_OK


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


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _NON_ADMIN)
async def test_truth_endpoint_denies_non_admin(role: str) -> None:
    with pytest.raises(HTTPException) as exc:
        await admin_connectors_truth(claims=_claims(role), probe=False)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_truth_endpoint_rejects_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await admin_connectors_truth(claims=None, probe=False)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_truth_endpoint_response_has_no_credential_values(monkeypatch) -> None:
    # Configure secrets so any accidental value-leak would show up.
    monkeypatch.setattr(cs.settings, "odoo_api_key", "super-secret-odoo-key", raising=False)
    monkeypatch.setattr(cs.settings, "n8n_webhook_token", "n8n-secret-token", raising=False)
    monkeypatch.setattr(cs.settings, "anthropic_api_key", "sk-ant-secret", raising=False)

    report = await admin_connectors_truth(claims=_claims(Role.ADMIN.value), probe=False)
    blob = _serialise(report)
    assert "super-secret-odoo-key" not in blob
    assert "n8n-secret-token" not in blob
    assert "sk-ant-secret" not in blob
    assert not _CRED_SUBSTRING_RE.search(blob), f"credential substring leaked: {blob!r}"


@pytest.mark.asyncio
async def test_truth_endpoint_separates_core_from_connectors() -> None:
    report = await admin_connectors_truth(claims=_claims(Role.ADMIN.value), probe=False)
    assert {t.name for t in report.core_platform} == {"postgres", "redis", "qdrant", "minio"}
    assert any(t.name == "odoo" for t in report.external_connectors)
    assert any(t.name == "entra_auth" for t in report.auth)
    assert any(t.group == "edge" for t in report.edge)
