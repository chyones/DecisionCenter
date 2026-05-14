"""Phase 2A backend additions — integration tests.

Covers the five endpoints added to close gap G12:

- ``GET    /reports``                — list, with RBAC scoping & filters
- ``GET    /reports/{id}``           — metadata + review decisions
- ``GET    /reports/{id}/status``    — processing state for the polling loop
- ``DELETE /reports/{id}``           — cancel a non-terminal report
- ``POST   /upload``                 — multipart file upload to MinIO

The tests mock PostgresStore and MinioStore so they run in CI without a live
stack, matching the Phase 1F/1G test pattern.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from apps.edr.app import (
    cancel_report,
    get_report,
    get_report_content,
    get_report_status,
    get_workspace_context,
    list_reports,
    upload_file,
    _derive_external_state,
    _exported_formats,
    _query_excerpt,
    _safe_filename,
)
from apps.edr.persistence.hash import hash_user_id
from apps.edr.rbac.roles import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit_row(
    *,
    request_id: str = "req-2a-001",
    user_id_hash: str | None = None,
    project_code: str = "PRJ-001",
    query: str = "What is the budget status?",
    quality_gate_status: str = "passed",
    review_state: str = "staging",
    requires_approval: bool = True,
    artifact_keys: list[str] | str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> dict:
    if user_id_hash is None:
        user_id_hash = hash_user_id("user-42")
    if artifact_keys is None:
        artifact_keys = [
            f"staging/{request_id}/executive-decision-report.md",
            f"staging/{request_id}/evidence-pack.json",
        ]
    ts = datetime(2026, 5, 14, 9, 0, 0, tzinfo=timezone.utc)
    return {
        "id": 1,
        "request_id": request_id,
        "user_id_hash": user_id_hash,
        "project_code": project_code,
        "query": query,
        "quality_gate_status": quality_gate_status,
        "token_counts": {},
        "cost_total_usd": 1.0,
        "artifact_keys": artifact_keys,
        "review_state": review_state,
        "requires_approval": requires_approval,
        "created_at": created_at or ts,
        "updated_at": updated_at or ts,
    }


def _claims(user_id: str = "user-42", role: str = Role.EXECUTIVE.value) -> MagicMock:
    """Return a mock JWTClaims object with ``user_id`` and ``role`` attributes."""
    return MagicMock(user_id=user_id, role=role)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_derive_external_state_terminal_review_states_win() -> None:
    for review_state in ("final", "rejected", "approved", "revision_requested", "cancelled"):
        audit = _audit_row(review_state=review_state, quality_gate_status="failed")
        assert _derive_external_state(audit) == review_state


def test_derive_external_state_failed_gate_overrides_staging() -> None:
    assert _derive_external_state(
        _audit_row(review_state="staging", quality_gate_status="failed")
    ) == "failed"


def test_derive_external_state_needs_review_when_gate_says_so() -> None:
    assert _derive_external_state(
        _audit_row(review_state="staging", quality_gate_status="needs_review")
    ) == "needs_review"


def test_derive_external_state_defaults_to_staging() -> None:
    assert _derive_external_state(
        _audit_row(review_state="staging", quality_gate_status="passed")
    ) == "staging"


def test_query_excerpt_truncates_with_ellipsis() -> None:
    long = "x" * 200
    out = _query_excerpt(long, limit=120)
    assert out is not None
    assert len(out) == 120
    assert out.endswith("…")


def test_query_excerpt_returns_short_query_unchanged() -> None:
    assert _query_excerpt("hello") == "hello"


def test_exported_formats_filters_to_known_extensions() -> None:
    audit = _audit_row(
        artifact_keys=[
            "staging/req/executive-decision-report.md",
            "staging/req/executive-decision-report.pdf",
            "staging/req/evidence-pack.json",  # not a report format
            "staging/req/audit-log.json",
            "staging/req/executive-decision-report.docx",
        ]
    )
    assert _exported_formats(audit) == ["md", "pdf", "docx"]


def test_safe_filename_strips_directory_and_unsafe_chars() -> None:
    assert _safe_filename("../../etc/passwd") == "passwd"
    assert _safe_filename("contracts/contract 2024.pdf") == "contract_2024.pdf"
    assert _safe_filename("") == "upload"
    assert _safe_filename("///") == "upload"


# ---------------------------------------------------------------------------
# GET /workspace/context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_context_returns_projects_for_report_role() -> None:
    response = await get_workspace_context(
        claims=_claims(role=Role.EXECUTIVE.value)
    )

    assert response.can_generate_report is True
    assert response.can_approve is True
    assert [p.project_code for p in response.allowed_projects] == ["PRJ-001", "PRJ-002"]


@pytest.mark.asyncio
async def test_workspace_context_empty_for_non_report_role() -> None:
    response = await get_workspace_context(claims=_claims(role=Role.AUDITOR.value))

    assert response.can_generate_report is False
    assert response.allowed_projects == []


@pytest.mark.asyncio
async def test_workspace_context_denies_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_workspace_context(claims=_claims(role=Role.ADMIN.value))

    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# GET /reports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_scopes_to_own_user_for_normal_role() -> None:
    rows = [_audit_row(request_id="req-1"), _audit_row(request_id="req-2")]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audits = AsyncMock(return_value=(rows, 2))

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await list_reports(
            claims=_claims(user_id="user-42", role=Role.EXECUTIVE.value),
            state=None,
            project_code=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
        )

    mock_pg.list_audits.assert_awaited_once()
    kwargs = mock_pg.list_audits.call_args.kwargs
    assert kwargs["user_id_hash"] == hash_user_id("user-42")
    assert response.total == 2
    assert len(response.reports) == 2
    assert response.reports[0].request_id == "req-1"


@pytest.mark.asyncio
async def test_list_reports_passes_query_filters_to_pg() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audits = AsyncMock(return_value=([], 0))

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await list_reports(
            claims=_claims(),
            state="needs_review",
            project_code="PRJ-002",
            date_from=datetime(2026, 5, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 5, 14, tzinfo=timezone.utc),
            limit=25,
            offset=10,
        )

    kwargs = mock_pg.list_audits.call_args.kwargs
    assert kwargs["state"] == "needs_review"
    assert kwargs["project_code"] == "PRJ-002"
    assert kwargs["limit"] == 25
    assert kwargs["offset"] == 10
    assert response.limit == 25
    assert response.offset == 10


@pytest.mark.asyncio
async def test_list_reports_auditor_sees_all_users() -> None:
    """Auditors are not scoped by user_id_hash."""
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audits = AsyncMock(return_value=([], 0))

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        await list_reports(
            claims=_claims(role=Role.AUDITOR.value),
            state=None,
            project_code=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
        )

    kwargs = mock_pg.list_audits.call_args.kwargs
    assert kwargs["user_id_hash"] is None


@pytest.mark.asyncio
async def test_list_reports_admin_is_forbidden() -> None:
    """Admin must not see any business reports (CONTROL_PLANE_LOCK)."""
    with pytest.raises(HTTPException) as exc:
        await list_reports(
            claims=_claims(role=Role.ADMIN.value),
            state=None,
            project_code=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_list_reports_rejects_invalid_role() -> None:
    with pytest.raises(HTTPException) as exc:
        await list_reports(
            claims=_claims(role="manager-of-coffee"),
            state=None,
            project_code=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_list_reports_response_shape_is_typed() -> None:
    rows = [_audit_row(request_id="req-a", quality_gate_status="passed")]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.list_audits = AsyncMock(return_value=(rows, 1))

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await list_reports(
            claims=_claims(),
            state=None,
            project_code=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
        )

    summary = response.reports[0]
    assert summary.request_id == "req-a"
    assert summary.project_code == "PRJ-001"
    assert summary.state == "staging"
    assert summary.quality_gate == "passed"
    assert summary.requires_approval is True
    assert summary.query_excerpt == "What is the budget status?"


# ---------------------------------------------------------------------------
# GET /reports/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_report_returns_metadata_for_owner() -> None:
    audit = _audit_row()
    decisions = [
        {
            "action": "approve",
            "reason": None,
            "comment": "Looks good",
            "created_at": datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc),
        }
    ]
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=audit)
    mock_pg.get_review_decisions = AsyncMock(return_value=decisions)

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        detail = await get_report(request_id="req-2a-001", claims=_claims())

    assert detail.request_id == "req-2a-001"
    assert detail.state == "staging"
    assert detail.exported_formats == ["md"]
    assert len(detail.review_decisions) == 1
    assert detail.review_decisions[0].action == "approve"


@pytest.mark.asyncio
async def test_get_report_returns_404_when_unknown() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=None)

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_report(request_id="unknown", claims=_claims())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_report_denies_admin() -> None:
    """Admin role cannot view any report metadata."""
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row())

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_report(
                request_id="req-2a-001", claims=_claims(role=Role.ADMIN.value)
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_report_denies_other_user_in_entra_mode() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row())

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc:
            await get_report(
                request_id="req-2a-001",
                claims=_claims(user_id="attacker", role=Role.EXECUTIVE.value),
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_report_allows_auditor_in_entra_mode() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row())
    mock_pg.get_review_decisions = AsyncMock(return_value=[])

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        detail = await get_report(
            request_id="req-2a-001",
            claims=_claims(user_id="auditor-7", role=Role.AUDITOR.value),
        )
    assert detail.request_id == "req-2a-001"


# ---------------------------------------------------------------------------
# GET /reports/{id}/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_reflects_external_state() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_audit_row(quality_gate_status="failed")
    )

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        status = await get_report_status(request_id="req-2a-001", claims=_claims())

    assert status.state == "failed"
    assert status.is_terminal is True
    assert status.total_nodes == 18
    assert status.current_node == 18


@pytest.mark.asyncio
async def test_get_status_returns_404_for_unknown_report() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=None)

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_report_status(request_id="unknown", claims=_claims())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_status_denies_admin() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row())

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_report_status(
                request_id="req-2a-001", claims=_claims(role=Role.ADMIN.value)
            )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# GET /reports/{id}/content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_content_hides_needs_review_from_requester() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_audit_row(quality_gate_status="needs_review")
    )

    mock_minio = MagicMock()
    mock_minio.get_object.return_value = (
        b'{"checks":[{"verdict":"needs_review","reason":"Reviewer required"}]}'
    )

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.get_minio_store", return_value=mock_minio),
    ):
        response = await get_report_content(
            request_id="req-2a-001",
            claims=_claims(user_id="user-42", role=Role.EXECUTIVE.value),
        )

    assert response.state == "needs_review"
    assert response.content_available is False
    assert response.markdown is None
    assert response.quality_gate_flags == ["Reviewer required"]


@pytest.mark.asyncio
async def test_report_content_allows_reviewer_to_view_staged_draft() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(
        return_value=_audit_row(quality_gate_status="needs_review")
    )

    evidence_pack = (
        b'{"evidence":[{"evidence_id":"ev-1","source_type":"sharepoint",'
        b'"source_uri":"sp://doc","title":"Doc","excerpt":"Supported claim",'
        b'"hash_sha256":"abcdef0123456789","confidence":"high"}]}'
    )
    qg = b'{"checks":[{"verdict":"needs_review","reason":"Reviewer required"}]}'
    draft = (
        b'{"request_id":"req-2a-001","project_code":"PRJ-001","query":"q",'
        b'"executive_summary":[{"claim":"Supported claim","evidence_ids":["ev-1"],'
        b'"confidence":"high"}],"sources":[],"quality_gate_status":"needs_review"}'
    )

    def get_object(_request_id: str, filename: str, prefix: str = "staging") -> bytes:
        if filename == "quality-gate-result.json":
            return qg
        if filename == "evidence-pack.json":
            return evidence_pack
        if filename == "report-draft.json":
            return draft
        raise FileNotFoundError(filename)

    mock_minio = MagicMock()
    mock_minio.get_object.side_effect = get_object

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.get_minio_store", return_value=mock_minio),
    ):
        response = await get_report_content(
            request_id="req-2a-001",
            claims=_claims(user_id="reviewer-9", role=Role.PROJECT_MANAGER.value),
        )

    assert response.can_review is True
    assert response.content_available is True
    assert response.markdown is not None
    assert response.evidence[0].citation_label == "1"


@pytest.mark.asyncio
async def test_report_content_denies_admin() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row())

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await get_report_content(
                request_id="req-2a-001",
                claims=_claims(user_id="admin-1", role=Role.ADMIN.value),
            )

    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /reports/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_report_sets_state_and_records_decision() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row(review_state="staging"))
    mock_pg.insert_review_decision = AsyncMock(return_value=None)
    mock_pg.update_review_state = AsyncMock(return_value=None)

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        response = await cancel_report(request_id="req-2a-001", claims=_claims())

    assert response.state == "cancelled"
    mock_pg.insert_review_decision.assert_awaited_once()
    assert mock_pg.insert_review_decision.call_args.kwargs["action"] == "report.cancelled"
    mock_pg.update_review_state.assert_awaited_once_with("req-2a-001", "cancelled")


@pytest.mark.asyncio
async def test_cancel_report_denies_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        await cancel_report(
            request_id="req-2a-001",
            claims=_claims(user_id="admin-1", role=Role.ADMIN.value),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_cancel_report_blocks_terminal_states() -> None:
    for review_state, expected_external in (
        ("final", "final"),
        ("rejected", "rejected"),
        ("cancelled", "cancelled"),
    ):
        mock_pg = MagicMock()
        mock_pg.init_schema = AsyncMock(return_value=None)
        mock_pg.get_audit = AsyncMock(
            return_value=_audit_row(review_state=review_state)
        )

        with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
            with pytest.raises(HTTPException) as exc:
                await cancel_report(request_id="req-2a-001", claims=_claims())
        assert exc.value.status_code == 409
        assert expected_external in str(exc.value.detail).lower() or "cancelled" in str(
            exc.value.detail
        ).lower()


@pytest.mark.asyncio
async def test_cancel_report_owner_only_in_entra_mode() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=_audit_row())

    with (
        patch("apps.edr.app.get_postgres_store", return_value=mock_pg),
        patch("apps.edr.app.settings.entra_client_id", "test-client-id"),
        patch("apps.edr.app.settings.entra_tenant_id", "test-tenant-id"),
    ):
        with pytest.raises(HTTPException) as exc:
            await cancel_report(
                request_id="req-2a-001",
                claims=_claims(user_id="attacker", role=Role.EXECUTIVE.value),
            )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_cancel_report_returns_404_when_unknown() -> None:
    mock_pg = MagicMock()
    mock_pg.init_schema = AsyncMock(return_value=None)
    mock_pg.get_audit = AsyncMock(return_value=None)

    with patch("apps.edr.app.get_postgres_store", return_value=mock_pg):
        with pytest.raises(HTTPException) as exc:
            await cancel_report(request_id="unknown", claims=_claims())
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------


def _upload_file(
    *,
    filename: str = "doc.pdf",
    content_type: str = "application/pdf",
    data: bytes = b"%PDF-1.4\nminimal pdf body",
) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename, headers=None, size=None)


@pytest.mark.asyncio
async def test_upload_accepts_pdf_and_writes_to_minio() -> None:
    mock_minio = MagicMock()
    mock_minio.put_upload.return_value = "uploads/HASH/UID/doc.pdf"

    upload = _upload_file()
    upload.headers = {"content-type": "application/pdf"}  # type: ignore[attr-defined]

    with patch("apps.edr.app.get_minio_store", return_value=mock_minio):
        response = await upload_file(
            claims=_claims(user_id="user-42"),
            file=upload,
        )

    assert response.filename == "doc.pdf"
    assert response.size > 0
    assert response.content_type == "application/pdf"
    assert len(response.content_hash) == 64  # sha256 hex
    mock_minio.put_upload.assert_called_once()
    kwargs = mock_minio.put_upload.call_args.kwargs
    assert kwargs["user_id_hash"] == hash_user_id("user-42")
    assert kwargs["filename"] == "doc.pdf"


@pytest.mark.asyncio
async def test_upload_denies_admin() -> None:
    upload = _upload_file()

    with pytest.raises(HTTPException) as exc:
        await upload_file(
            claims=_claims(user_id="admin-1", role=Role.ADMIN.value),
            file=upload,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_upload_rejects_unknown_type() -> None:
    upload = UploadFile(
        file=io.BytesIO(b"\x00\x01\x02"),
        filename="virus.exe",
    )

    mock_minio = MagicMock()
    with patch("apps.edr.app.get_minio_store", return_value=mock_minio):
        with pytest.raises(HTTPException) as exc:
            await upload_file(claims=_claims(), file=upload)
    assert exc.value.status_code == 400
    assert not mock_minio.put_upload.called


@pytest.mark.asyncio
async def test_upload_rejects_cad_even_with_octet_stream_content_type() -> None:
    upload = UploadFile(
        file=io.BytesIO(b"cad"),
        filename="drawing.dwg",
        headers={"content-type": "application/octet-stream"},
    )

    mock_minio = MagicMock()
    with patch("apps.edr.app.get_minio_store", return_value=mock_minio):
        with pytest.raises(HTTPException) as exc:
            await upload_file(claims=_claims(), file=upload)
    assert exc.value.status_code == 400
    assert not mock_minio.put_upload.called


@pytest.mark.asyncio
async def test_upload_rejects_empty_body() -> None:
    upload = UploadFile(file=io.BytesIO(b""), filename="empty.pdf")
    mock_minio = MagicMock()
    with patch("apps.edr.app.get_minio_store", return_value=mock_minio):
        with pytest.raises(HTTPException) as exc:
            await upload_file(claims=_claims(), file=upload)
    assert exc.value.status_code == 400
    assert not mock_minio.put_upload.called


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file() -> None:
    oversized = b"x" * (10 * 1024 * 1024 + 1)
    upload = UploadFile(file=io.BytesIO(oversized), filename="big.pdf")

    mock_minio = MagicMock()
    with patch("apps.edr.app.get_minio_store", return_value=mock_minio):
        with pytest.raises(HTTPException) as exc:
            await upload_file(claims=_claims(), file=upload)
    assert exc.value.status_code == 413
    assert not mock_minio.put_upload.called


@pytest.mark.asyncio
async def test_upload_accepts_eml_by_extension_even_without_content_type() -> None:
    """``.eml`` and ``.msg`` files sometimes arrive as application/octet-stream;
    the extension whitelist must still accept them."""
    upload = UploadFile(
        file=io.BytesIO(b"From: a@b.com\nSubject: hello\n\nbody"),
        filename="thread.eml",
    )

    mock_minio = MagicMock()
    mock_minio.put_upload.return_value = "uploads/HASH/UID/thread.eml"
    with patch("apps.edr.app.get_minio_store", return_value=mock_minio):
        response = await upload_file(
            claims=_claims(user_id="user-42"),
            file=upload,
        )
    assert response.filename == "thread.eml"
    assert mock_minio.put_upload.called
