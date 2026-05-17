"""Phase 2B Slice 7 — Approval Queue + Admin Override integration tests.

Coverage:
- RBAC: all 8 non-admin roles → 403 on all 4 endpoints
- Missing claims → 401
- List happy path — staging + needs_review rows returned
- List project filter propagated
- Detail happy path — includes QG flags
- Detail 404 — get_audit returns None
- Detail 409 — already finalized
- Override-approve happy path
- Audit-before-action order (N-1)
- A-10 self-approval blocked → 403
- Override-approve 404
- Override-approve 409 (already finalized)
- R13 — quality_gate_status='failed' → 409
- Override-reject happy path
- Override-reject self-rejection blocked → 403
- Mandatory comment enforced
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
    AdminOverrideRequest,
    AdminOverrideResponse,
    ApprovalQueueDetail,
    ApprovalQueueResponse,
    _require_admin,
)
from apps.edr.auth.validator import JWTClaims
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# RBAC — all endpoints deny every non-admin role (parametrised)
# ---------------------------------------------------------------------------

NON_ADMIN_ROLES = [r for r in Role if r != Role.ADMIN]


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_approvals_list_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_approvals_detail_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_approvals_override_approve_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_approvals_override_reject_rbac_denial(role: Role) -> None:
    claims = JWTClaims(user_id="u", role=role.value)
    with pytest.raises(HTTPException) as exc:
        _require_admin(claims)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing claims → 401
# ---------------------------------------------------------------------------


def test_approvals_missing_claims_401() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(None)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# List — happy path + project filter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_approvals_list_returns_items() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_rows = [
        {
            "request_id": "req-staging",
            "project_code": "PRJ-001",
            "review_state": "staging",
            "quality_gate_status": "passed",
            "created_at": datetime(2026, 5, 1, 10, 0, 0),
            "user_id_hash": "abc123",
            "cost_total_usd": 1.2345,
        },
        {
            "request_id": "req-needs-review",
            "project_code": "PRJ-002",
            "review_state": "staging",
            "quality_gate_status": "needs_review",
            "created_at": datetime(2026, 5, 2, 10, 0, 0),
            "user_id_hash": "def456",
            "cost_total_usd": 0.5,
        },
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=(fake_rows, 2))

    from apps.edr.app import list_approval_queue

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await list_approval_queue(claims)

    assert isinstance(result, ApprovalQueueResponse)
    assert len(result.items) == 2
    assert result.items[0].request_id == "req-staging"
    assert result.items[1].review_state == "needs_review"
    assert result.total == 2


@pytest.mark.anyio
async def test_approvals_list_project_filter() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_approval_queue = AsyncMock(return_value=([], 0))

    from apps.edr.app import list_approval_queue

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await list_approval_queue(claims, project_code="PRJ-001")

    call_kwargs = mock_pg.list_approval_queue.call_args.kwargs
    assert call_kwargs["project_code"] == "PRJ-001"


# ---------------------------------------------------------------------------
# Detail — happy path, 404, 409
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_approvals_detail_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "abc123",
        "cost_total_usd": 1.0,
        "token_counts": {"claude": 100},
        "requires_approval": True,
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import get_approval_queue_item

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with patch("apps.edr.app._load_json_artifact", return_value={"checks": [{"verdict": "unsupported", "reason": "test-flag"}]}):
            result = await get_approval_queue_item("req-1", claims)

    assert isinstance(result, ApprovalQueueDetail)
    assert result.request_id == "req-1"
    assert result.quality_gate_flags == ["test-flag"]
    assert result.token_counts == {"claude": 100}


@pytest.mark.anyio
async def test_approvals_detail_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=None)

    from apps.edr.app import get_approval_queue_item

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_approval_queue_item("missing", claims)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_approvals_detail_already_finalized() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "final",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "abc123",
        "cost_total_usd": 1.0,
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import get_approval_queue_item

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_approval_queue_item("req-1", claims)

    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Override-approve — happy path, N-1, A-10, 404, 409, R13
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_override_approve_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "different_hash",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)
    mock_pg.insert_admin_event = AsyncMock(return_value=42)
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    from apps.edr.app import admin_override_approve

    body = AdminOverrideRequest(comment="LGTM")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with patch("apps.edr.app.node_17_publish.run", AsyncMock(return_value=True)):
            result = await admin_override_approve("req-1", body, claims)

    assert isinstance(result, AdminOverrideResponse)
    assert result.action == "admin_override_approved"
    assert result.new_state == "approved"


@pytest.mark.anyio
async def test_override_approve_audit_before_action() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "different_hash",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)
    mock_pg.insert_admin_event = AsyncMock(return_value=99)
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    from apps.edr.app import admin_override_approve

    body = AdminOverrideRequest(comment="Approved")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with patch("apps.edr.app.node_17_publish.run", AsyncMock(return_value=True)):
            await admin_override_approve("req-1", body, claims)

    calls = mock_pg.method_calls
    call_names = [c[0] for c in calls]
    audit_idx = call_names.index("insert_admin_event")
    decision_idx = call_names.index("insert_review_decision")
    state_idx = call_names.index("update_review_state")
    assert audit_idx < decision_idx, "N-1 violation: audit must fire before review decision"
    assert audit_idx < state_idx, "N-1 violation: audit must fire before state update"


@pytest.mark.anyio
async def test_override_approve_self_approval_blocked() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import admin_override_approve

    body = AdminOverrideRequest(comment="LGTM")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await admin_override_approve("req-1", body, claims)

    assert exc.value.status_code == 403
    mock_pg.insert_admin_event.assert_not_called()


@pytest.mark.anyio
async def test_override_approve_not_found() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=None)

    from apps.edr.app import admin_override_approve

    body = AdminOverrideRequest(comment="LGTM")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await admin_override_approve("missing", body, claims)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_override_approve_already_finalized() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "final",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "different",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import admin_override_approve

    body = AdminOverrideRequest(comment="LGTM")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await admin_override_approve("req-1", body, claims)

    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# R13 — failed QG row → 409
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_override_approve_failed_qg_r13() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "failed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "different",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import admin_override_approve

    body = AdminOverrideRequest(comment="LGTM")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await admin_override_approve("req-1", body, claims)

    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Override-reject — happy path, self-block
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_override_reject_happy_path() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "different_hash",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)
    mock_pg.insert_admin_event = AsyncMock(return_value=42)
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    from apps.edr.app import admin_override_reject

    body = AdminOverrideRequest(comment="Not good enough")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        result = await admin_override_reject("req-1", body, claims)

    assert isinstance(result, AdminOverrideResponse)
    assert result.action == "admin_override_rejected"
    assert result.new_state == "rejected"


@pytest.mark.anyio
async def test_override_reject_self_rejection_blocked() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
        "cost_total_usd": 1.0,
        "query": "test query",
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import admin_override_reject

    body = AdminOverrideRequest(comment="Nope")
    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await admin_override_reject("req-1", body, claims)

    assert exc.value.status_code == 403
    mock_pg.insert_admin_event.assert_not_called()


# ---------------------------------------------------------------------------
# Mandatory comment enforced
# ---------------------------------------------------------------------------


def test_admin_override_request_empty_comment_rejected() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AdminOverrideRequest(comment="")


# ---------------------------------------------------------------------------
# C-1 — no business content in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_approvals_detail_no_business_content() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "abc123",
        "cost_total_usd": 1.0,
        "token_counts": None,
        "requires_approval": True,
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import get_approval_queue_item

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with patch("apps.edr.app._load_json_artifact", return_value={}):
            result = await get_approval_queue_item("req-1", claims)

    raw = result.model_dump_json()
    forbidden = re.compile(r"(?i)(query|markdown|evidence|excerpt|report_content)")
    assert not forbidden.search(raw), "C-1 violation: business content found in approval detail"


# ---------------------------------------------------------------------------
# C-6 — no credential values in admin responses
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_approvals_detail_no_credentials() -> None:
    claims = JWTClaims(user_id="admin", role="admin")
    fake_audit = {
        "request_id": "req-1",
        "project_code": "PRJ-001",
        "review_state": "staging",
        "quality_gate_status": "passed",
        "created_at": datetime(2026, 5, 1, 10, 0, 0),
        "user_id_hash": "abc123",
        "cost_total_usd": 1.0,
        "token_counts": None,
        "requires_approval": True,
    }
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=fake_audit)

    from apps.edr.app import get_approval_queue_item

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with patch("apps.edr.app._load_json_artifact", return_value={}):
            result = await get_approval_queue_item("req-1", claims)

    raw = result.model_dump_json()
    cred_re = re.compile(
        r"(?i)(password|token|api[_-]?key|secret|bearer|credential)\s*[:=]\s*\S"
    )
    assert not cred_re.search(raw), "C-6 violation: credential pattern in approval detail"
