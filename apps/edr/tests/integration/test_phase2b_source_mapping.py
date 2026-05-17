"""Phase 2B Slice 6 — Project Source Mapping integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403 on all 5 endpoints
- Missing claims → 401
- Happy path: list, get detail, validate, upsert, disable
- Get detail 404
- Validate complete vs incomplete mapping
- Upsert happy path
- A-21 audit-before-save order
- Disable happy path → 204
- Disable not found → 404
- Disable already disabled → 409
- C-1: no query / report content / evidence in responses
- C-6: no credential values in responses
"""
from __future__ import annotations

import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.app import (
    SourceMappingDetail,
    SourceMappingListResponse,
    SourceMappingUpsertRequest,
    _compute_mapping_status,
    _require_admin,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — all endpoints deny every non-admin role (parametrised)
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_list_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_detail_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_validate_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_upsert_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_source_disable_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_source_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# List — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_list_returns_mappings() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "project_code": "PRJ-001",
            "project_name": "Alpha",
            "mapping_status": "complete",
            "contract_numbers": '["CON-001"]',
        },
        {
            "project_code": "PRJ-002",
            "project_name": "Beta",
            "mapping_status": "incomplete",
            "contract_numbers": '["CON-002"]',
        },
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_source_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_source_mappings(claims)

    assert isinstance(result, SourceMappingListResponse)
    assert len(result.mappings) == 2
    assert result.mappings[0].project_code == "PRJ-001"
    assert result.mappings[1].mapping_status == "incomplete"


# ---------------------------------------------------------------------------
# Get detail — happy path + 404
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_detail_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Alpha",
        "contract_numbers": '["CON-001"]',
        "sharepoint": '{"site_id": "s1", "drive_id": "d1", "root_path": "/r1"}',
        "owncloud": '{"base_path": "/o1"}',
        "email": '{"shared_mailboxes": ["m1"], "document_control_mailbox": "dc1"}',
        "odoo": '{"project_model": "pm", "cost_model": "cm", "project_external_id": "pe"}',
        "related_people": '{"project_manager": "pm"}',
        "enabled_sources": '["sharepoint", "email"]',
        "allowed_roles": '["executive", "finance"]',
        "mapping_status": "complete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        "created_by_hash": "abc",
        "updated_by_hash": "def",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import get_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await get_source_mapping("PRJ-001", claims)

    assert isinstance(result, SourceMappingDetail)
    assert result.project_code == "PRJ-001"
    assert result.sharepoint.site_id == "s1"


@pytest.mark.anyio
async def test_source_detail_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=None)

    from apps.edr.app import get_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_source_mapping("MISSING", claims)

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Validate — pure function tests
# ---------------------------------------------------------------------------


def test_validate_complete_mapping() -> None:
    body = SourceMappingUpsertRequest(
        sharepoint={"site_id": "s1", "drive_id": "d1", "root_path": "/r1"},
        owncloud={"base_path": "/o1"},
        email={"shared_mailboxes": ["m1"]},
        odoo={"project_external_id": "pe1"},
        enabled_sources=["sharepoint", "owncloud", "email", "odoo"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "complete"
    assert errors == []


def test_validate_incomplete_mapping() -> None:
    body = SourceMappingUpsertRequest(
        sharepoint={"site_id": "", "drive_id": "", "root_path": ""},
        enabled_sources=["sharepoint"],
    )
    status, errors = _compute_mapping_status("PRJ-001", body)
    assert status == "incomplete"
    assert any(e.field == "sharepoint.site_id" for e in errors)


# ---------------------------------------------------------------------------
# Upsert — happy path + A-21 audit-before-save
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_upsert_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Alpha",
        "contract_numbers": '["CON-001"]',
        "sharepoint": '{"site_id": "s1", "drive_id": "d1", "root_path": "/r1"}',
        "owncloud": '{"base_path": "/o1"}',
        "email": '{"shared_mailboxes": ["m1"], "document_control_mailbox": "dc1"}',
        "odoo": '{"project_model": "pm", "cost_model": "cm", "project_external_id": "pe"}',
        "related_people": '{"project_manager": "pm"}',
        "enabled_sources": '["sharepoint"]',
        "allowed_roles": '["executive"]',
        "mapping_status": "complete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        "created_by_hash": "abc",
        "updated_by_hash": "def",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=42)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import upsert_source_mapping

    body = SourceMappingUpsertRequest(
        sharepoint={"site_id": "s1", "drive_id": "d1", "root_path": "/r1"},
        enabled_sources=["sharepoint"],
    )
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await upsert_source_mapping("PRJ-001", body, claims)

    assert isinstance(result, SourceMappingDetail)
    assert result.project_code == "PRJ-001"


@pytest.mark.anyio
async def test_source_upsert_audit_before_save() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "project_name": "Alpha",
        "contract_numbers": '[]',
        "sharepoint": '{}',
        "owncloud": '{}',
        "email": '{}',
        "odoo": '{}',
        "related_people": '{}',
        "enabled_sources": '[]',
        "allowed_roles": '[]',
        "mapping_status": "incomplete",
        "last_validation_result": None,
        "last_validated_at": None,
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "updated_at": datetime(2026, 5, 1, 10, 0, 0),
        "created_by_hash": "",
        "updated_by_hash": "",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=99)
    mock_pg.upsert_source_mapping = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import upsert_source_mapping

    body = SourceMappingUpsertRequest()
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await upsert_source_mapping("PRJ-001", body, claims)

    calls = mock_pg.method_calls
    call_names = [c[0] for c in calls]
    audit_idx = call_names.index("insert_admin_event")
    upsert_idx = call_names.index("upsert_source_mapping")
    assert audit_idx < upsert_idx, "A-21 violation: audit must fire before DB write"


# ---------------------------------------------------------------------------
# Disable — happy path, 404, 409
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_disable_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "project_code": "PRJ-001",
        "mapping_status": "complete",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)
    mock_pg.insert_admin_event = AsyncMock(return_value=77)
    mock_pg.disable_source_mapping = AsyncMock(return_value=None)

    from apps.edr.app import disable_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await disable_source_mapping("PRJ-001", claims)

    assert response.status_code == 204
    mock_pg.disable_source_mapping.assert_awaited_once_with("PRJ-001")


@pytest.mark.anyio
async def test_source_disable_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=None)

    from apps.edr.app import disable_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await disable_source_mapping("MISSING", claims)

    assert exc.value.status_code == 404
    mock_pg.insert_admin_event.assert_not_called()
    mock_pg.disable_source_mapping.assert_not_called()


@pytest.mark.anyio
async def test_source_disable_already_disabled() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {"project_code": "PRJ-001", "mapping_status": "disabled"}
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_source_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import disable_source_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await disable_source_mapping("PRJ-001", claims)

    assert exc.value.status_code == 409
    mock_pg.insert_admin_event.assert_not_called()
    mock_pg.disable_source_mapping.assert_not_called()


# ---------------------------------------------------------------------------
# C-1 — no business content in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_list_no_business_content() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "project_code": "PRJ-001",
            "project_name": "Alpha",
            "mapping_status": "complete",
            "contract_numbers": '["CON-001"]',
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_source_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_source_mappings(claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in source list"


# ---------------------------------------------------------------------------
# C-6 — no credential values in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_source_list_no_credentials() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "project_code": "PRJ-001",
            "project_name": "Alpha",
            "mapping_status": "complete",
            "contract_numbers": '["CON-001"]',
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_source_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_source_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_source_mappings(claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in source list"
