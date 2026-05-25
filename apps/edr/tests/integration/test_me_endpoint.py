"""Phase 2D Slice 2 — production auth backend tests.

Covers:
- ``GET /me`` — identity metadata (hashed user id + canonical role) for every
  authenticated role, including admin (metadata-only, no business data).
- ``_extract_claims`` — production rejects dev bypass headers
  (``x-user-role`` / ``x-user-id``) while local/CI bypass is unchanged.

Mirrors the Phase 2A/2B pattern: endpoint functions are called directly with a
mock claims object, and ``apps.edr.app.settings`` fields are patched in place.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.app import MeResponse, _extract_claims, get_me
from apps.edr.persistence.hash import hash_user_id
from apps.edr.rbac.roles import Role


def _claims(user_id: str = "user-42", role: str | None = Role.EXECUTIVE.value) -> MagicMock:
    return MagicMock(user_id=user_id, role=role)


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [r.value for r in Role])
@pytest.mark.asyncio
async def test_me_returns_role_and_hash_for_every_canonical_role(role: str) -> None:
    resp = await get_me(claims=_claims(user_id="user-42", role=role))
    assert isinstance(resp, MeResponse)
    assert resp.role == role
    assert resp.user_id_hash == hash_user_id("user-42")


@pytest.mark.asyncio
async def test_me_allows_admin_and_exposes_only_metadata() -> None:
    resp = await get_me(claims=_claims(user_id="admin-1", role=Role.ADMIN.value))
    assert resp.role == "admin"
    # Structurally metadata-only: role + hashed id, never any business field.
    assert set(resp.model_dump().keys()) == {"user_id_hash", "role"}
    assert resp.user_id_hash == hash_user_id("admin-1")
    assert resp.user_id_hash != "admin-1"


@pytest.mark.asyncio
async def test_me_raises_401_when_unauthenticated() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_me(claims=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_me_raises_403_for_invalid_role() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_me(claims=_claims(role="not-a-real-role"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_me_raises_403_for_missing_role() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_me(claims=_claims(role=None))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_me_empty_hash_when_no_user_id() -> None:
    resp = await get_me(claims=_claims(user_id="", role=Role.EXECUTIVE.value))
    assert resp.user_id_hash == ""
    assert resp.role == "executive"


# ---------------------------------------------------------------------------
# _extract_claims — production rejects dev bypass headers
# ---------------------------------------------------------------------------


def test_extract_claims_rejects_dev_role_header_in_production() -> None:
    with patch("apps.edr.app.settings.app_env", "production"):
        with pytest.raises(HTTPException) as exc:
            _extract_claims(authorization=None, x_user_role="executive", x_user_id=None)
    assert exc.value.status_code == 400
    assert "dev bypass headers" in exc.value.detail


def test_extract_claims_rejects_dev_id_header_in_production() -> None:
    with patch("apps.edr.app.settings.app_env", "production"):
        with pytest.raises(HTTPException) as exc:
            _extract_claims(authorization=None, x_user_role=None, x_user_id="someone")
    assert exc.value.status_code == 400


def test_extract_claims_rejects_dev_headers_even_with_bearer_in_production() -> None:
    with (
        patch("apps.edr.app.settings.app_env", "production"),
        patch("apps.edr.app.settings.entra_client_id", "cid"),
        patch("apps.edr.app.settings.entra_tenant_id", "tid"),
    ):
        with pytest.raises(HTTPException) as exc:
            _extract_claims(authorization="Bearer abc", x_user_role="admin", x_user_id=None)
    assert exc.value.status_code == 400


def test_extract_claims_production_validates_bearer_token() -> None:
    fake = MagicMock(user_id="oid-1", role="executive")
    with (
        patch("apps.edr.app.settings.app_env", "production"),
        patch("apps.edr.app.settings.entra_client_id", "cid"),
        patch("apps.edr.app.settings.entra_tenant_id", "tid"),
        patch("apps.edr.app.EntraJWTValidator") as validator_cls,
    ):
        validator_cls.return_value.validate.return_value = fake
        claims = _extract_claims(authorization="Bearer abc", x_user_role=None, x_user_id=None)
    assert claims is fake


def test_extract_claims_production_without_entra_raises_500() -> None:
    with (
        patch("apps.edr.app.settings.app_env", "production"),
        patch("apps.edr.app.settings.entra_client_id", None),
        patch("apps.edr.app.settings.entra_tenant_id", None),
    ):
        with pytest.raises(HTTPException) as exc:
            _extract_claims(authorization=None, x_user_role=None, x_user_id=None)
    assert exc.value.status_code == 500


def test_extract_claims_local_bypass_unchanged() -> None:
    with (
        patch("apps.edr.app.settings.app_env", "local"),
        patch("apps.edr.app.settings.entra_client_id", None),
        patch("apps.edr.app.settings.entra_tenant_id", None),
    ):
        claims = _extract_claims(authorization=None, x_user_role="finance", x_user_id="u1")
    assert claims is not None
    assert claims.role == "finance"
    assert claims.user_id == "u1"
