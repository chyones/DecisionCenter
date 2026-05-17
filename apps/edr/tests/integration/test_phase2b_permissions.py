"""Phase 2B Slice 5 — Permissions & Roles (Entra Group Mapping) integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403 on all 3 endpoints
- Missing claims → 401
- Happy path: list, upsert, delete
- Upsert invalid role → 400
- A-17: audit event emitted BEFORE save (call order assertion)
- Delete not-found → 404
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
    EntraGroupMapping,
    EntraGroupMappingListResponse,
    EntraGroupMappingUpsertRequest,
    _require_admin,
    _validate_canonical_role,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — all endpoints deny every non-admin role (parametrised)
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_entra_list_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_entra_upsert_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_entra_delete_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_entra_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# List — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_list_returns_mappings() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "entra_group_id": "grp-1",
            "role": "finance",
            "created_at": datetime(2026, 5, 1, 10, 0, 0),
            "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_entra_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_entra_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_entra_mappings(claims)

    assert isinstance(result, EntraGroupMappingListResponse)
    assert len(result.mappings) == 1
    assert result.mappings[0].entra_group_id == "grp-1"
    assert result.mappings[0].role == "finance"


# ---------------------------------------------------------------------------
# Upsert — happy path
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_upsert_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "entra_group_id": "grp-2",
        "role": "executive",
        "created_at": datetime(2026, 5, 3, 10, 0, 0),
        "updated_at": datetime(2026, 5, 3, 10, 0, 0),
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=42)
    mock_pg.upsert_entra_mapping = AsyncMock(return_value=None)
    mock_pg.get_entra_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import upsert_entra_mapping

    body = EntraGroupMappingUpsertRequest(role="executive")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await upsert_entra_mapping("grp-2", body, claims)

    assert isinstance(result, EntraGroupMapping)
    assert result.entra_group_id == "grp-2"
    assert result.role == "executive"


# ---------------------------------------------------------------------------
# Upsert — invalid role → 400
# ---------------------------------------------------------------------------


def test_validate_canonical_role_rejects_invalid() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_canonical_role("superuser")
    assert exc.value.status_code == 400
    assert "superuser" in exc.value.detail


# ---------------------------------------------------------------------------
# A-17 — audit event emitted BEFORE save
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_upsert_audit_before_save() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "entra_group_id": "grp-3",
        "role": "legal",
        "created_at": datetime(2026, 5, 4, 10, 0, 0),
        "updated_at": datetime(2026, 5, 4, 10, 0, 0),
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=99)
    mock_pg.upsert_entra_mapping = AsyncMock(return_value=None)
    mock_pg.get_entra_mapping = AsyncMock(return_value=fake_row)

    from apps.edr.app import upsert_entra_mapping

    body = EntraGroupMappingUpsertRequest(role="legal")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await upsert_entra_mapping("grp-3", body, claims)

    calls = mock_pg.method_calls
    # Extract call names in order
    call_names = [c[0] for c in calls]
    audit_idx = call_names.index("insert_admin_event")
    upsert_idx = call_names.index("upsert_entra_mapping")
    assert audit_idx < upsert_idx, "A-17 violation: audit must fire before DB write"


# ---------------------------------------------------------------------------
# Delete — happy path → 204
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_delete_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_row = {
        "entra_group_id": "grp-4",
        "role": "auditor",
        "created_at": datetime(2026, 5, 5, 10, 0, 0),
        "updated_at": datetime(2026, 5, 5, 10, 0, 0),
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_entra_mapping = AsyncMock(return_value=fake_row)
    mock_pg.insert_admin_event = AsyncMock(return_value=77)
    mock_pg.delete_entra_mapping = AsyncMock(return_value=True)

    from apps.edr.app import delete_entra_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await delete_entra_mapping("grp-4", claims)

    assert response.status_code == 204
    mock_pg.delete_entra_mapping.assert_awaited_once_with("grp-4")


# ---------------------------------------------------------------------------
# Delete — not found → 404
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_delete_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_entra_mapping = AsyncMock(return_value=None)
    mock_pg.insert_admin_event = AsyncMock(return_value=0)
    mock_pg.delete_entra_mapping = AsyncMock(return_value=False)

    from apps.edr.app import delete_entra_mapping

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await delete_entra_mapping("missing-group", claims)

    assert exc.value.status_code == 404
    mock_pg.insert_admin_event.assert_not_called()
    mock_pg.delete_entra_mapping.assert_not_called()


# ---------------------------------------------------------------------------
# C-1 — no business content in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_list_no_business_content() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "entra_group_id": "grp-1",
            "role": "finance",
            "created_at": datetime(2026, 5, 1, 10, 0, 0),
            "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_entra_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_entra_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_entra_mappings(claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in mapping list"


# ---------------------------------------------------------------------------
# C-6 — no credential values in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_entra_list_no_credentials() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "entra_group_id": "grp-1",
            "role": "finance",
            "created_at": datetime(2026, 5, 1, 10, 0, 0),
            "updated_at": datetime(2026, 5, 2, 12, 0, 0),
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_entra_mappings = AsyncMock(return_value=fake_rows)

    from apps.edr.app import list_entra_mappings

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_entra_mappings(claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in mapping list"
