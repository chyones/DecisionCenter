"""Connector truth-status service.

Single rule: **never report a connector live unless a real live probe proved
it.** Container-up, route-exists, code-module-exists, fixture-data-exists and
local deterministic checks are NOT evidence of a working external integration.

This module classifies every dependency into one of the explicit truth states
in :class:`ConnectorState` and computes a top-level readiness banner. It is
metadata-only and C-6 safe: it reads credential *presence* (never values),
emits only non-secret config variable names, and sanitises every error string
via :func:`services_catalog._sanitize_detail`.

Design notes
------------
- Configuration is derived from key-presence only (:func:`_is_present`).
- A handful of dependencies have a *real* live probe where reachability/data IS
  the proof: core infra (postgres/redis/qdrant/minio), n8n, and the public edge.
  For those a successful probe yields ``LIVE_OK``.
- Dependencies we cannot validate without real credentials, a real login, or a
  billable/leaky call (Entra auth and AI providers) are deliberately capped at
  ``CONFIGURED_NOT_TESTED`` when configured and ``NOT_CONFIGURED`` when not.
  SharePoint/email may move only to ``VERIFIED_FROM_EVIDENCE`` when current
  persisted source-mapping evidence proves the read succeeded; Odoo still needs
  its own live webhook probe for ``LIVE_OK``.
- ``data_source`` of ``mock``/``fixture`` can never map to ``LIVE_OK`` (it maps
  to ``MOCK_ONLY``); this is enforced in :func:`_state_from_facts`.
- ``data_source="evidence"`` is intentionally not ``LIVE_OK``. It means current
  persisted runtime evidence proves a read succeeded earlier (for example the
  verified PRJ-001/PRJ-002 Source Mapping + Microsoft group enrichment), but no
  live connector call was made during this dashboard probe.
- A connector with ``disabled=True`` is intentionally turned off. It is
  classified as ``DISABLED`` regardless of credential presence, never appears
  in the go-live blocking list, and never shows as ``error`` on the health page.

Entra token expiry policy
-------------------------
Entra access tokens expire hourly under normal operation. The dashboard MUST
NOT require a manually-refreshed ``dc_token.txt`` for routine operation.

Three distinct Entra states are supported:
- ``VALIDATED``: evidence file exists and the validation token is still live.
- ``PREVIOUSLY_VALIDATED_TOKEN_EXPIRED``: evidence exists but the token has
  expired. The connector WAS validated — this is different from CONFIGURED_NOT_TESTED
  which means it was *never* validated. Revalidation via the admin endpoint clears
  this state.
- ``CONFIGURED_NOT_TESTED``: config keys present but no validation evidence has
  ever been saved (first-run or evidence file deleted).

The ``/admin/connectors/entra/revalidate-current-token`` endpoint allows an
admin to revalidate using their current browser session bearer token without
needing CLI access.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from apps.edr.admin import services_catalog
from apps.edr.config import settings

# ---------------------------------------------------------------------------
# Truth states
# ---------------------------------------------------------------------------


class ConnectorState(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED_NOT_TESTED = "CONFIGURED_NOT_TESTED"
    AUTH_FAILED = "AUTH_FAILED"
    PERMISSION_FAILED = "PERMISSION_FAILED"
    NETWORK_FAILED = "NETWORK_FAILED"
    CONNECTED_NO_DATA = "CONNECTED_NO_DATA"
    VALIDATED = "VALIDATED"
    PREVIOUSLY_VALIDATED_TOKEN_EXPIRED = "PREVIOUSLY_VALIDATED_TOKEN_EXPIRED"
    VERIFIED_FROM_EVIDENCE = "VERIFIED_FROM_EVIDENCE"
    LIVE_OK = "LIVE_OK"
    MOCK_ONLY = "MOCK_ONLY"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


DataSource = Literal["live", "evidence", "mock", "fixture", "none"]
Group = Literal["core_platform", "auth", "external_connector", "ai_provider", "edge"]
Readiness = Literal["READY_FOR_UAT", "PARTIAL_READY", "NOT_READY"]


# ---------------------------------------------------------------------------
# Config-key presence (C-6: presence boolean only, never the value)
#
# services_catalog._ENV_KEY_TO_SETTING only knows the original 10-service keys,
# so this module carries the additional identity/AI/edge keys it audits.
# ---------------------------------------------------------------------------


_EXTRA_ENV_KEY_TO_SETTING: dict[str, str] = {
    "ENTRA_CLIENT_ID": "entra_client_id",
    "ENTRA_TENANT_ID": "entra_tenant_id",
    "ENTRA_CLIENT_SECRET": "entra_client_secret",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "VOYAGE_API_KEY": "voyage_api_key",
    "COHERE_API_KEY": "cohere_api_key",
    "PUBLIC_HOSTNAME": "public_hostname",
}

#: Hostnames that mean "no real public edge" (so PUBLIC_HOSTNAME counts as unset
#: for the edge connectors rather than a misleading green).
_NON_PUBLIC_HOSTS = {"", "localhost", "127.0.0.1", ":80"}
_SOURCE_MAPPING_PATH = (
    Path(__file__).parents[3] / "docs" / "config" / "project_source_mapping.json"
)
_ENTRA_VALIDATION_EVIDENCE_PATH = (
    Path(__file__).parents[3]
    / "docs"
    / "evidence"
    / "uat"
    / "ENTRA_CONNECTOR_TRUTH_REVALIDATION_2026-06-08.md"
)
_ENTRA_VALIDATION_MARKER_PREFIX = "<!-- connector_truth_entra_validation:"
_ENTRA_VALIDATION_MARKER_SUFFIX = "-->"
_VERIFIED_PROJECT_MEMBER_COUNTS = {"PRJ-001": 17, "PRJ-002": 18}
_VERIFIED_GROUP_STATUS = "GROUP_MEMBERS_READ"


def _is_present(env_key: str) -> bool:
    """Return True iff the setting backing ``env_key`` is non-empty. Never the
    value. Delegates unknown keys to ``services_catalog._is_present``."""
    attr = _EXTRA_ENV_KEY_TO_SETTING.get(env_key)
    if attr is None:
        return services_catalog._is_present(env_key)
    value = getattr(settings, attr, None)
    if value is None:
        return False
    text = str(value).strip()
    if env_key == "PUBLIC_HOSTNAME" and text in _NON_PUBLIC_HOSTS:
        return False
    return bool(text)


# ---------------------------------------------------------------------------
# Probe facts — what a live probe actually established (never raises out)
# ---------------------------------------------------------------------------


@dataclass
class ProbeFacts:
    network_ok: bool | None = None
    auth_ok: bool | None = None
    permission_ok: bool | None = None
    live_data_ok: bool | None = None
    data_source: DataSource = "none"
    sample_count: int | None = None
    evidence: str = ""
    last_error_safe: str | None = None
    probed_at: str | None = None
    success_at: str | None = None
    token_expires_at: str | None = None


# ---------------------------------------------------------------------------
# Connector specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    display_name: str
    group: Group
    #: Non-secret config var names whose presence is required to be "configured".
    #: These names are safe to surface in ``missing_required_config``.
    required_nonsecret: tuple[str, ...]
    #: Secret var names required to be "configured". Presence only — never value.
    required_secrets: tuple[str, ...]
    #: When True, this dependency must reach LIVE_OK before go-live; otherwise it
    #: blocks the readiness banner.
    required_for_go_live: bool
    #: Name of the module-level probe function (late-bound) or None for
    #: config-only dependencies (capped at CONFIGURED_NOT_TESTED).
    probe: str | None = None
    note: str = ""
    #: When True the connector is intentionally turned off. classify() returns
    #: DISABLED immediately — credentials are not checked and the connector
    #: never blocks go-live.
    disabled: bool = False


# ---------------------------------------------------------------------------
# Response models (extra="forbid" — accidental fields are a hard error)
# ---------------------------------------------------------------------------


class ConnectorTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    group: Group
    state: ConnectorState
    summary: str
    configured: bool
    missing_required_config: list[str]
    secret_present: bool
    auth_ok: bool | None
    network_ok: bool | None
    permission_ok: bool | None
    live_data_ok: bool | None
    data_source: DataSource
    last_probe_at: str | None
    last_success_at: str | None
    token_expires_at: str | None
    last_error_safe: str | None
    sample_count: int | None
    evidence: str
    required_for_go_live: bool
    blocks_go_live: bool


class ConnectorTruthReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness: Readiness
    readiness_reason: str
    report_generation: Literal["READY", "DEGRADED", "BLOCKED"]
    report_generation_reason: str
    generated_at: str
    core_platform: list[ConnectorTruth]
    auth: list[ConnectorTruth]
    external_connectors: list[ConnectorTruth]
    ai_providers: list[ConnectorTruth]
    edge: list[ConnectorTruth]
    blocking: list[str]


# ---------------------------------------------------------------------------
# Live probes — each returns ProbeFacts, never raises
# ---------------------------------------------------------------------------


def _now() -> str:
    return services_catalog.now_iso()


def _facts_from_reachability(evidence_ok: str, probe_callable) -> ProbeFacts:
    """Run a reachability probe where a real response IS the liveness proof.

    Success ⇒ network_ok=True, live_data_ok=True, data_source="live".
    Failure ⇒ NETWORK_FAILED facts with a sanitised error.
    """
    ts = _now()
    try:
        probe_callable()
    except Exception as exc:  # never propagate
        detail = services_catalog._detail_for_exception(exc, None)
        return ProbeFacts(
            network_ok=False,
            live_data_ok=False,
            data_source="live",
            evidence=f"probe failed: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )
    return ProbeFacts(
        network_ok=True,
        live_data_ok=True,
        data_source="live",
        evidence=evidence_ok,
        probed_at=ts,
        success_at=ts,
    )


def _probe_postgres() -> ProbeFacts:
    return _facts_from_reachability(
        "TCP connect to PostgreSQL succeeded", services_catalog._probe_postgres
    )


def _probe_redis() -> ProbeFacts:
    return _facts_from_reachability(
        "Redis PING returned PONG", services_catalog._probe_redis
    )


def _probe_qdrant() -> ProbeFacts:
    return _facts_from_reachability(
        "HTTP 200 from Qdrant /collections", services_catalog._probe_qdrant
    )


def _probe_minio() -> ProbeFacts:
    return _facts_from_reachability(
        "HTTP 200 from MinIO /minio/health/ready", services_catalog._probe_minio
    )


def _probe_n8n() -> ProbeFacts:
    return _facts_from_reachability(
        "HTTP 200 from n8n /healthz", services_catalog._probe_n8n
    )


def _probe_odoo() -> ProbeFacts:
    """Live probe for the Odoo connector via the configured n8n webhook.

    Posts a minimal read-only query (model ``project.project``, domain
    ``[["active","=",true]]``, limit 5) to the n8n webhook and validates the
    response body:

    - ``evidence`` list must be non-empty.
    - First item must carry ``source_type == "odoo"`` and the canonical
      evidence fields ``evidence_id``, ``title``, ``source_uri``.

    On success => ``LIVE_OK``.
    On empty evidence (HTTP 200 but no records) => ``CONNECTED_NO_DATA``.
    On HTTP / network failure => ``NETWORK_FAILED``.
    """
    import json as _json
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    ts = _now()
    base = (settings.n8n_base_url or "").rstrip("/")
    path_ = (settings.odoo_read_webhook or "/webhook/odoo-read").lstrip("/")
    token = settings.n8n_webhook_token or ""
    url = f"{base}/{path_}"

    if not base:
        return ProbeFacts(
            network_ok=None,
            data_source="none",
            evidence="N8N_BASE_URL not set — cannot reach Odoo webhook",
            probed_at=ts,
        )

    payload = _json.dumps({
        "model": "project.project",
        "domain": '[["active","=",true]]',
        "fields": '["name","id"]',
        "project_code": "_probe",
        "limit": 5,
    }).encode()

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=services_catalog.PROBE_TIMEOUT_SECONDS * 5) as resp:  # noqa: S310
            status = resp.status
            body_bytes = resp.read(65536)
    except HTTPError as exc:
        detail = services_catalog._detail_for_exception(exc, None)
        auth_failed = exc.code in (401, 403)
        return ProbeFacts(
            network_ok=True,
            auth_ok=False if auth_failed else None,
            live_data_ok=False,
            data_source="live",
            evidence=f"Odoo webhook HTTP {exc.code}: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )
    except Exception as exc:
        detail = services_catalog._detail_for_exception(exc, None)
        return ProbeFacts(
            network_ok=False,
            live_data_ok=False,
            data_source="live",
            evidence=f"Odoo webhook unreachable: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )

    if status != 200:
        return ProbeFacts(
            network_ok=True,
            live_data_ok=False,
            data_source="live",
            evidence=f"Odoo webhook returned HTTP {status}",
            last_error_safe=f"unexpected HTTP {status}",
            probed_at=ts,
        )

    try:
        parsed = _json.loads(body_bytes.decode("utf-8", "replace"))
    except Exception:
        return ProbeFacts(
            network_ok=True,
            live_data_ok=False,
            data_source="live",
            evidence="Odoo webhook returned non-JSON body",
            last_error_safe="non-JSON response from Odoo webhook",
            probed_at=ts,
        )

    evidence_list = parsed.get("evidence") if isinstance(parsed, dict) else None
    if not evidence_list:
        return ProbeFacts(
            network_ok=True,
            auth_ok=True,
            live_data_ok=False,
            data_source="live",
            evidence="Odoo webhook reachable but returned empty evidence list",
            probed_at=ts,
        )

    first = evidence_list[0] if isinstance(evidence_list, list) else {}
    required_fields = ("evidence_id", "title", "source_uri")
    missing_fields = [f for f in required_fields if not first.get(f)]
    source_type_ok = first.get("source_type") == "odoo"

    if missing_fields or not source_type_ok:
        return ProbeFacts(
            network_ok=True,
            auth_ok=True,
            live_data_ok=False,
            data_source="live",
            evidence=(
                f"Odoo evidence malformed: source_type={first.get('source_type')!r}"
                + (f", missing fields: {missing_fields}" if missing_fields else "")
            ),
            probed_at=ts,
        )

    return ProbeFacts(
        network_ok=True,
        auth_ok=True,
        permission_ok=True,
        live_data_ok=True,
        data_source="live",
        sample_count=len(evidence_list),
        evidence=(
            f"Odoo webhook live: {len(evidence_list)} evidence item(s) returned "
            f"(source_type=odoo)"
        ),
        probed_at=ts,
        success_at=ts,
    )


def _probe_public_edge() -> ProbeFacts:
    """Probe the public HTTPS edge end-to-end: Cloudflare Tunnel → Caddy → app.

    A JSON 200 from ``https://{public_hostname}/healthz`` proves the whole public
    chain is live. Anything else is NETWORK_FAILED — never assumed working.
    """
    host = (settings.public_hostname or "").strip()
    ts = _now()
    if host in _NON_PUBLIC_HOSTS:
        return ProbeFacts(
            network_ok=None,
            data_source="none",
            evidence="PUBLIC_HOSTNAME not set to a public domain",
            probed_at=ts,
        )
    url = f"https://{host}/healthz"
    try:
        import json as _json
        from urllib.request import urlopen

        with urlopen(url, timeout=services_catalog.PROBE_TIMEOUT_SECONDS) as resp:  # noqa: S310
            status = resp.status
            body = resp.read(512)
        try:
            parsed = _json.loads(body.decode("utf-8", "replace"))
            is_app_json = isinstance(parsed, dict) and parsed.get("status") == "ok"
        except Exception:
            is_app_json = False
        if status == 200 and is_app_json:
            return ProbeFacts(
                network_ok=True,
                live_data_ok=True,
                data_source="live",
                evidence=f"HTTPS 200 + app JSON from edge /healthz (Cloudflare Tunnel + Caddy, {host})",
                probed_at=ts,
                success_at=ts,
            )
        return ProbeFacts(
            network_ok=True,
            live_data_ok=False,
            data_source="live",
            evidence=f"edge /healthz returned HTTP {status} but not the app JSON",
            last_error_safe=f"unexpected edge response HTTP {status}",
            probed_at=ts,
        )
    except Exception as exc:
        detail = services_catalog._detail_for_exception(exc, host)
        return ProbeFacts(
            network_ok=False,
            live_data_ok=False,
            data_source="live",
            evidence=f"edge unreachable: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )


def _probe_caddy_routing() -> ProbeFacts:
    """Confirm Caddy proxies API routes (JSON) AND serves the SPA (HTML).

    Uses the public edge: ``/healthz`` must be JSON (API proxied) and ``/`` must
    be HTML (SPA served). Proves route separation without business data.
    """
    host = (settings.public_hostname or "").strip()
    ts = _now()
    if host in _NON_PUBLIC_HOSTS:
        return ProbeFacts(
            network_ok=None,
            data_source="none",
            evidence="PUBLIC_HOSTNAME not set to a public domain",
            probed_at=ts,
        )
    try:
        from urllib.request import urlopen

        with urlopen(  # noqa: S310
            f"https://{host}/healthz", timeout=services_catalog.PROBE_TIMEOUT_SECONDS
        ) as resp:
            api_json = resp.status == 200 and "json" in resp.headers.get(
                "content-type", ""
            ).lower()
        with urlopen(  # noqa: S310
            f"https://{host}/", timeout=services_catalog.PROBE_TIMEOUT_SECONDS
        ) as resp:
            spa_html = resp.status == 200 and "html" in resp.headers.get(
                "content-type", ""
            ).lower()
        if api_json and spa_html:
            return ProbeFacts(
                network_ok=True,
                live_data_ok=True,
                data_source="live",
                evidence="Caddy proxies /healthz as JSON and serves SPA HTML at /",
                probed_at=ts,
                success_at=ts,
            )
        return ProbeFacts(
            network_ok=True,
            live_data_ok=False,
            data_source="live",
            evidence=f"Caddy routing incomplete (api_json={api_json}, spa_html={spa_html})",
            last_error_safe="caddy route check failed",
            probed_at=ts,
        )
    except Exception as exc:
        detail = services_catalog._detail_for_exception(exc, host)
        return ProbeFacts(
            network_ok=False,
            live_data_ok=False,
            data_source="live",
            evidence=f"edge unreachable for Caddy check: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )


def _parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _entra_validation_marker() -> dict[str, Any] | None:
    """Return the redacted Entra validation marker from the UAT evidence doc.

    The marker is a JSON object embedded in an HTML comment. It contains only
    safe claims/check booleans, never the token value.
    """
    try:
        text = _ENTRA_VALIDATION_EVIDENCE_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith(_ENTRA_VALIDATION_MARKER_PREFIX):
            continue
        if not line.endswith(_ENTRA_VALIDATION_MARKER_SUFFIX):
            return None
        payload = line.removeprefix(_ENTRA_VALIDATION_MARKER_PREFIX)
        payload = payload.removesuffix(_ENTRA_VALIDATION_MARKER_SUFFIX).strip()
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return None


def _entra_validation_evidence_facts(ts: str) -> ProbeFacts | None:
    """Return ProbeFacts derived from the persisted Entra validation marker.

    Returns ``None`` if no valid evidence marker exists (no file, invalid
    marker, or FAIL result) — the caller treats None as "no evidence".

    When a valid marker exists but the validated token has expired, returns
    facts with ``data_source="evidence"`` and ``live_data_ok=False``.  This
    signals ``PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`` in ``classify()``, which is
    semantically distinct from ``CONFIGURED_NOT_TESTED``: the connector was
    verified before — it just needs revalidation, not first-time setup.

    When a valid marker exists and the token is still live, returns facts with
    ``data_source="evidence"`` and ``live_data_ok=True`` → ``VALIDATED``.
    """
    marker = _entra_validation_marker()
    if marker is None:
        return None
    checks = marker.get("checks")
    if not isinstance(checks, dict):
        return None
    required_checks = (
        "oidc_discovery_ok",
        "jwks_ok",
        "issuer_ok",
        "audience_ok",
        "tenant_ok",
        "expiry_valid",
        "role_present",
        "me_role_ok",
    )
    if marker.get("result") != "PASS" or not all(checks.get(k) is True for k in required_checks):
        return None

    expires_at = _parse_utc_datetime(marker.get("token_expires_at"))
    validated_at = _parse_utc_datetime(marker.get("validated_at"))
    if expires_at is None or validated_at is None:
        return None

    role = services_catalog._sanitize_detail(str(marker.get("role") or "unknown"))
    now = datetime.now(timezone.utc)

    if expires_at <= now:
        # Evidence exists but the token that was validated has since expired.
        # data_source="evidence" + live_data_ok=False signals
        # PREVIOUSLY_VALIDATED_TOKEN_EXPIRED (not CONFIGURED_NOT_TESTED).
        expired_text = expires_at.isoformat().replace("+00:00", "Z")
        return ProbeFacts(
            network_ok=True,
            auth_ok=None,
            live_data_ok=False,
            data_source="evidence",
            evidence=(
                f"Previous Entra validation for role={role} expired and "
                "requires revalidation."
            ),
            probed_at=ts,
            success_at=validated_at.isoformat().replace("+00:00", "Z"),
            token_expires_at=expired_text,
        )

    expires_text = expires_at.isoformat().replace("+00:00", "Z")
    return ProbeFacts(
        network_ok=True,
        auth_ok=True,
        permission_ok=True,
        live_data_ok=True,
        data_source="evidence",
        sample_count=1,
        evidence=(
            "Fresh Entra auth validation accepted: OIDC/JWKS, issuer, audience, "
            f"tenant, expiry, role and /me passed for role={role}; "
            f"token expires at {expires_text}"
        ),
        probed_at=ts,
        success_at=validated_at.isoformat().replace("+00:00", "Z"),
        token_expires_at=expires_text,
    )


def _probe_entra_oidc_jwks(tenant: str, ts: str) -> ProbeFacts:
    url = f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
    try:
        from urllib.request import urlopen

        with urlopen(url, timeout=services_catalog.PROBE_TIMEOUT_SECONDS) as resp:  # noqa: S310
            ok = resp.status == 200
            doc = json.loads(resp.read()) if ok else {}
        jwks_uri = doc.get("jwks_uri")
        if not jwks_uri:
            return ProbeFacts(
                network_ok=True,
                auth_ok=None,
                live_data_ok=None,
                data_source="none",
                evidence="OIDC discovery reachable but JWKS URI missing",
                last_error_safe="OIDC discovery missing jwks_uri",
                probed_at=ts,
            )
        with urlopen(jwks_uri, timeout=services_catalog.PROBE_TIMEOUT_SECONDS) as resp:  # noqa: S310
            jwks_ok = resp.status == 200
        if not (ok and jwks_ok):
            return ProbeFacts(
                network_ok=True,
                auth_ok=None,
                live_data_ok=None,
                data_source="none",
                evidence="OIDC discovery or JWKS not reachable",
                last_error_safe="OIDC/JWKS reachability check failed",
                probed_at=ts,
            )
        return ProbeFacts(
            network_ok=True,
            auth_ok=None,
            live_data_ok=None,
            data_source="none",
            evidence="OIDC discovery and JWKS reachable",
            probed_at=ts,
            success_at=ts,
        )
    except Exception as exc:
        detail = services_catalog._detail_for_exception(exc, None)
        return ProbeFacts(
            network_ok=False,
            data_source="none",
            evidence=f"OIDC discovery or JWKS unreachable: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )


def _probe_entra() -> ProbeFacts:
    """Reach tenant OIDC/JWKS and accept only fresh redacted token proof.

    The dashboard never reads a token. Entra moves to ``VALIDATED`` only when
    an operator-run validation script records a redacted PASS marker whose token
    expiry is still in the future.

    Token expiry is handled transparently:
    - Fresh evidence → VALIDATED (classify handles data_source=evidence + live=True)
    - Expired evidence → PREVIOUSLY_VALIDATED_TOKEN_EXPIRED (data_source=evidence + live=False)
    - No evidence → CONFIGURED_NOT_TESTED (None returned here → fallback ProbeFacts)
    """
    tenant = (settings.entra_tenant_id or "").strip()
    ts = _now()
    if not tenant:
        return ProbeFacts(data_source="none", evidence="ENTRA_TENANT_ID not set", probed_at=ts)
    oidc_facts = _probe_entra_oidc_jwks(tenant, ts)
    if oidc_facts.network_ok is not True:
        return oidc_facts
    validation_facts = _entra_validation_evidence_facts(ts)
    if validation_facts is not None:
        return validation_facts
    return ProbeFacts(
        network_ok=True,
        auth_ok=None,
        live_data_ok=None,  # no token validated → cannot claim live
        data_source="none",
        evidence="OIDC discovery and JWKS reachable; no fresh user-token validation evidence",
        probed_at=ts,
        success_at=oidc_facts.success_at,
    )


# ---------------------------------------------------------------------------
# Admin revalidation — writes redacted evidence, never stores raw token
# ---------------------------------------------------------------------------


def write_entra_validation_evidence_marker(token: str, *, me_ok: bool) -> dict[str, Any]:
    """Validate a user bearer token and write redacted evidence to the evidence file.

    Accepts the raw token **only for the duration of this call**. The token is:
    - Passed to EntraJWTValidator.validate() for cryptographic verification.
    - Used to decode the ``exp`` claim (already verified above).
    - Never written to any file, log, or return value.

    What IS written to the evidence file after all checks pass (only):
    - result: "PASS"
    - validated_at: ISO timestamp of this call
    - token_expires_at: ISO timestamp of the token expiry
    - role: the resolved role string (sanitised)
    - me_role: same as role
    - checks: dict of boolean pass/fail for each validation step

    Raises ValueError if the token is invalid or already expired.
    Returns the redacted payload dict (no token, no secret values).
    """
    from apps.edr.auth.validator import EntraJWTValidator

    tenant = (settings.entra_tenant_id or "").strip()
    client_id = (settings.entra_client_id or "").strip()
    if not tenant or not client_id:
        raise ValueError("Entra not configured (ENTRA_TENANT_ID or ENTRA_CLIENT_ID missing)")

    validator = EntraJWTValidator(tenant, client_id)
    try:
        jwt_claims = validator.validate(token)
    except Exception as exc:
        raise ValueError("Token validation failed") from exc

    try:
        import jwt as _pyjwt  # PyJWT (validated in EntraJWTValidator above)
        unverified = _pyjwt.decode(token, options={"verify_signature": False})
        exp_ts = int(unverified.get("exp", 0))
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    except Exception as exc:
        raise ValueError("Cannot read token expiry claim") from exc

    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise ValueError(
            "Token is already expired — cannot revalidate with an expired token. "
            "Log in again and retry."
        )
    if not me_ok:
        raise ValueError(
            "Microsoft session validation failed. Sign in again and retry."
        )

    role = services_catalog._sanitize_detail(str(jwt_claims.role or "unknown"))
    expires_iso = expires_at.isoformat().replace("+00:00", "Z")
    validated_iso = now.isoformat().replace("+00:00", "Z")

    payload: dict[str, Any] = {
        "result": "PASS",
        "validated_at": validated_iso,
        "token_expires_at": expires_iso,
        "role": role,
        "me_role": role,
        "checks": {
            "oidc_discovery_ok": True,
            "jwks_ok": True,
            "issuer_ok": True,
            "audience_ok": True,
            "tenant_ok": True,
            "expiry_valid": True,
            "role_present": bool(jwt_claims.role),
            "me_role_ok": me_ok,
        },
    }

    # Write marker to evidence file. No raw token is written.
    marker_line = (
        f"{_ENTRA_VALIDATION_MARKER_PREFIX} "
        + json.dumps(payload, sort_keys=True)
        + f" {_ENTRA_VALIDATION_MARKER_SUFFIX}\n"
    )
    _ENTRA_VALIDATION_EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ENTRA_VALIDATION_EVIDENCE_PATH.write_text(marker_line, encoding="utf-8")

    # Return only redacted evidence — no token, no secret values.
    return payload


# ---------------------------------------------------------------------------
# Connector registry — the dependencies the dashboard must tell the truth about
# ---------------------------------------------------------------------------


CONNECTOR_SPECS: tuple[ConnectorSpec, ...] = (
    # --- Core platform (reachability is the liveness proof) ---
    ConnectorSpec("postgres", "PostgreSQL", "core_platform",
                  ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER"),
                  ("POSTGRES_PASSWORD",), True, probe="_probe_postgres"),
    ConnectorSpec("redis", "Redis", "core_platform", ("REDIS_URL",), (), True,
                  probe="_probe_redis"),
    ConnectorSpec("qdrant", "Qdrant", "core_platform", ("QDRANT_URL",), (), True,
                  probe="_probe_qdrant"),
    ConnectorSpec("minio", "MinIO", "core_platform",
                  ("MINIO_ENDPOINT", "MINIO_BUCKET", "MINIO_ACCESS_KEY"),
                  ("MINIO_SECRET_KEY",), True, probe="_probe_minio"),
    # --- Public edge ---
    ConnectorSpec("public_edge", "Cloudflare Tunnel / public edge", "edge",
                  ("PUBLIC_HOSTNAME",), (), True, probe="_probe_public_edge"),
    ConnectorSpec("caddy_routing", "Caddy routing", "edge",
                  ("PUBLIC_HOSTNAME",), (), True, probe="_probe_caddy_routing"),
    # --- Auth ---
    ConnectorSpec("entra_auth", "Microsoft Entra authentication", "auth",
                  ("ENTRA_CLIENT_ID", "ENTRA_TENANT_ID"), (), True,
                  probe="_probe_entra",
                  note="Live proof requires a validated user token; not testable server-side."),
    # --- External data connectors (orchestrated via n8n) ---
    ConnectorSpec("n8n", "n8n webhook", "external_connector",
                  ("N8N_BASE_URL",), ("N8N_WEBHOOK_TOKEN",), True, probe="_probe_n8n"),
    ConnectorSpec("sharepoint", "SharePoint", "external_connector",
                  ("SHAREPOINT_SEARCH_WEBHOOK", "N8N_BASE_URL"),
                  ("N8N_WEBHOOK_TOKEN",), True,
                  probe="_probe_sharepoint_source_mapping",
                  note="Verified from current PRJ-001/PRJ-002 source mapping evidence."),
    ConnectorSpec("microsoft_graph", "Email / mailbox connector", "external_connector",
                  ("EMAIL_SEARCH_WEBHOOK", "N8N_BASE_URL"),
                  ("N8N_WEBHOOK_TOKEN",), True,
                  probe="_probe_microsoft_graph_source_mapping",
                  note="Verified from current PRJ-001/PRJ-002 group mailbox/member evidence."),
    # ownCloud is intentionally disabled — credentials are not configured and
    # ownCloud is not part of the enabled source set for any project.
    ConnectorSpec("owncloud", "ownCloud", "external_connector",
                  ("OWNCLOUD_LIST_WEBHOOK", "OWNCLOUD_USERNAME", "N8N_BASE_URL"),
                  ("OWNCLOUD_PASSWORD", "N8N_WEBHOOK_TOKEN"),
                  required_for_go_live=False,
                  note="ownCloud is disabled — not part of any project's enabled sources.",
                  disabled=True),
    ConnectorSpec("odoo", "Odoo", "external_connector",
                  ("ODOO_READ_WEBHOOK", "ODOO_URL", "ODOO_DATABASE", "ODOO_USERNAME",
                   "N8N_BASE_URL"),
                  ("ODOO_API_KEY", "N8N_WEBHOOK_TOKEN"), True, probe="_probe_odoo"),
    # --- AI providers (no billable probe here) ---
    ConnectorSpec("anthropic", "Anthropic (report generation)", "ai_provider",
                  (), ("ANTHROPIC_API_KEY",), True,
                  note="Generation LLM. No billable probe; key-presence only."),
    ConnectorSpec("voyage", "Voyage (embeddings)", "ai_provider",
                  (), ("VOYAGE_API_KEY",), True,
                  note="Embeddings. No billable probe; key-presence only."),
    ConnectorSpec("cohere", "Cohere (rerank)", "ai_provider",
                  (), ("COHERE_API_KEY",), True,
                  note="Rerank. No billable probe; key-presence only."),
)

CONNECTOR_SPEC_BY_NAME: dict[str, ConnectorSpec] = {s.name: s for s in CONNECTOR_SPECS}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _state_from_facts(facts: ProbeFacts) -> ConnectorState:
    """Map probe facts to a truth state.

    Invariant: fixture/mock data can NEVER be LIVE_OK — it is MOCK_ONLY.

    CONNECTED_NO_DATA applies whenever the server was reachable (network_ok=True)
    but no live data was confirmed (live_data_ok=False). This covers HTTP error
    responses from the server (e.g. 404 webhook-not-found, 500 server error) as
    well as reachable-but-empty responses — all cases where the probe ran and
    produced a definitive non-success result.  The auth_ok guard is intentionally
    absent here: auth state is unknown for HTTP errors that aren't 401/403, and
    those cases must not fall through to CONFIGURED_NOT_TESTED (which implies the
    probe was never attempted).

    Note: ``data_source="evidence"`` with ``live_data_ok=False`` is intentionally
    NOT handled here — that combination is Entra-specific and is mapped to
    ``PREVIOUSLY_VALIDATED_TOKEN_EXPIRED`` by ``classify()`` before reaching this
    function.
    """
    if facts.data_source in ("mock", "fixture"):
        return ConnectorState.MOCK_ONLY
    if facts.data_source == "evidence" and facts.live_data_ok is True:
        return ConnectorState.VERIFIED_FROM_EVIDENCE
    if facts.network_ok is False:
        return ConnectorState.NETWORK_FAILED
    if facts.auth_ok is False:
        return ConnectorState.AUTH_FAILED
    if facts.permission_ok is False:
        return ConnectorState.PERMISSION_FAILED
    if facts.live_data_ok is True:
        return ConnectorState.LIVE_OK
    if facts.live_data_ok is False and facts.network_ok is True:
        return ConnectorState.CONNECTED_NO_DATA
    # Reachable but nothing was actually validated as live data → not green.
    return ConnectorState.CONFIGURED_NOT_TESTED


_STATE_LABELS: dict[ConnectorState, str] = {
    ConnectorState.NOT_CONFIGURED: "Not configured",
    ConnectorState.CONFIGURED_NOT_TESTED: "Configured — not tested",
    ConnectorState.AUTH_FAILED: "Authentication failed",
    ConnectorState.PERMISSION_FAILED: "Permission/scope missing",
    ConnectorState.NETWORK_FAILED: "Unreachable",
    ConnectorState.CONNECTED_NO_DATA: "Connected — no data",
    ConnectorState.VALIDATED: "Validated",
    ConnectorState.PREVIOUSLY_VALIDATED_TOKEN_EXPIRED: "Previously validated — token expired",
    ConnectorState.VERIFIED_FROM_EVIDENCE: "Verified from evidence",
    ConnectorState.LIVE_OK: "Live",
    ConnectorState.MOCK_ONLY: "Sample/mock data only",
    ConnectorState.DISABLED: "Disabled",
    ConnectorState.UNKNOWN: "Unknown",
}


def _state_label(state: ConnectorState) -> str:
    return _STATE_LABELS.get(state, state.value)


def classify(spec: ConnectorSpec, *, run_probe: bool = True) -> ConnectorTruth:
    """Classify one connector into a truth state. Never raises."""
    # Disabled connectors are intentionally turned off: return DISABLED immediately
    # without checking credentials or running probes. They never block go-live.
    if spec.disabled:
        return ConnectorTruth(
            name=spec.name,
            display_name=spec.display_name,
            group=spec.group,
            state=ConnectorState.DISABLED,
            summary=f"{spec.display_name}: Disabled",
            configured=False,
            missing_required_config=[],
            secret_present=False,
            auth_ok=None,
            network_ok=None,
            permission_ok=None,
            live_data_ok=None,
            data_source="none",
            last_probe_at=None,
            last_success_at=None,
            token_expires_at=None,
            last_error_safe=None,
            sample_count=None,
            evidence=services_catalog._sanitize_detail(
                spec.note or "intentionally disabled"
            ),
            required_for_go_live=spec.required_for_go_live,
            blocks_go_live=False,
        )

    missing = [k for k in spec.required_nonsecret if not _is_present(k)]
    secret_present = (
        all(_is_present(k) for k in spec.required_secrets)
        if spec.required_secrets
        else True
    )
    configured = (not missing) and secret_present

    facts: ProbeFacts | None = None
    if configured and run_probe and spec.probe is not None:
        try:
            facts = globals()[spec.probe]()
        except Exception:  # pragma: no cover - probes already guard themselves
            facts = ProbeFacts(last_error_safe="probe raised unexpectedly")

    if not configured:
        state = ConnectorState.NOT_CONFIGURED
        summary = f"{spec.display_name}: Not configured"
        missing_bits = list(missing)
        if not secret_present:
            missing_bits.append("<required secret missing>")
        evidence = "missing required config: " + ", ".join(missing_bits)
        facts = facts or ProbeFacts()
    elif facts is None:
        state = ConnectorState.CONFIGURED_NOT_TESTED
        summary = f"{spec.display_name}: Configured — not tested"
        evidence = spec.note or "configured; no live probe available server-side"
        facts = ProbeFacts(evidence=evidence)
    else:
        if (
            spec.name == "entra_auth"
            and facts.data_source == "evidence"
            and facts.live_data_ok is True
        ):
            # Fresh validation evidence present and token still live.
            state = ConnectorState.VALIDATED
        elif (
            spec.name == "entra_auth"
            and facts.data_source == "evidence"
            and facts.live_data_ok is False
        ):
            # Previous validation evidence exists but the validated token expired.
            # This is distinct from CONFIGURED_NOT_TESTED: the connector was proven
            # to work before — it needs revalidation, not first-time setup.
            state = ConnectorState.PREVIOUSLY_VALIDATED_TOKEN_EXPIRED
        else:
            state = _state_from_facts(facts)
        summary = f"{spec.display_name}: {_state_label(state)}"
        evidence = facts.evidence or spec.note

    blocks_go_live = spec.required_for_go_live and not _satisfies_go_live(state)

    return ConnectorTruth(
        name=spec.name,
        display_name=spec.display_name,
        group=spec.group,
        state=state,
        summary=summary,
        configured=configured,
        missing_required_config=missing,
        secret_present=secret_present,
        auth_ok=facts.auth_ok,
        network_ok=facts.network_ok,
        permission_ok=facts.permission_ok,
        live_data_ok=facts.live_data_ok,
        data_source=facts.data_source,
        last_probe_at=facts.probed_at,
        last_success_at=facts.success_at,
        token_expires_at=facts.token_expires_at,
        last_error_safe=services_catalog._sanitize_detail(facts.last_error_safe)
        if facts.last_error_safe
        else None,
        sample_count=facts.sample_count,
        evidence=services_catalog._sanitize_detail(evidence),
        required_for_go_live=spec.required_for_go_live,
        blocks_go_live=blocks_go_live,
    )


# ---------------------------------------------------------------------------
# Report + readiness banner
# ---------------------------------------------------------------------------


def build_report(*, run_probes: bool = True) -> ConnectorTruthReport:
    truths = [classify(spec, run_probe=run_probes) for spec in CONNECTOR_SPECS]
    by_group: dict[str, list[ConnectorTruth]] = {
        "core_platform": [],
        "auth": [],
        "external_connector": [],
        "ai_provider": [],
        "edge": [],
    }
    for t in truths:
        by_group[t.group].append(t)

    blocking = [t.name for t in truths if t.blocks_go_live]
    readiness, reason = _compute_readiness(truths)
    report_gen, report_reason = _report_generation_status(by_group["ai_provider"])

    return ConnectorTruthReport(
        readiness=readiness,
        readiness_reason=reason,
        report_generation=report_gen,
        report_generation_reason=report_reason,
        generated_at=_now(),
        core_platform=by_group["core_platform"],
        auth=by_group["auth"],
        external_connectors=by_group["external_connector"],
        ai_providers=by_group["ai_provider"],
        edge=by_group["edge"],
        blocking=blocking,
    )


def _compute_readiness(truths: list[ConnectorTruth]) -> tuple[Readiness, str]:
    """Three-tier readiness, biased to honesty.

    - NOT_READY  : a core platform or edge dependency is not LIVE_OK, or Entra
                   auth is not even configured — the app shell itself isn't proven.
    - READY_FOR_UAT : every go-live-required dependency is LIVE_OK, VALIDATED,
                   or explicitly VERIFIED_FROM_EVIDENCE by the truth model.
    - PARTIAL_READY : core + edge live and auth configured, but some required
                   connectors/providers are still pending live validation.
    """
    by_name = {t.name: t for t in truths}
    core_edge = [t for t in truths if t.group in ("core_platform", "edge")]
    core_edge_down = [t.name for t in core_edge if t.state != ConnectorState.LIVE_OK]
    auth = by_name.get("entra_auth")
    auth_unconfigured = auth is not None and not auth.configured

    if core_edge_down or auth_unconfigured:
        bits = []
        if core_edge_down:
            bits.append("core/edge not live: " + ", ".join(core_edge_down))
        if auth_unconfigured:
            bits.append("Entra auth not configured")
        return "NOT_READY", "; ".join(bits)

    required = [t for t in truths if t.required_for_go_live]
    not_live = [t.name for t in required if not _satisfies_go_live(t.state)]
    if not not_live:
        return "READY_FOR_UAT", (
            "all required dependencies passed a live probe or accepted current evidence"
        )
    return (
        "PARTIAL_READY",
        "core platform, edge and login are up; pending live validation: "
        + ", ".join(not_live),
    )


def _report_generation_status(
    ai: list[ConnectorTruth],
) -> tuple[Literal["READY", "DEGRADED", "BLOCKED"], str]:
    by_name = {t.name: t for t in ai}
    anthropic = by_name.get("anthropic")
    if anthropic is None or not anthropic.configured:
        return "BLOCKED", "provider keys missing — ANTHROPIC_API_KEY not set"
    missing = [t.display_name for t in ai if not t.configured]
    if missing:
        return "DEGRADED", "secondary providers missing: " + ", ".join(missing)
    return "READY", "provider keys present (not yet live-verified)"


def _satisfies_go_live(state: ConnectorState) -> bool:
    return state in {
        ConnectorState.LIVE_OK,
        ConnectorState.VALIDATED,
        ConnectorState.VERIFIED_FROM_EVIDENCE,
    }


# ---------------------------------------------------------------------------
# Source-mapping helpers (SharePoint / Graph evidence probes)
# ---------------------------------------------------------------------------


def _jsonish(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return fallback


async def _source_mapping_rows_from_db_async() -> list[dict[str, Any]]:
    import asyncpg

    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        timeout=1.0,
    )
    try:
        rows = await conn.fetch(
            """
            SELECT project_code, mapping_status, enabled_sources, sharepoint,
                   microsoft, odoo
            FROM source_mappings
            WHERE project_code = ANY($1::text[])
            ORDER BY project_code
            """,
            list(_VERIFIED_PROJECT_MEMBER_COUNTS),
        )
    finally:
        await conn.close()
    return [
        {
            "project_code": row["project_code"],
            "mapping_status": row["mapping_status"],
            "enabled_sources": _jsonish(row["enabled_sources"], []),
            "sharepoint": _jsonish(row["sharepoint"], {}),
            "microsoft": _jsonish(row["microsoft"], {}),
            "odoo": _jsonish(row["odoo"], {}),
        }
        for row in rows
    ]


def _source_mapping_rows_from_db() -> list[dict[str, Any]]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        return []
    try:
        return asyncio.run(_source_mapping_rows_from_db_async())
    except Exception:
        return []


def _source_mapping_rows_from_file() -> list[dict[str, Any]]:
    try:
        raw = json.loads(_SOURCE_MAPPING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw if isinstance(raw, list) else list(raw.values()) if isinstance(raw, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _source_mapping_rows() -> list[dict[str, Any]]:
    return _source_mapping_rows_from_db() or _source_mapping_rows_from_file()


def _real_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    return "example" not in lowered and "placeholder" not in lowered


def _verified_project_rows() -> tuple[list[dict[str, Any]], list[str]]:
    rows_by_code = {
        str(row.get("project_code")): row
        for row in _source_mapping_rows()
        if str(row.get("project_code")) in _VERIFIED_PROJECT_MEMBER_COUNTS
    }
    missing = [code for code in _VERIFIED_PROJECT_MEMBER_COUNTS if code not in rows_by_code]
    return [rows_by_code[code] for code in _VERIFIED_PROJECT_MEMBER_COUNTS if code in rows_by_code], missing


def _probe_sharepoint_source_mapping() -> ProbeFacts:
    """Verify SharePoint from current PRJ-001/PRJ-002 source mapping facts.

    This is not a live Graph call. It accepts only current persisted runtime
    facts (DB first, checked-in mapping fallback) that prove SharePoint site and
    drive discovery already succeeded for the two operator-verified projects.
    """
    ts = _now()
    rows, missing = _verified_project_rows()
    verified: list[str] = []
    blockers = [f"missing {code}" for code in missing]
    for row in rows:
        code = str(row.get("project_code"))
        enabled = set(row.get("enabled_sources") or [])
        sharepoint = row.get("sharepoint") or {}
        if row.get("mapping_status") != "complete":
            blockers.append(f"{code}: mapping_status is not complete")
            continue
        if "sharepoint" not in enabled:
            blockers.append(f"{code}: sharepoint source not enabled")
            continue
        if not _real_value(sharepoint.get("site_id")) or not _real_value(
            sharepoint.get("drive_id")
        ):
            blockers.append(f"{code}: verified SharePoint site/drive missing")
            continue
        verified.append(code)

    if blockers:
        return ProbeFacts(
            data_source="none",
            evidence="SharePoint source mapping verification incomplete: "
            + "; ".join(blockers),
            probed_at=ts,
        )
    return ProbeFacts(
        network_ok=True,
        auth_ok=True,
        permission_ok=True,
        live_data_ok=True,
        data_source="evidence",
        sample_count=len(verified),
        evidence=(
            "Current source_mappings verify SharePoint site/drive coordinates "
            f"for {', '.join(verified)}"
        ),
        probed_at=ts,
        success_at=ts,
    )


def _probe_microsoft_graph_source_mapping() -> ProbeFacts:
    """Verify Email/Graph from current group enrichment facts.

    This does not call Microsoft Graph. It reconciles the dashboard with the
    already-persisted GROUP_MEMBERS_READ evidence for PRJ-001 and PRJ-002.
    """
    ts = _now()
    rows, missing = _verified_project_rows()
    verified: list[str] = []
    blockers = [f"missing {code}" for code in missing]
    total_members = 0
    for row in rows:
        code = str(row.get("project_code"))
        expected_members = _VERIFIED_PROJECT_MEMBER_COUNTS[code]
        enabled = set(row.get("enabled_sources") or [])
        microsoft = row.get("microsoft") or {}
        group = microsoft.get("group") or {}
        member_count = microsoft.get("member_count")
        try:
            member_count_int = int(member_count)
        except (TypeError, ValueError):
            member_count_int = -1
        if "email" not in enabled:
            blockers.append(f"{code}: email source not enabled")
            continue
        if microsoft.get("group_membership_status") != _VERIFIED_GROUP_STATUS:
            blockers.append(f"{code}: group membership not read")
            continue
        if not group.get("mail_enabled") or not _real_value(group.get("mail")):
            blockers.append(f"{code}: verified group mailbox missing")
            continue
        if member_count_int != expected_members:
            blockers.append(f"{code}: member_count {member_count_int} != {expected_members}")
            continue
        if microsoft.get("missing_permissions") or microsoft.get("blockers"):
            blockers.append(f"{code}: Microsoft enrichment has blockers")
            continue
        verified.append(f"{code} ({member_count_int} members)")
        total_members += member_count_int

    if blockers:
        return ProbeFacts(
            data_source="none",
            evidence="Microsoft Graph/email group enrichment incomplete: "
            + "; ".join(blockers),
            probed_at=ts,
        )
    return ProbeFacts(
        network_ok=True,
        auth_ok=True,
        permission_ok=True,
        live_data_ok=True,
        data_source="evidence",
        sample_count=total_members,
        evidence=(
            "Current source_mappings verify Microsoft group mailbox/member "
            f"enrichment for {', '.join(verified)}"
        ),
        probed_at=ts,
        success_at=ts,
    )
