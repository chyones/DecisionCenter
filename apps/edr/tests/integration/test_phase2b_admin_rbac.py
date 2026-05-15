"""Phase 2B Slice 1 — Admin RBAC base.

Verifies the shared admin gate (``_require_admin``) that every subsequent
Phase 2B endpoint will reuse. Exercises:

- One case per canonical role calling ``GET /admin/_authcheck``.
- Edge cases: missing role, unknown role string, missing claims in
  production-shape mode.

These tests intentionally avoid touching persistence or external services so
they remain fast and stable in CI.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from apps.edr.app import _require_admin, admin_authcheck
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claims(role: str | None, user_id: str = "user-admin") -> MagicMock:
    return MagicMock(user_id=user_id, role=role)


_NON_ADMIN_ROLES: list[str] = [
    Role.EXECUTIVE.value,
    Role.PROJECT_MANAGER.value,
    Role.FINANCE.value,
    Role.COMMERCIAL.value,
    Role.DOCUMENT_CONTROL.value,
    Role.PROCUREMENT.value,
    Role.LEGAL.value,
    Role.AUDITOR.value,
]


# ---------------------------------------------------------------------------
# /admin/_authcheck — role-by-role coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_authcheck_allows_admin_role() -> None:
    response = await admin_authcheck(claims=_claims(role=Role.ADMIN.value))
    assert response == {"ok": True, "role": Role.ADMIN.value}


@pytest.mark.asyncio
@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
async def test_admin_authcheck_denies_every_non_admin_role(role: str) -> None:
    with pytest.raises(HTTPException) as exc:
        await admin_authcheck(claims=_claims(role=role))
    assert exc.value.status_code == 403
    assert "admin" in str(exc.value.detail).lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_authcheck_rejects_missing_role() -> None:
    with pytest.raises(HTTPException) as exc:
        await admin_authcheck(claims=_claims(role=None))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_authcheck_rejects_unknown_role_string() -> None:
    with pytest.raises(HTTPException) as exc:
        await admin_authcheck(claims=_claims(role="manager-of-coffee"))
    assert exc.value.status_code == 403
    assert "invalid role" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_admin_authcheck_rejects_missing_claims() -> None:
    """Production-mode shape: ``_extract_claims`` would return ``None`` only
    when Entra is misconfigured. ``_require_admin`` must surface that as a
    401 — distinct from the 403 used for role denial."""
    with pytest.raises(HTTPException) as exc:
        await admin_authcheck(claims=None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# _require_admin direct behaviour (separate from the route, so the helper is
# usable by future endpoints without going through FastAPI's dependency
# injection)
# ---------------------------------------------------------------------------


def test_require_admin_returns_claims_for_admin() -> None:
    claims = _claims(role=Role.ADMIN.value)
    out = _require_admin(claims)
    assert out is claims


def test_require_admin_raises_403_for_auditor() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(_claims(role=Role.AUDITOR.value))
    assert exc.value.status_code == 403


def test_require_admin_raises_401_when_claims_none() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401
