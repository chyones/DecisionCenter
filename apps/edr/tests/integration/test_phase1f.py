"""Phase 1F integration tests.

Cover MinIO persistence, PostgreSQL audit logging, hashed user IDs,
token/cost tracking, and download endpoint behavior.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.edr.graph import node_15_save_audit
from apps.edr.graph.state import DecisionState
from apps.edr.llm import reset_daily_cost, reset_token_usage
from apps.edr.persistence.hash import hash_user_id
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(gate: str = "passed", with_export: bool = True) -> DecisionState:
    state = DecisionState(
        request_id="req-1f-001",
        user_id="user-42",
        role="executive",
        project_code="PRJ-001",
        query="What is the budget status?",
        allowed_projects=["PRJ-001"],
        allowed_mailboxes=["pm@elrace.com"],
        evidence=[
            {
                "evidence_id": "ev_000001",
                "source_type": "odoo",
                "source_uri": "odoo://project.project/1",
                "title": "Budget",
                "excerpt": "Budget: 1000000",
                "hash_sha256": "a" * 64,
                "confidence": "high",
            }
        ],
    )
    state.cost_accumulated_usd = 1.2345
    state.outputs["quality_gate"] = gate
    state.outputs["quality_gate_result"] = {
        "request_id": "req-1f-001",
        "verdict": gate,
        "checks": [],
    }
    if with_export:
        state.outputs["report_exports_raw"] = {
            "md": b"# Report\n\nBudget is 1M AED.\n",
        }
    return state


# ---------------------------------------------------------------------------
# Node 15 — Artifact persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_15_writes_all_four_artifacts() -> None:
    reset_daily_cost()
    reset_token_usage("req-1f-001")
    state = _make_state()

    mock_minio = MagicMock()
    mock_minio.put_bytes.return_value = "staging/req-1f-001/executive-decision-report.md"
    mock_minio.put_json.side_effect = [
        "staging/req-1f-001/evidence-pack.json",
        "staging/req-1f-001/quality-gate-result.json",
        "staging/req-1f-001/audit-log.json",
    ]

    mock_pg = MagicMock()
    mock_pg.init_schema = MagicMock(return_value=None)
    mock_pg.insert_audit = MagicMock(return_value=None)

    with (
        patch("apps.edr.graph.node_15_save_audit.get_minio_store", return_value=mock_minio),
        patch("apps.edr.graph.node_15_save_audit.get_postgres_store", return_value=mock_pg),
    ):
        result = await node_15_save_audit.run(state)

    assert result.outputs["audit_status"] == "persisted"
    assert len(result.outputs["artifact_keys"]) == 4
    assert mock_minio.put_bytes.call_count == 1
    assert mock_minio.put_json.call_count == 3


@pytest.mark.asyncio
async def test_node_15_bucket_init_is_idempotent() -> None:
    """MinioStore._ensure_bucket is called by every put and is idempotent."""
    state = _make_state()
    mock_minio = MagicMock()
    mock_minio.put_bytes.return_value = "key-md"
    mock_minio.put_json.return_value = "key-json"

    mock_pg = MagicMock()
    mock_pg.init_schema = MagicMock(return_value=None)
    mock_pg.insert_audit = MagicMock(return_value=None)

    with (
        patch("apps.edr.graph.node_15_save_audit.get_minio_store", return_value=mock_minio),
        patch("apps.edr.graph.node_15_save_audit.get_postgres_store", return_value=mock_pg),
    ):
        await node_15_save_audit.run(state)

    # Each put operation triggers _ensure_bucket internally
    assert mock_minio.put_bytes.called
    assert mock_minio.put_json.called


@pytest.mark.asyncio
async def test_node_15_creates_audit_row() -> None:
    state = _make_state()
    mock_minio = MagicMock()
    mock_minio.put_bytes.return_value = "key-md"
    mock_minio.put_json.return_value = "key-json"

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_audit = AsyncMock(return_value=None)

    with (
        patch("apps.edr.graph.node_15_save_audit.get_minio_store", return_value=mock_minio),
        patch("apps.edr.graph.node_15_save_audit.get_postgres_store", return_value=mock_pg),
    ):
        await node_15_save_audit.run(state)

    mock_pg.init_schema.assert_awaited_once()
    mock_pg.insert_audit.assert_awaited_once()
    call_kwargs = mock_pg.insert_audit.call_args.kwargs
    assert call_kwargs["request_id"] == "req-1f-001"
    assert call_kwargs["quality_gate_status"] == "passed"


@pytest.mark.asyncio
async def test_node_15_never_stores_raw_user_id() -> None:
    state = _make_state()
    mock_minio = MagicMock()
    mock_minio.put_bytes.return_value = "key-md"
    mock_minio.put_json.return_value = "key-json"

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_audit = AsyncMock(return_value=None)

    with (
        patch("apps.edr.graph.node_15_save_audit.get_minio_store", return_value=mock_minio),
        patch("apps.edr.graph.node_15_save_audit.get_postgres_store", return_value=mock_pg),
    ):
        result = await node_15_save_audit.run(state)

    # Postgres insert
    call_kwargs = mock_pg.insert_audit.call_args.kwargs
    assert call_kwargs["user_id_hash"] == hash_user_id("user-42")
    assert call_kwargs["user_id_hash"] != "user-42"

    # MinIO audit-log artifact
    audit_log_arg = mock_minio.put_json.call_args_list[-1][0][2]
    assert audit_log_arg["user_id_hash"] == hash_user_id("user-42")
    assert "user-42" not in json.dumps(audit_log_arg)

    # State output
    assert result.outputs["audit_user_id_hash"] == hash_user_id("user-42")


@pytest.mark.asyncio
async def test_node_15_persists_token_and_cost_totals() -> None:
    reset_daily_cost()
    reset_token_usage("req-1f-001")
    state = _make_state()

    mock_minio = MagicMock()
    mock_minio.put_bytes.return_value = "key-md"
    mock_minio.put_json.return_value = "key-json"

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.insert_audit = AsyncMock(return_value=None)

    with (
        patch("apps.edr.graph.node_15_save_audit.get_minio_store", return_value=mock_minio),
        patch("apps.edr.graph.node_15_save_audit.get_postgres_store", return_value=mock_pg),
    ):
        await node_15_save_audit.run(state)

    call_kwargs = mock_pg.insert_audit.call_args.kwargs
    assert call_kwargs["cost_total_usd"] == 1.2345
    assert isinstance(call_kwargs["token_counts"], dict)


@pytest.mark.asyncio
async def test_node_15_audit_artifact_omits_confidential_content() -> None:
    state = _make_state()
    state.evidence = [
        {
            "evidence_id": "ev_000001",
            "source_type": "sharepoint",
            "source_uri": "/Contracts/Secret.pdf",
            "title": "Secret Contract",
            "excerpt": "Confidential terms...",
            "hash_sha256": "a" * 64,
            "confidence": "high",
        }
    ]

    mock_minio = MagicMock()
    mock_minio.put_bytes.return_value = "key-md"
    mock_minio.put_json.return_value = "key-json"

    mock_pg = MagicMock()
    mock_pg.init_schema = MagicMock(return_value=None)
    mock_pg.insert_audit = MagicMock(return_value=None)

    with (
        patch("apps.edr.graph.node_15_save_audit.get_minio_store", return_value=mock_minio),
        patch("apps.edr.graph.node_15_save_audit.get_postgres_store", return_value=mock_pg),
    ):
        await node_15_save_audit.run(state)

    # Audit-log artifact (last put_json call)
    audit_log_arg = mock_minio.put_json.call_args_list[-1][0][2]
    assert "evidence" not in audit_log_arg  # no full evidence content
    assert "Secret Contract" not in json.dumps(audit_log_arg)
    assert "Confidential" not in json.dumps(audit_log_arg)

    # Evidence pack (second put_json call) DOES contain evidence
    evidence_pack_arg = mock_minio.put_json.call_args_list[0][0][2]
    assert "evidence" in evidence_pack_arg


# ---------------------------------------------------------------------------
# Download endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_md_returns_persisted_markdown() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value={
            "request_id": "req-1f-001",
            "user_id_hash": hash_user_id("user-42"),
            "quality_gate_status": "passed",
            "requires_approval": False,
            "review_state": "staging",
        }
    )

    mock_minio = MagicMock()
    mock_minio.get_object.return_value = b"# Report\n\nBudget is 1M AED.\n"

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.get_minio_store", return_value=mock_minio),
    ):
        response = await download_report(
            request_id="req-1f-001",
            fmt="md",
            claims=MagicMock(user_id="user-42", role="executive"),
        )

    assert response.status_code == 200
    assert response.body == b"# Report\n\nBudget is 1M AED.\n"
    mock_minio.get_object.assert_called_once_with("req-1f-001", "executive-decision-report.md", prefix="staging")


@pytest.mark.asyncio
async def test_download_blocks_when_quality_gate_failed() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value={
            "request_id": "req-1f-001",
            "user_id_hash": hash_user_id("user-42"),
            "quality_gate_status": "failed",
        }
    )

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc_info:
            await download_report(
                request_id="req-1f-001",
                fmt="md",
                claims=MagicMock(user_id="user-42", role="executive"),
            )
    assert exc_info.value.status_code == 403
    assert "quality gate failed" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_download_rejects_invalid_format() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc_info:
            await download_report(
                request_id="req-1f-001",
                fmt="invalid",
                claims=MagicMock(user_id="user-42", role="executive"),
            )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_download_rejects_unknown_request_id() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=None)

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc_info:
            await download_report(
                request_id="unknown-id",
                fmt="md",
                claims=MagicMock(user_id="user-42", role="executive"),
            )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_download_blocks_unauthorized_user() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value={
            "request_id": "req-1f-001",
            "user_id_hash": hash_user_id("user-42"),
            "quality_gate_status": "passed",
        }
    )

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await download_report(
                request_id="req-1f-001",
                fmt="md",
                claims=MagicMock(user_id="attacker-99", role="executive"),
            )
    assert exc_info.value.status_code == 403
    assert "not authorized" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_download_allows_admin_or_auditor() -> None:
    from apps.edr.app import download_report

    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value={
            "request_id": "req-1f-001",
            "user_id_hash": hash_user_id("user-42"),
            "quality_gate_status": "passed",
            "requires_approval": False,
            "review_state": "staging",
        }
    )

    mock_minio = MagicMock()
    mock_minio.get_object.return_value = b"# Report\n"

    for role in (Role.ADMIN.value, Role.AUDITOR.value):
        with (
            patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
            patch("apps.edr.app.get_minio_store", return_value=mock_minio),
        ):
            response = await download_report(
                request_id="req-1f-001",
                fmt="md",
                claims=MagicMock(user_id="different-user", role=role),
            )
        assert response.status_code == 200
