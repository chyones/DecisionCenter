"""Unit tests for Graph token acquisition (client credentials flow).

These tests never make real network calls.  They verify:
- Token is fetched and cached on first call.
- Cached token is reused within the validity window.
- Cache is bypassed when the token is near expiry.
- Empty string is returned when Entra is not configured.
- HTTP errors propagate as exceptions.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import apps.edr.connectors.graph_token as _mod
from apps.edr.connectors.graph_token import _reset_cache, get_graph_token


def _mock_token_response(access_token: str = "test-graph-token", expires_in: int = 3600) -> AsyncMock:
    resp = AsyncMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value={"access_token": access_token, "expires_in": expires_in})
    return resp


def _patch_settings(*, tenant="tenant-id", client_id="client-id", secret="secret"):
    return patch.multiple(
        "apps.edr.connectors.graph_token.settings",
        entra_tenant_id=tenant,
        entra_client_id=client_id,
        entra_client_secret=secret,
    )


def setup_function() -> None:
    _reset_cache()


# ---------------------------------------------------------------------------
# Basic acquisition
# ---------------------------------------------------------------------------


def test_get_graph_token_acquires_and_returns_token() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_token_response("tok-abc")

    with _patch_settings(), patch("apps.edr.connectors.graph_token.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(get_graph_token())

    assert result == "tok-abc"
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[1]["data"]["grant_type"] == "client_credentials"
    assert call_kwargs[1]["data"]["scope"] == "https://graph.microsoft.com/.default"


def test_get_graph_token_cached_on_second_call() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_token_response("tok-cached")

    with _patch_settings(), patch("apps.edr.connectors.graph_token.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        first = asyncio.run(get_graph_token())
        second = asyncio.run(get_graph_token())

    assert first == second == "tok-cached"
    assert mock_client.post.call_count == 1  # only one HTTP call


def test_get_graph_token_re_fetches_when_expired() -> None:
    _reset_cache()
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        _mock_token_response("tok-first", expires_in=1),  # will expire almost immediately
        _mock_token_response("tok-second"),
    ]

    with _patch_settings(), patch("apps.edr.connectors.graph_token.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(get_graph_token())

        # Force the cached token to appear expired
        _mod._cache.expires_at = time.monotonic() - 1

        second = asyncio.run(get_graph_token())

    assert second == "tok-second"
    assert mock_client.post.call_count == 2


# ---------------------------------------------------------------------------
# Not-configured guard
# ---------------------------------------------------------------------------


def test_get_graph_token_returns_empty_when_not_configured() -> None:
    with patch.multiple(
        "apps.edr.connectors.graph_token.settings",
        entra_tenant_id=None,
        entra_client_id="some-id",
        entra_client_secret="some-secret",
    ):
        result = asyncio.run(get_graph_token())

    assert result == ""


def test_get_graph_token_returns_empty_when_secret_missing() -> None:
    with patch.multiple(
        "apps.edr.connectors.graph_token.settings",
        entra_tenant_id="tenant",
        entra_client_id="client",
        entra_client_secret=None,
    ):
        result = asyncio.run(get_graph_token())

    assert result == ""


# ---------------------------------------------------------------------------
# HTTP error propagation
# ---------------------------------------------------------------------------


def test_get_graph_token_raises_on_http_error() -> None:
    import httpx

    mock_client = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "401", request=MagicMock(), response=MagicMock()
    ))
    mock_client.post.return_value = mock_resp

    with _patch_settings(), patch("apps.edr.connectors.graph_token.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(get_graph_token())


# ---------------------------------------------------------------------------
# Token injected into SharePoint / email connectors
# ---------------------------------------------------------------------------


def test_sharepoint_connector_injects_graph_token() -> None:
    """search_sharepoint must merge the acquired Graph token into the n8n payload."""
    from unittest.mock import Mock

    from apps.edr.connectors.sharepoint import search_sharepoint

    fake_evidence = {
        "evidence": [
            {
                "evidence_id": "sp-t1",
                "source_type": "sharepoint",
                "source_uri": "https://graph.microsoft.com/v1.0/drives/x/items/y",
                "title": "Test.pdf",
                "project_code": "PRJ-001",
                "excerpt": "test content",
                "hash_sha256": "a" * 64,
                "confidence": "medium",
            }
        ]
    }

    n8n_resp = AsyncMock()
    n8n_resp.json = Mock(return_value=fake_evidence)
    n8n_resp.raise_for_status = Mock(return_value=None)
    mock_n8n = AsyncMock()
    mock_n8n.post.return_value = n8n_resp

    with (
        patch("apps.edr.connectors.sharepoint.get_graph_token", new=AsyncMock(return_value="injected-token")),
        patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_n8n)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(search_sharepoint({"query": "test", "project_code": "PRJ-001"}))

    sent_payload = mock_n8n.post.call_args[1]["json"]
    assert sent_payload["access_token"] == "injected-token"
    assert len(result) == 1


def test_email_connector_injects_graph_token() -> None:
    """search_email must merge the acquired Graph token into the n8n payload."""
    from unittest.mock import Mock

    from apps.edr.connectors.email import search_email

    fake_evidence = {
        "evidence": [
            {
                "evidence_id": "eml-t1",
                "source_type": "email",
                "source_uri": "https://graph.microsoft.com/v1.0/users/u/messages/m",
                "title": "Re: Project kickoff",
                "project_code": "PRJ-001",
                "excerpt": "email excerpt",
                "hash_sha256": "b" * 64,
                "confidence": "medium",
            }
        ]
    }

    n8n_resp = AsyncMock()
    n8n_resp.json = Mock(return_value=fake_evidence)
    n8n_resp.raise_for_status = Mock(return_value=None)
    mock_n8n = AsyncMock()
    mock_n8n.post.return_value = n8n_resp

    with (
        patch("apps.edr.connectors.email.get_graph_token", new=AsyncMock(return_value="injected-email-token")),
        patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_n8n)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(search_email({"query": "test", "user_mailbox": "u@e.com"}))

    sent_payload = mock_n8n.post.call_args[1]["json"]
    assert sent_payload["access_token"] == "injected-email-token"
    assert len(result) == 1
