"""Phase 2B Slice 2 — Connectors & APIs (read + probe) service catalog.

This module is the single source of truth for the 10 external services the
admin Connectors screen surfaces. It is intentionally metadata-only:

- No credential values are read into Python objects (only key-presence).
- No credential substrings ever appear in any response or persisted row.
- Probes are read-only — they neither mutate state nor touch business data.

Per UI_CONTRACT_v1.md §3.2 and PHASE_2B_PLAN.md §E row 2 / §C.2.
"""
from __future__ import annotations

import json
import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict

from apps.edr.config import settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Latency above this is recorded as a ``connector.latency_spike`` event in
#: addition to the pass/fail event. Aligns with the UI contract's "degraded"
#: 2340ms ownCloud fixture (status pill turns orange).
LATENCY_SPIKE_THRESHOLD_MS: int = 2000

#: Per-leg socket / HTTP timeout, in seconds. Matches the existing
#: ``_tcp_connect`` / ``_http_ok`` budget used by ``/healthz``.
PROBE_TIMEOUT_SECONDS: float = 2.0

#: Repo-relative directory containing the n8n workflow JSON files. The probe
#: never *runs* these workflows; it reads the JSON to determine whether the
#: workflow is deployed (A-05).
_WORKFLOWS_DIR: Path = Path(__file__).resolve().parents[3] / "n8n"


# ---------------------------------------------------------------------------
# Pydantic response models — extra="forbid" so unintended fields are a hard
# error (defensive against C-6 / C-1 leakage via accidental serialization).
# ---------------------------------------------------------------------------


class EnvKeyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    present: bool


class ConnectorEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ts: str
    event_type: Literal[
        "connector.probe_success",
        "connector.error",
        "connector.latency_spike",
    ]
    latency_ms: int | None
    status_code: int | None
    detail: str


class ServiceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    category: Literal["infrastructure", "workflow"]
    auth_mechanism: Literal[
        "tcp", "http", "webhook_header_token", "oauth_bearer", "basic", "none"
    ]
    hostname: str | None
    last_probe_status: Literal["pass", "fail", "unknown"]
    last_probe_at: str | None
    last_latency_ms: int | None
    workflow_status: Literal["empty", "deployed"] | None


class ServiceDetail(ServiceSummary):
    model_config = ConfigDict(extra="forbid")

    description: str
    env_keys: list[EnvKeyStatus]
    workflow_node_count: int | None
    recent_events: list[ConnectorEventView]


class ProbeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    status: Literal["pass", "fail"]
    latency_ms: int
    status_code: int | None
    detail: str
    probed_at: str


# ---------------------------------------------------------------------------
# Service catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceDef:
    name: str
    display_name: str
    category: Literal["infrastructure", "workflow"]
    auth_mechanism: Literal[
        "tcp", "http", "webhook_header_token", "oauth_bearer", "basic", "none"
    ]
    description: str
    env_keys: tuple[str, ...]
    hostname_source: Callable[[], str | None]
    probe: str  # name of the module-level probe function (late-bound)
    workflow_file: str | None = None


# ---------------------------------------------------------------------------
# Hostname extractors — never return user-info
# ---------------------------------------------------------------------------


