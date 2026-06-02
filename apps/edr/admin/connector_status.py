"""Connector truth-status service.

Single rule: **never report a connector green unless a real live probe proved
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
  billable/leaky call (Entra auth, AI providers, Odoo/ownCloud/SharePoint/email
  data connectors) are deliberately capped at ``CONFIGURED_NOT_TESTED`` when
  configured and ``NOT_CONFIGURED`` when not — never green.
- ``data_source`` of ``mock``/``fixture`` can never map to ``LIVE_OK`` (it maps
  to ``MOCK_ONLY``); this is enforced in :func:`_state_from_facts`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

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
    LIVE_OK = "LIVE_OK"
    MOCK_ONLY = "MOCK_ONLY"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


DataSource = Literal["live", "mock", "fixture", "none"]
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


def _probe_entra() -> ProbeFacts:
    """Reach the tenant OIDC metadata (network only). Auth is NOT proven here.

    A real auth proof requires a live user token to validate — which does not
    exist at probe time — so this never reports LIVE_OK; at most it records that
    the issuer's discovery document is reachable.
    """
    tenant = (settings.entra_tenant_id or "").strip()
    ts = _now()
    if not tenant:
        return ProbeFacts(data_source="none", evidence="ENTRA_TENANT_ID not set", probed_at=ts)
    url = f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
    try:
        from urllib.request import urlopen

        with urlopen(url, timeout=services_catalog.PROBE_TIMEOUT_SECONDS) as resp:  # noqa: S310
            ok = resp.status == 200
        return ProbeFacts(
            network_ok=ok,
            auth_ok=None,
            live_data_ok=None,  # no token validated → cannot claim live
            data_source="none",
            evidence=(
                "OIDC discovery reachable; no live user token validated yet"
                if ok
                else "OIDC discovery not reachable"
            ),
            probed_at=ts,
            success_at=ts if ok else None,
        )
    except Exception as exc:
        detail = services_catalog._detail_for_exception(exc, None)
        return ProbeFacts(
            network_ok=False,
            data_source="none",
            evidence=f"OIDC discovery unreachable: {detail}",
            last_error_safe=detail,
            probed_at=ts,
        )


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
                  note="Graph creds live inside n8n; no safe server-side data probe."),
    ConnectorSpec("microsoft_graph", "Email / mailbox connector", "external_connector",
                  ("EMAIL_SEARCH_WEBHOOK", "N8N_BASE_URL"),
                  ("N8N_WEBHOOK_TOKEN",), True,
                  note="Graph mailbox creds live inside n8n; no safe server-side data probe."),
    ConnectorSpec("owncloud", "ownCloud", "external_connector",
                  ("OWNCLOUD_LIST_WEBHOOK", "OWNCLOUD_USERNAME", "N8N_BASE_URL"),
                  ("OWNCLOUD_PASSWORD", "N8N_WEBHOOK_TOKEN"), True),
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
    """
    if facts.data_source in ("mock", "fixture"):
        return ConnectorState.MOCK_ONLY
    if facts.network_ok is False:
        return ConnectorState.NETWORK_FAILED
    if facts.auth_ok is False:
        return ConnectorState.AUTH_FAILED
    if facts.permission_ok is False:
        return ConnectorState.PERMISSION_FAILED
    if facts.live_data_ok is True:
        return ConnectorState.LIVE_OK
    if facts.live_data_ok is False and facts.network_ok is True and facts.auth_ok is True:
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
    ConnectorState.LIVE_OK: "Live",
    ConnectorState.MOCK_ONLY: "Sample/mock data only",
    ConnectorState.DISABLED: "Disabled",
    ConnectorState.UNKNOWN: "Unknown",
}


def _state_label(state: ConnectorState) -> str:
    return _STATE_LABELS.get(state, state.value)


def classify(spec: ConnectorSpec, *, run_probe: bool = True) -> ConnectorTruth:
    """Classify one connector into a truth state. Never raises."""
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
        state = _state_from_facts(facts)
        summary = f"{spec.display_name}: {_state_label(state)}"
        evidence = facts.evidence or spec.note

    blocks_go_live = spec.required_for_go_live and state != ConnectorState.LIVE_OK

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
    - READY_FOR_UAT : every go-live-required dependency is LIVE_OK (strict).
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
    not_live = [t.name for t in required if t.state != ConnectorState.LIVE_OK]
    if not not_live:
        return "READY_FOR_UAT", "all required dependencies passed a live probe"
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
