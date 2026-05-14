"""Phase 1G integration tests.

Cover human review gate: approve, reject, request-revision endpoints,
final download, Node 16/17 behavior, RBAC, self-approval blocking,
admin override, write-once final artifacts, and approval-log.json.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.graph import node_16_review, node_17_publish
from apps.edr.graph.state import DecisionState
from apps.edr.persistence.hash import hash_user_id
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_row(
    request_id: str = "req-1g-001",
    user_id: str = "user-42",
    review_state: str = "staging",
    requires_approval: bool = True,
    quality_gate_status: str = "passed",
) -> dict:
    return {
        "request_id": request_id,
        "user_id_hash": hash_user_id(user_id),
        "quality_gate_status": quality_gate_status,
        "review_state": review_state,
        "requires_approval": requires_approval,
        "artifact_keys": [f"staging/{request_id}/executive-decision-report.md"],
    }


def _make_state(request_id: str = "req-1g-001") -> DecisionState:
    return DecisionState(
        request_id=request_id,
        user_id="user-42",
        role="executive",
        project_code="PRJ-001",
        query="What is the budget status?",
    )


# ---------------------------------------------------------------------------
# Approve endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_writes_approval_record_with_hashed_reviewer_id() -> None:
    from apps.edr.app import approve_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row())
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        response = await approve_report(
            request_id="req-1g-001",
            body=MagicMock(comment="Looks good"),
            claims=MagicMock(user_id="reviewer-01", role="executive"),
        )

    assert response["new_state"] == "approved"
    call_kwargs = mock_pg.insert_review_decision.call_args.kwargs
    assert call_kwargs["reviewer_id_hash"] == hash_user_id("reviewer-01")
    assert call_kwargs["reviewer_id_hash"] != "reviewer-01"
    assert call_kwargs["action"] == "approve"


@pytest.mark.asyncio
async def test_approve_blocks_self_approval() -> None:
    from apps.edr.app import approve_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(user_id="user-42"))

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await approve_report(
                request_id="req-1g-001",
                body=MagicMock(comment=""),
                claims=MagicMock(user_id="user-42", role="executive"),
            )
    assert exc_info.value.status_code == 403
    assert "self-approval" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_approve_blocks_auditor() -> None:
    from apps.edr.app import approve_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row())

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await approve_report(
                request_id="req-1g-001",
                body=MagicMock(comment=""),
                claims=MagicMock(user_id="auditor-01", role=Role.AUDITOR.value),
            )
    assert exc_info.value.status_code == 403
    assert "auditor" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_approve_admin_override_requires_comment() -> None:
    from apps.edr.app import approve_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row())
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    # Missing comment
    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await approve_report(
                request_id="req-1g-001",
                body=MagicMock(comment=None),
                claims=MagicMock(user_id="admin-01", role=Role.ADMIN.value),
            )
    assert exc_info.value.status_code == 400
    assert "mandatory comment" in str(exc_info.value.detail).lower()

    # With comment — succeeds and creates admin_override action
    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        response = await approve_report(
            request_id="req-1g-001",
            body=MagicMock(comment="Emergency override"),
            claims=MagicMock(user_id="admin-01", role=Role.ADMIN.value),
        )
    assert response["action"] == "admin_override"
    assert mock_pg.insert_review_decision.call_args.kwargs["action"] == "admin_override"


# ---------------------------------------------------------------------------
# Reject endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_requires_reason() -> None:

    # Pydantic validates min_length at the framework layer; verify the schema itself.
    from apps.edr.app import RejectRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RejectRequest(reason="")


@pytest.mark.asyncio
async def test_reject_writes_rejection_record() -> None:
    from apps.edr.app import reject_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row())
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        response = await reject_report(
            request_id="req-1g-001",
            body=MagicMock(reason="Insufficient evidence"),
            claims=MagicMock(user_id="reviewer-01", role="executive"),
        )

    assert response["new_state"] == "rejected"
    call_kwargs = mock_pg.insert_review_decision.call_args.kwargs
    assert call_kwargs["reason"] == "Insufficient evidence"
    assert call_kwargs["action"] == "approve"  # normal reviewer action type


# ---------------------------------------------------------------------------
# Request-revision endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_revision_writes_decision() -> None:
    from apps.edr.app import request_revision

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row())
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        response = await request_revision(
            request_id="req-1g-001",
            body=MagicMock(reason="Missing Odoo data", comment="Please re-run with Odoo scope"),
            claims=MagicMock(user_id="reviewer-01", role="executive"),
        )

    assert response["new_state"] == "revision_requested"
    call_kwargs = mock_pg.insert_review_decision.call_args.kwargs
    assert call_kwargs["reason"] == "Missing Odoo data"
    assert call_kwargs["comment"] == "Please re-run with Odoo scope"


# ---------------------------------------------------------------------------
# Node 16 — Review state exposure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_16_reflects_pending_when_no_decisions() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="staging"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[])

    with patch("apps.edr.graph.node_16_review.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_16_review.run(state)

    assert result.outputs["human_review_status"] == "pending"
    assert result.outputs["review_state"] == "staging"


@pytest.mark.asyncio
async def test_node_16_reflects_approved() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="approved"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "approve"}])

    with patch("apps.edr.graph.node_16_review.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_16_review.run(state)

    assert result.outputs["human_review_status"] == "approved"
    assert result.outputs["review_state"] == "approved"
    assert result.outputs["review_decisions_count"] == 1


@pytest.mark.asyncio
async def test_node_16_reflects_rejected() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="rejected"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "reject"}])

    with patch("apps.edr.graph.node_16_review.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_16_review.run(state)

    assert result.outputs["human_review_status"] == "rejected"


@pytest.mark.asyncio
async def test_node_16_reflects_revision_requested() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="revision_requested"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "request_revision"}])

    with patch("apps.edr.graph.node_16_review.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_16_review.run(state)

    assert result.outputs["human_review_status"] == "revision_requested"


# ---------------------------------------------------------------------------
# Node 17 — Publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_17_publishes_when_approved() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="approved"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "approve", "reviewer_id_hash": "abc"}])
    mock_pg.update_review_state = AsyncMock(return_value=None)

    mock_minio = MagicMock()
    mock_minio.copy_to_final.return_value = "final/req-1g-001/executive-decision-report.md"
    mock_minio.put_json.return_value = "final/req-1g-001/approval-log.json"

    with (
        patch("apps.edr.graph.node_17_publish.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.graph.node_17_publish.get_minio_store", return_value=mock_minio),
    ):
        state = _make_state()
        result = await node_17_publish.run(state)

    assert result.outputs["publish_status"] == "published"
    mock_minio.copy_to_final.assert_called()
    mock_minio.put_json.assert_called_once()


@pytest.mark.asyncio
async def test_node_17_blocks_when_no_approval() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="staging"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[])

    with patch("apps.edr.graph.node_17_publish.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_17_publish.run(state)

    assert result.outputs["publish_status"] == "blocked_until_approval"


@pytest.mark.asyncio
async def test_node_17_rejects_rejected_reports() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="rejected"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "reject"}])

    with patch("apps.edr.graph.node_17_publish.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_17_publish.run(state)

    assert result.outputs["publish_status"] == "rejected"


@pytest.mark.asyncio
async def test_node_17_rejects_revision_requested_reports() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="revision_requested"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "request_revision"}])

    with patch("apps.edr.graph.node_17_publish.get_postgres_store", return_value=mock_pg):
        state = _make_state()
        result = await node_17_publish.run(state)

    assert result.outputs["publish_status"] == "revision_requested"


@pytest.mark.asyncio
async def test_node_17_final_artifacts_are_write_once() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="approved"))
    mock_pg.get_review_decisions = AsyncMock(return_value=[{"action": "approve"}])
    mock_pg.update_review_state = AsyncMock(return_value=None)

    mock_minio = MagicMock()
    # First call succeeds, second raises FileExistsError (simulating write-once)
    mock_minio.copy_to_final.side_effect = [
        "final/req-1g-001/executive-decision-report.md",
        FileExistsError("already exists"),
        FileExistsError("already exists"),
        FileExistsError("already exists"),
        FileExistsError("already exists"),
    ]
    mock_minio.put_json.return_value = "final/req-1g-001/approval-log.json"

    with (
        patch("apps.edr.graph.node_17_publish.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.graph.node_17_publish.get_minio_store", return_value=mock_minio),
    ):
        state = _make_state()
        result = await node_17_publish.run(state)

    assert result.outputs["publish_status"] == "published"
    # Should still contain the final keys even when some copies were skipped
    assert "final_artifact_keys" in result.outputs


# ---------------------------------------------------------------------------
# Download behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_staging_download_blocked_before_approval() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_make_audit_row(review_state="staging", requires_approval=True)
    )

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_report(
                request_id="req-1g-001",
                fmt="md",
                claims=MagicMock(user_id="user-42", role="executive"),
            )
    assert exc_info.value.status_code == 403
    assert "awaiting approval" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_final_download_succeeds_after_approval() -> None:
    from apps.edr.app import download_final_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_make_audit_row(review_state="final", requires_approval=True)
    )

    mock_minio = MagicMock()
    mock_minio.get_object.return_value = b"# Final Report\n"

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.get_minio_store", return_value=mock_minio),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        response = await download_final_report(
            request_id="req-1g-001",
            fmt="md",
            claims=MagicMock(user_id="user-42", role="executive"),
        )

    assert response.status_code == 200
    assert response.body == b"# Final Report\n"
    mock_minio.get_object.assert_called_once_with(
        "req-1g-001", "executive-decision-report.md", prefix="final"
    )


def test_minio_copy_to_final_uses_minio_copy_source() -> None:
    from minio.commonconfig import CopySource

    from apps.edr.persistence.minio_store import MinioStore

    store = object.__new__(MinioStore)
    store._bucket = "reports"
    store._client = MagicMock()
    store._ensure_bucket = MagicMock()
    store.object_exists = MagicMock(return_value=False)

    key = store.copy_to_final("req-1g-001", "executive-decision-report.md")

    assert key == "final/req-1g-001/executive-decision-report.md"
    store._client.copy_object.assert_called_once()
    args = store._client.copy_object.call_args.args
    assert args[0] == "reports"
    assert args[1] == "final/req-1g-001/executive-decision-report.md"
    assert isinstance(args[2], CopySource)
    assert args[2].bucket_name == "reports"
    assert args[2].object_name == "staging/req-1g-001/executive-decision-report.md"


@pytest.mark.asyncio
async def test_final_download_blocked_before_finalization() -> None:
    from apps.edr.app import download_final_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_make_audit_row(review_state="approved", requires_approval=True)
    )

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_final_report(
                request_id="req-1g-001",
                fmt="md",
                claims=MagicMock(user_id="user-42", role="executive"),
            )
    assert exc_info.value.status_code == 403
    assert "not yet finalized" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_quality_gate_failed_blocks_all_downloads() -> None:
    from apps.edr.app import download_report, download_final_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_make_audit_row(quality_gate_status="failed")
    )

    for endpoint in (download_report, download_final_report):
        with (
            patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
            patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
            patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await endpoint(
                    request_id="req-1g-001",
                    fmt="md",
                    claims=MagicMock(user_id="user-42", role="executive"),
                )
        assert exc_info.value.status_code == 403
        assert "quality gate failed" in str(exc_info.value.detail).lower()


# ---------------------------------------------------------------------------
# Approval-log.json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_log_json_written_once() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row(review_state="approved"))
    mock_pg.get_review_decisions = AsyncMock(
        return_value=[
            {"action": "approve", "reviewer_id_hash": "hash-1", "created_at": "2026-01-01T00:00:00", "comment": "Approved"}
        ]
    )
    mock_pg.update_review_state = AsyncMock(return_value=None)

    mock_minio = MagicMock()
    mock_minio.copy_to_final.return_value = "final/req-1g-001/executive-decision-report.md"

    with (
        patch("apps.edr.graph.node_17_publish.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.graph.node_17_publish.get_minio_store", return_value=mock_minio),
    ):
        state = _make_state()
        result = await node_17_publish.run(state)

    assert result.outputs["publish_status"] == "published"
    # put_json should be called once for approval-log.json
    assert mock_minio.put_json.call_count == 1
    args = mock_minio.put_json.call_args
    assert args[0][1] == "approval-log.json"
    assert args[1].get("prefix") == "final"


# ---------------------------------------------------------------------------
# Unauthorized roles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthorized_role_blocked_from_review() -> None:
    from apps.edr.app import approve_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_make_audit_row())

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await approve_report(
                request_id="req-1g-001",
                body=MagicMock(comment=""),
                claims=MagicMock(user_id="rando-01", role="unknown_role"),
            )
    assert exc_info.value.status_code == 403
