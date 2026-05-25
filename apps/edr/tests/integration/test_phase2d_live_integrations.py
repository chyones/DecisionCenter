"""Phase 2D Slice 3 — Live Integration Validation.

These tests attempt real connections against production integrations.
- Infrastructure probes run when the Docker stack is up (local dev / operator run).
- In CI (no services running) they skip gracefully on connection failure.
- Webhook probes validate explicit failure states (inactive workflows, missing auth).
- No fake success: every integration must surface an explicit error when broken.

Operator run (target environment with live credentials):
    pytest -v apps/edr/tests/integration/test_phase2d_live_integrations.py
"""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from apps.edr.config import settings
from apps.edr.connectors.email import search_email
from apps.edr.connectors.odoo import read_odoo
from apps.edr.connectors.owncloud import list_owncloud
from apps.edr.connectors.sharepoint import search_sharepoint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_if_missing(setting_name: str, value: str | None) -> None:
    if not value:
        pytest.skip(f"{setting_name} not configured — live probe unavailable")


def _webhook_url(webhook_path: str) -> str:
    base = settings.n8n_base_url.rstrip("/")
    path = webhook_path.lstrip("/")
    return f"{base}/{path}"


def _mocked_error_response(status_code: int, json_data: dict | None = None) -> AsyncMock:
    response = AsyncMock()
    response.json = Mock(return_value=json_data or {})
    response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            f"{status_code} Error",
            request=Mock(),
            response=Mock(status_code=status_code),
        )
    )
    return response


def _is_unreachable_error(exc: Exception) -> bool:
    """Return True for common "service not available" errors."""
    name = type(exc).__name__
    return name in {
        "CannotConnectNowError",
        "ConnectionRefusedError",
        "TimeoutError",
        "OSError",
        "ConnectError",
        "NetworkError",
        "gaierror",  # socket.getaddrinfo error
    }


# ---------------------------------------------------------------------------
# Infrastructure — real connectivity probes
# ---------------------------------------------------------------------------


@pytest.mark.live_probe
@pytest.mark.asyncio
async def test_postgres_live() -> None:
    """PostgreSQL: real TCP + auth + SELECT 1."""
    _skip_if_missing("POSTGRES_HOST", settings.postgres_host)
    import asyncpg

    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            timeout=5,
        )
        result = await conn.fetch("SELECT 1")
        assert result[0][0] == 1
        await conn.close()
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"PostgreSQL unreachable ({type(exc).__name__}) — skipping live probe")
        pytest.fail(f"PostgreSQL live probe failed: {type(exc).__name__}: {exc}")


@pytest.mark.live_probe
def test_redis_live() -> None:
    """Redis: TCP PING → PONG."""
    _skip_if_missing("REDIS_URL", settings.redis_url)
    from urllib.parse import urlparse

    parsed = urlparse(settings.redis_url)
    if parsed.scheme != "redis" or not parsed.hostname:
        pytest.skip("REDIS_URL is not a redis:// URL")
    host, port = parsed.hostname, parsed.port or 6379

    try:
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            pong = sock.recv(16)
            assert pong.startswith(b"+PONG"), f"Expected +PONG, got {pong!r}"
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"Redis unreachable ({type(exc).__name__}) — skipping live probe")
        pytest.fail(f"Redis live probe failed: {type(exc).__name__}: {exc}")


@pytest.mark.live_probe
def test_qdrant_live() -> None:
    """Qdrant: HTTP GET /collections."""
    _skip_if_missing("QDRANT_URL", settings.qdrant_url)
    try:
        resp = httpx.get(f"{settings.qdrant_url.rstrip('/')}/collections", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        # Qdrant wraps the payload under "result".
        result = data.get("result", {})
        assert "collections" in result
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"Qdrant unreachable ({type(exc).__name__}) — skipping live probe")
        pytest.fail(f"Qdrant live probe failed: {type(exc).__name__}: {exc}")


@pytest.mark.live_probe
def test_minio_live() -> None:
    """MinIO: HTTP GET /minio/health/ready."""
    _skip_if_missing("MINIO_ENDPOINT", settings.minio_endpoint)
    endpoint = settings.minio_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    try:
        resp = httpx.get(f"{endpoint.rstrip('/')}/minio/health/ready", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"MinIO unreachable ({type(exc).__name__}) — skipping live probe")
        pytest.fail(f"MinIO live probe failed: {type(exc).__name__}: {exc}")


@pytest.mark.live_probe
def test_langfuse_live() -> None:
    """Langfuse: HTTP GET /api/public/health (connectivity probe)."""
    _skip_if_missing("LANGFUSE_HOST", settings.langfuse_host)
    try:
        resp = httpx.get(
            f"{settings.langfuse_host.rstrip('/')}/api/public/health", timeout=10
        )
        # Reachability is the key probe. 401/403 means the service is live but
        # credentials are missing; that is an explicit state, not silent success.
        if resp.status_code >= 500:
            pytest.fail(f"Langfuse returned server error {resp.status_code}")
        # Any 2xx/3xx/4xx is treated as "reachable".
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"Langfuse unreachable ({type(exc).__name__}) — skipping live probe")
        pytest.fail(f"Langfuse live probe failed: {type(exc).__name__}: {exc}")