def _safe_hostname(value: str | None) -> str | None:
    """Return ``urlparse(value).hostname`` for URLs, or the bare host segment
    for ``host:port`` style values. Strips any embedded user-info even when
    callers slip credentials into the URL (defensive against C-6)."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if "://" in text:
        try:
            host = urlparse(text).hostname
        except Exception:
            return None
        return host or None
    # bare host[:port]
    host_part = text.split("@", 1)[-1]
    host_part = host_part.split("/", 1)[0]
    host_only = host_part.split(":", 1)[0]
    return host_only or None


def _postgres_host() -> str | None:
    return settings.postgres_host or None


def _redis_host() -> str | None:
    return _safe_hostname(settings.redis_url)


def _qdrant_host() -> str | None:
    return _safe_hostname(settings.qdrant_url)


def _minio_host() -> str | None:
    return _safe_hostname(settings.minio_endpoint)


def _langfuse_host() -> str | None:
    return _safe_hostname(settings.langfuse_host)


def _n8n_host() -> str | None:
    return _safe_hostname(settings.n8n_base_url)


def _odoo_host() -> str | None:
    return _safe_hostname(settings.odoo_url) if settings.odoo_url else None


# ---------------------------------------------------------------------------
# Probe primitives
# ---------------------------------------------------------------------------


def _tcp_probe(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=PROBE_TIMEOUT_SECONDS):
        return


def _http_probe(url: str) -> None:
    with urlopen(url, timeout=PROBE_TIMEOUT_SECONDS) as response:  # noqa: S310
        if response.status >= 400:
            raise ConnectionError(f"HTTP {response.status}")


def _probe_postgres() -> None:
    _tcp_probe(settings.postgres_host, settings.postgres_port)


def _probe_redis() -> None:
    parsed = urlparse(settings.redis_url)
    if parsed.scheme != "redis" or not parsed.hostname:
        raise ValueError("REDIS_URL must be a redis:// URL")
    port = parsed.port or 6379
    with socket.create_connection(
        (parsed.hostname, port), timeout=PROBE_TIMEOUT_SECONDS
    ) as sock:
        sock.sendall(b"*1\r\n$4\r\nPING\r\n")
        if not sock.recv(16).startswith(b"+PONG"):
            raise ConnectionError("Redis PING did not return PONG")


def _probe_qdrant() -> None:
    _http_probe(f"{settings.qdrant_url.rstrip('/')}/collections")


def _probe_minio() -> None:
    endpoint = settings.minio_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    _http_probe(f"{endpoint.rstrip('/')}/minio/health/ready")


def _probe_langfuse() -> None:
    _http_probe(f"{settings.langfuse_host.rstrip('/')}/api/public/health")


def _probe_n8n() -> None:
    _http_probe(f"{settings.n8n_base_url.rstrip('/')}/healthz")


def _probe_workflow_service() -> None:
    """Probe a workflow-backed service by checking n8n reachability only.

    Per Slice 2 design (user-confirmed): do NOT POST to the webhook. A no-op
    POST would (a) trigger real downstream HTTP against the vendor API,
    (b) require valid downstream credentials at probe time, (c) surface
    vendor-side error bodies that risk credential leakage. The n8n
    reachability check is sufficient for the [Test connection] semantics
    locked in UI_CONTRACT §3.2.
    """
    _probe_n8n()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


SERVICE_REGISTRY: dict[str, ServiceDef] = {
    "postgres": ServiceDef(
        name="postgres",
        display_name="PostgreSQL",
        category="infrastructure",
        auth_mechanism="basic",
        description="Primary audit/state database.",
        env_keys=(
            "POSTGRES_HOST",
            "POSTGRES_PORT",
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
        ),
        hostname_source=_postgres_host,
        probe="_probe_postgres",
    ),
    "redis": ServiceDef(
        name="redis",
        display_name="Redis",
        category="infrastructure",
        auth_mechanism="none",
        description="Embedding and rerank cache.",
        env_keys=("REDIS_URL",),
        hostname_source=_redis_host,
        probe="_probe_redis",
    ),
    "qdrant": ServiceDef(
        name="qdrant",
        display_name="Qdrant",
        category="infrastructure",
        auth_mechanism="none",
        description="Per-project vector store (collections prefixed edr_*).",
        env_keys=("QDRANT_URL",),
        hostname_source=_qdrant_host,
        probe="_probe_qdrant",
    ),
    "minio": ServiceDef(
        name="minio",
        display_name="MinIO",
        category="infrastructure",
        auth_mechanism="basic",
        description="Object storage for staging/final artifacts and uploads.",
        env_keys=(
            "MINIO_ENDPOINT",
            "MINIO_ACCESS_KEY",
            "MINIO_SECRET_KEY",
            "MINIO_BUCKET",
        ),
        hostname_source=_minio_host,
        probe="_probe_minio",
    ),
    "langfuse": ServiceDef(
        name="langfuse",
        display_name="Langfuse",
        category="infrastructure",
        auth_mechanism="oauth_bearer",
        description="LLM observability and tracing.",
        env_keys=(
            "LANGFUSE_HOST",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
        ),
        hostname_source=_langfuse_host,
        probe="_probe_langfuse",
    ),
    "n8n": ServiceDef(
        name="n8n",
        display_name="n8n",
        category="infrastructure",
        auth_mechanism="webhook_header_token",
        description="Connector orchestration layer.",
        env_keys=(
            "N8N_BASE_URL",
            "N8N_WEBHOOK_TOKEN",
            "N8N_TIMEOUT",
        ),
        hostname_source=_n8n_host,
        probe="_probe_n8n",
    ),
    "sharepoint": ServiceDef(
        name="sharepoint",
        display_name="SharePoint",
        category="workflow",
        auth_mechanism="webhook_header_token",
        description="SharePoint Graph Search via n8n workflow.",
        env_keys=(
            "SHAREPOINT_SEARCH_WEBHOOK",
            "N8N_BASE_URL",
            "N8N_WEBHOOK_TOKEN",
        ),
        hostname_source=_n8n_host,
        probe="_probe_workflow_service",
        workflow_file="sharepoint_search.json",
    ),
    "microsoft_graph": ServiceDef(
        name="microsoft_graph",
        display_name="Microsoft Graph",
        category="workflow",
        auth_mechanism="webhook_header_token",
        description="Microsoft Graph mailbox search via n8n workflow.",
        env_keys=(
            "EMAIL_SEARCH_WEBHOOK",
            "N8N_BASE_URL",
            "N8N_WEBHOOK_TOKEN",
        ),
        hostname_source=_n8n_host,
        probe="_probe_workflow_service",
        workflow_file="email_search.json",
    ),
    "owncloud": ServiceDef(
        name="owncloud",
        display_name="ownCloud",
        category="workflow",
        auth_mechanism="basic",
        description="ownCloud WebDAV listing via n8n workflow.",
        env_keys=(
            "OWNCLOUD_LIST_WEBHOOK",
            "OWNCLOUD_USERNAME",
            "OWNCLOUD_PASSWORD",
            "N8N_BASE_URL",
            "N8N_WEBHOOK_TOKEN",
        ),
        hostname_source=_n8n_host,
        probe="_probe_workflow_service",
        workflow_file="owncloud_list.json",
    ),
    "odoo": ServiceDef(
        name="odoo",
        display_name="Odoo",
        category="workflow",
        auth_mechanism="webhook_header_token",
        description="Odoo read-only JSON-RPC via n8n workflow.",
        env_keys=(
            "ODOO_READ_WEBHOOK",
            "ODOO_URL",
            "ODOO_DATABASE",
            "ODOO_USERNAME",
            "ODOO_API_KEY",
            "N8N_BASE_URL",
            "N8N_WEBHOOK_TOKEN",
        ),
        hostname_source=_n8n_host,
        probe="_probe_workflow_service",
        workflow_file="odoo_read.json",
    ),
}


# ---------------------------------------------------------------------------
# Env-key presence (C-6: value never read, only presence boolean)
# ---------------------------------------------------------------------------


_ENV_KEY_TO_SETTING: dict[str, str] = {
    "POSTGRES_HOST": "postgres_host",
    "POSTGRES_PORT": "postgres_port",
    "POSTGRES_DB": "postgres_db",
    "POSTGRES_USER": "postgres_user",
    "POSTGRES_PASSWORD": "postgres_password",
    "REDIS_URL": "redis_url",
    "QDRANT_URL": "qdrant_url",
    "MINIO_ENDPOINT": "minio_endpoint",
    "MINIO_ACCESS_KEY": "minio_access_key",
    "MINIO_SECRET_KEY": "minio_secret_key",
    "MINIO_BUCKET": "minio_bucket",
    "LANGFUSE_HOST": "langfuse_host",
    "LANGFUSE_PUBLIC_KEY": "langfuse_public_key",
    "LANGFUSE_SECRET_KEY": "langfuse_secret_key",
    "N8N_BASE_URL": "n8n_base_url",
    "N8N_WEBHOOK_TOKEN": "n8n_webhook_token",
    "N8N_TIMEOUT": "n8n_timeout",
    "SHAREPOINT_SEARCH_WEBHOOK": "sharepoint_search_webhook",
    "EMAIL_SEARCH_WEBHOOK": "email_search_webhook",
    "OWNCLOUD_LIST_WEBHOOK": "owncloud_list_webhook",
    "OWNCLOUD_USERNAME": "owncloud_username",
    "OWNCLOUD_PASSWORD": "owncloud_password",
    "ODOO_READ_WEBHOOK": "odoo_read_webhook",
    "ODOO_URL": "odoo_url",
    "ODOO_DATABASE": "odoo_database",
    "ODOO_USERNAME": "odoo_username",
    "ODOO_API_KEY": "odoo_api_key",
}


def _is_present(env_key: str) -> bool:
    """Return ``True`` iff the setting backing ``env_key`` is non-None and
    non-empty after coercion to string. Never returns the value itself."""
    attr = _ENV_KEY_TO_SETTING.get(env_key)
    if attr is None:
        return False
    value = getattr(settings, attr, None)
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip()
    return bool(text)


def env_key_statuses(service: ServiceDef) -> list[EnvKeyStatus]:
    return [
        EnvKeyStatus(name=key, present=_is_present(key)) for key in service.env_keys
    ]


# ---------------------------------------------------------------------------
# Workflow status (A-05)
# ---------------------------------------------------------------------------


def workflow_node_count(service: ServiceDef) -> int | None:
    """Return the node count of the workflow JSON file backing ``service``.

    ``None`` for infrastructure services and when the file cannot be read.
    """
    if service.workflow_file is None:
        return None
    path = _WORKFLOWS_DIR / service.workflow_file
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    nodes = data.get("nodes") if isinstance(data, dict) else None
    if not isinstance(nodes, list):
        return 0
    return len(nodes)


def workflow_status_for(
    service: ServiceDef,
) -> Literal["empty", "deployed"] | None:
    if service.category != "workflow":
        return None
    count = workflow_node_count(service)
    if count is None:
        return "empty"
    return "deployed" if count > 0 else "empty"


# ---------------------------------------------------------------------------
# Detail sanitisation — last line of defence for C-6
# ---------------------------------------------------------------------------


_LONG_OPAQUE = re.compile(r"[A-Za-z0-9_+/=]{20,}")
_KV_LEAK = re.compile(
    r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S+"
)


def _sanitize_detail(text: str | None, hostname: str | None = None) -> str:
    """Return a short, C-6-safe detail string.

    Drops:
    - Long opaque tokens (base64-ish / API keys; ``[A-Za-z0-9_+/=]{20,}``).
    - Embedded ``key=value`` / ``key: value`` pairs naming credentials.
    - URL user-info (``user:pass@host`` → ``host``).

    Truncated to 200 chars. Suitable for both the response body and the
    persisted ``connector_events.detail`` column.
    """
    if not text:
        return ""
    cleaned = text.strip()
    if hostname:
        cleaned = cleaned.replace(f"{hostname}", hostname)  # idempotent
    # Strip user-info from any URL substring.
    cleaned = re.sub(r"://[^/\s@]+@", "://", cleaned)
    cleaned = _KV_LEAK.sub(r"\1=<redacted>", cleaned)
    cleaned = _LONG_OPAQUE.sub("<redacted>", cleaned)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    return cleaned


def _detail_for_exception(exc: BaseException, hostname: str | None) -> str:
    """Build ``"{ExceptionClassName}@{hostname}"`` — never ``str(exc)``.

    Some drivers (asyncpg, MinIO, urllib) embed the connection string —
    including the password — in their exception messages. Reducing the
    detail to class name + hostname is the only safe option.
    """
    cls = type(exc).__name__
    suffix = f"@{hostname}" if hostname else ""
    return _sanitize_detail(f"{cls}{suffix}", hostname=hostname)


# ---------------------------------------------------------------------------
# Probe entrypoint
# ---------------------------------------------------------------------------


@dataclass
class _ProbeOutcome:
    status: Literal["pass", "fail"]
    latency_ms: int
    status_code: int | None
    detail: str


def run_probe(service: ServiceDef) -> _ProbeOutcome:
    """Execute the service's registered probe and return a structured outcome.

    Never re-raises. Network / value errors collapse to ``status="fail"`` with
    a sanitised detail; success is ``status="pass"``. Latency is wall-clock
    milliseconds measured around the probe call.
    """
    host = service.hostname_source()
    start = _now_monotonic()
    status: Literal["pass", "fail"] = "pass"
    status_code: int | None = None
    detail: str = "ok"
    try:
        globals()[service.probe]()
        status_code = 200
    except (ConnectionError, OSError, URLError, ValueError, TimeoutError) as exc:
        status = "fail"
        status_code = None
        # urllib HTTPError carries .code; capture without ever including body
        code = getattr(exc, "code", None)
        if isinstance(code, int):
            status_code = code
        detail = _detail_for_exception(exc, host)
    except Exception as exc:  # defensive: never propagate to FastAPI as 500
        status = "fail"
        detail = _detail_for_exception(exc, host)
    elapsed_ms = int((_now_monotonic() - start) * 1000)
    return _ProbeOutcome(
        status=status,
        latency_ms=elapsed_ms,
        status_code=status_code,
        detail=detail,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_monotonic() -> float:
    """Indirection over ``time.monotonic`` so tests can fake elapsed time
    without monkeypatching the entire ``time`` module (which leaks into the
    event loop / pytest internals)."""
    return time.monotonic()
