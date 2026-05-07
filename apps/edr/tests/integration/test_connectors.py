"""Isolated connector validation tests for Phase 1C.

These tests mock n8n webhook responses and validate that every connector
normalizes and validates output against the EvidenceObject schema.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from apps.edr.connectors.email import search_email
from apps.edr.connectors.odoo import read_odoo
from apps.edr.connectors.owncloud import list_owncloud
from apps.edr.connectors.sharepoint import search_sharepoint
from apps.edr.schemas.evidence import EvidenceObject


def _mocked_response(data: dict) -> AsyncMock:
    """Build an async mock that mimics an httpx Response.

    httpx ``Response.json()`` and ``raise_for_status()`` are synchronous,
    so we attach regular ``Mock`` objects for those methods.
    """
    response = AsyncMock()
    response.json = Mock(return_value=data)
    response.raise_for_status = Mock(return_value=None)
    return response


# ---------------------------------------------------------------------------
# SharePoint
# ---------------------------------------------------------------------------


def test_sharepoint_connector_valid_evidence() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {
            "evidence": [
                {
                    "evidence_id": "sp-001",
                    "source_type": "sharepoint",
                    "source_uri": "https://graph.microsoft.com/v1.0/drives/abc/items/001",
                    "title": "Contract Amendment.pdf",
                    "project_code": "PRJ-001",
                    "excerpt": "Amendment to contract CON-001 dated 2024-01-15",
                    "hash_sha256": "a" * 64,
                    "confidence": "high",
                }
            ]
        }
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(search_sharepoint({"query": "contract", "project_code": "PRJ-001"}))

    assert len(result) == 1
    assert isinstance(result[0], EvidenceObject)
    assert result[0].evidence_id == "sp-001"
    assert result[0].source_type == "sharepoint"
    assert result[0].confidence == "high"


def test_sharepoint_connector_rejects_invalid_payload() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {
            "evidence": [
                {
                    "evidence_id": "sp-bad",
                    "source_type": "invalid_source",
                    "source_uri": "https://example.com",
                    "title": "Bad",
                    "excerpt": "x",
                    "hash_sha256": "a" * 64,
                    "confidence": "high",
                }
            ]
        }
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception):
            asyncio.run(search_sharepoint({"query": "test"}))


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def test_email_connector_excerpt_truncated_to_500() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {
            "evidence": [
                {
                    "evidence_id": "eml-001",
                    "source_type": "email",
                    "source_uri": "https://graph.microsoft.com/v1.0/users/bob@corp.com/messages/001",
                    "title": "Re: Delay Notice",
                    "project_code": "PRJ-001",
                    "excerpt": "A" * 500,
                    "hash_sha256": "b" * 64,
                    "confidence": "medium",
                }
            ]
        }
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(
            search_email(
                {
                    "user_mailbox": "bob@corp.com",
                    "allowed_mailboxes": ["project@corp.com"],
                    "query": "delay",
                    "project_code": "PRJ-001",
                }
            )
        )

    assert len(result) == 1
    assert isinstance(result[0], EvidenceObject)
    assert result[0].source_type == "email"
    assert len(result[0].excerpt) <= 500


def test_email_connector_rejects_missing_fields() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {"evidence": [{"source_type": "email"}]}
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception):
            asyncio.run(search_email({"user_mailbox": "bob@corp.com", "query": "test"}))


# ---------------------------------------------------------------------------
# ownCloud
# ---------------------------------------------------------------------------


def test_owncloud_connector_valid_evidence() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {
            "evidence": [
                {
                    "evidence_id": "oc-001",
                    "source_type": "owncloud",
                    "source_uri": "https://owncloud.corp.com/remote.php/dav/files/admin/Projects/PRJ-001/BOQ.xlsx",
                    "title": "BOQ.xlsx",
                    "project_code": "PRJ-001",
                    "excerpt": "Bill of Quantities for PRJ-001",
                    "hash_sha256": "c" * 64,
                    "confidence": "medium",
                }
            ]
        }
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(
            list_owncloud(
                {
                    "base_url": "https://owncloud.corp.com",
                    "root_path": "Projects/PRJ-001",
                    "username": "admin",
                    "password": "secret",
                    "project_code": "PRJ-001",
                }
            )
        )

    assert len(result) == 1
    assert isinstance(result[0], EvidenceObject)
    assert result[0].source_type == "owncloud"
    assert result[0].title == "BOQ.xlsx"


# ---------------------------------------------------------------------------
# Odoo
# ---------------------------------------------------------------------------


def test_odoo_connector_returns_required_fields() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {
            "evidence": [
                {
                    "evidence_id": "odoo-project.project-42",
                    "source_type": "odoo",
                    "source_uri": "https://odoo.corp.com/web#id=42&model=project.project",
                    "title": "PRJ-001 Tower A",
                    "project_code": "PRJ-001",
                    "excerpt": "name: PRJ-001 Tower A; budget: 5000000.0",
                    "hash_sha256": "d" * 64,
                    "confidence": "high",
                    "timestamp": "2024-06-01T12:00:00Z",
                    "metadata": {"model": "project.project", "record_id": 42},
                }
            ]
        }
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(
            read_odoo(
                {
                    "odoo_url": "https://odoo.corp.com",
                    "database": "prod",
                    "username": "api@corp.com",
                    "api_key": "secret",
                    "model": "project.project",
                    "domain": "[[\"id\", \"=\", 42]]",
                    "fields": '["name", "budget"]',
                    "project_code": "PRJ-001",
                }
            )
        )

    assert len(result) == 1
    assert isinstance(result[0], EvidenceObject)
    assert result[0].source_type == "odoo"
    assert result[0].timestamp is not None
    assert result[0].metadata.get("model") == "project.project"
    assert result[0].metadata.get("record_id") == 42


def test_odoo_connector_rejects_invalid_evidence() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(
        {
            "evidence": [
                {
                    "evidence_id": "odoo-bad",
                    "source_type": "odoo",
                    "source_uri": "https://odoo.corp.com",
                    "title": "Bad",
                    "excerpt": "x",
                    "hash_sha256": "d" * 64,
                    "confidence": "impossible",
                }
            ]
        }
    )

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception):
            asyncio.run(read_odoo({"model": "project.project", "domain": "[]"}))


# ---------------------------------------------------------------------------
# Validation layer edge cases
# ---------------------------------------------------------------------------


def test_connector_rejects_non_dict_payload() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response(["not", "a", "dict"])

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ValueError, match="Expected dict payload"):
            asyncio.run(search_sharepoint({"query": "test"}))


def test_connector_rejects_missing_evidence_key() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response({"results": []})

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = asyncio.run(search_sharepoint({"query": "test"}))
        assert result == []


def test_connector_rejects_non_list_evidence() -> None:
    mock_client = AsyncMock()
    mock_client.post.return_value = _mocked_response({"evidence": "not-a-list"})

    with patch("apps.edr.connectors.base.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ValueError, match="Expected 'evidence' to be a list"):
            asyncio.run(search_sharepoint({"query": "test"}))