@pytest.mark.live_probe
def test_n8n_live() -> None:
    """n8n: HTTP GET /healthz."""
    _skip_if_missing("N8N_BASE_URL", settings.n8n_base_url)
    try:
        resp = httpx.get(f"{settings.n8n_base_url.rstrip('/')}/healthz", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"n8n unreachable ({type(exc).__name__}) — skipping live probe")
        pytest.fail(f"n8n live probe failed: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Workflow webhooks — explicit failure-state validation (no silent success)
# ---------------------------------------------------------------------------


@pytest.mark.live_probe
def test_sharepoint_webhook_explicit_failure() -> None:
    """SharePoint webhook: inactive or unauthenticated must NOT return 200."""
    _skip_if_missing("N8N_BASE_URL", settings.n8n_base_url)
    _skip_if_missing("SHAREPOINT_SEARCH_WEBHOOK", settings.sharepoint_search_webhook)
    url = _webhook_url(settings.sharepoint_search_webhook)
    try:
        resp = httpx.post(url, json={"query": "test"}, timeout=5)
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"n8n unreachable ({type(exc).__name__}) — skipping webhook probe")
        pytest.fail(f"SharePoint webhook probe failed: {type(exc).__name__}: {exc}")
    # An inactive workflow returns 404; missing auth returns 401/403.
    # Anything other than 200 is an explicit failure state.
    assert resp.status_code != 200, (
        f"SharePoint webhook returned 200 — possible silent success. "
        f"Status: {resp.status_code}"
    )


@pytest.mark.live_probe
def test_email_webhook_explicit_failure() -> None:
    """Microsoft Graph (Email) webhook: inactive or unauthenticated must NOT return 200."""
    _skip_if_missing("N8N_BASE_URL", settings.n8n_base_url)
    _skip_if_missing("EMAIL_SEARCH_WEBHOOK", settings.email_search_webhook)
    url = _webhook_url(settings.email_search_webhook)
    try:
        resp = httpx.post(url, json={"query": "test"}, timeout=5)
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"n8n unreachable ({type(exc).__name__}) — skipping webhook probe")
        pytest.fail(f"Email webhook probe failed: {type(exc).__name__}: {exc}")
    assert resp.status_code != 200, (
        f"Email webhook returned 200 — possible silent success. "
        f"Status: {resp.status_code}"
    )


@pytest.mark.live_probe
def test_owncloud_webhook_explicit_failure() -> None:
    """ownCloud webhook: inactive or unauthenticated must NOT return 200."""
    _skip_if_missing("N8N_BASE_URL", settings.n8n_base_url)
    _skip_if_missing("OWNCLOUD_LIST_WEBHOOK", settings.owncloud_list_webhook)
    url = _webhook_url(settings.owncloud_list_webhook)
    try:
        resp = httpx.post(url, json={"query": "test"}, timeout=5)
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"n8n unreachable ({type(exc).__name__}) — skipping webhook probe")
        pytest.fail(f"ownCloud webhook probe failed: {type(exc).__name__}: {exc}")
    assert resp.status_code != 200, (
        f"ownCloud webhook returned 200 — possible silent success. "
        f"Status: {resp.status_code}"
    )


@pytest.mark.live_probe
def test_odoo_webhook_explicit_failure() -> None:
    """Odoo webhook: inactive or unauthenticated must NOT return 200."""
    _skip_if_missing("N8N_BASE_URL", settings.n8n_base_url)
    _skip_if_missing("ODOO_READ_WEBHOOK", settings.odoo_read_webhook)
    url = _webhook_url(settings.odoo_read_webhook)
    try:
        resp = httpx.post(url, json={"query": "test"}, timeout=5)
    except Exception as exc:
        if _is_unreachable_error(exc):
            pytest.skip(f"n8n unreachable ({type(exc).__name__}) — skipping webhook probe")
        pytest.fail(f"Odoo webhook probe failed: {type(exc).__name__}: {exc}")
    assert resp.status_code != 200, (
        f"Odoo webhook returned 200 — possible silent success. "
        f"Status: {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Connector failure-mode tests — degraded vs silent success
# ---------------------------------------------------------------------------


def test_sharepoint_connector_fails_explicitly_on_404() -> None:
    """Connector must raise on n8n 404, not return empty evidence silently."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_error_response(404)

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(search_sharepoint({"query": "test", "project_code": "PRJ-001"}))


def test_email_connector_fails_explicitly_on_500() -> None:
    """Connector must raise on n8n 500, not return empty evidence silently."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_error_response(500)

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(
                search_email(
                    {
                        "user_mailbox": "a@b.com",
                        "allowed_mailboxes": ["a@b.com"],
                        "query": "test",
                        "project_code": "PRJ-001",
                    }
                )
            )


def test_owncloud_connector_fails_explicitly_on_403() -> None:
    """Connector must raise on n8n 403, not return empty evidence silently."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_error_response(403)

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(list_owncloud({"project_code": "PRJ-001"}))


def test_odoo_connector_fails_explicitly_on_502() -> None:
    """Connector must raise on n8n 502, not return empty evidence silently."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_error_response(502)

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(read_odoo({"project_code": "PRJ-001"}))


def test_connector_fails_on_malformed_200_response() -> None:
    """A 200 OK with non-dict body must fail during validation."""
    response = AsyncMock()
    response.json = Mock(return_value=["not", "a", "dict"])
    response.raise_for_status = Mock(return_value=None)

    mock_client = AsyncMock()
    mock_client.post.return_value = response

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ValueError, match="Expected dict payload"):
            asyncio.run(search_sharepoint({"query": "test"}))
