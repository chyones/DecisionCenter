import hashlib
import os
import re
import socket
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from apps.edr.auth.validator import EntraJWTValidator, JWTClaims
from apps.edr.config import settings
from apps.edr.exporters.base import MIME_TYPES
from apps.edr.graph.runner import NODE_COUNT, run_workflow
from apps.edr.graph.state import DecisionState
from apps.edr.persistence import get_minio_store, get_postgres_store, hash_user_id
from apps.edr.rbac.project_mapping import RbacDeniedError
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role

app = FastAPI(
    title="Decision Center",
    version="0.1.0",
    description="Read-only executive decision report workflow.",
)


class ReportRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    project_code: str | None = None
    contract_no: str | None = None
    vendor: str | None = None
    date_range: str | None = None
    document_type: str | None = None
    mailbox_scope: str | None = None
    output_formats: list[Literal["md", "docx", "xlsx", "pdf", "pptx"]] = ["md"]


class ApproveRequest(BaseModel):
    comment: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class RequestRevisionRequest(BaseModel):
    reason: str = Field(min_length=1)
    comment: str | None = None


# ---------------------------------------------------------------------------
# Phase 2A backend additions — response models for the read/status/cancel/upload
# endpoints required by `docs/execution/PHASE_2A_PLAN.md` §F.2.
# ---------------------------------------------------------------------------


class ReportSummary(BaseModel):
    request_id: str
    project_code: str | None
    query_excerpt: str | None
    state: str
    quality_gate: str | None
    requires_approval: bool
    created_at: datetime | None
    updated_at: datetime | None


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]
    total: int
    limit: int
    offset: int


class ReviewDecisionView(BaseModel):
    action: str
    reason: str | None
    comment: str | None
    created_at: datetime | None


class ReportDetail(BaseModel):
    request_id: str
    project_code: str | None
    query: str | None
    state: str
    quality_gate: str | None
    requires_approval: bool
    created_at: datetime | None
    updated_at: datetime | None
    exported_formats: list[str]
    review_decisions: list[ReviewDecisionView]


class ReportStatusResponse(BaseModel):
    request_id: str
    state: str
    quality_gate: str | None
    total_nodes: int
    current_node: int
    is_terminal: bool
    updated_at: datetime | None


class CancelReportResponse(BaseModel):
    request_id: str
    state: str


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    size: int
    content_type: str
    content_hash: str


# Accepted upload types — mirrors `frontend/src/screens/UploadZone.tsx` constants.
_ACCEPTED_UPLOAD_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "message/rfc822",
        # Some clients send empty/octet-stream for .msg/.eml; the extension check
        # below covers those.
        "application/octet-stream",
    }
)
_ACCEPTED_UPLOAD_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".docx", ".xlsx", ".txt", ".msg", ".eml"}
)
_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB per file, matches UploadZone


def _extract_claims(
    authorization: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> JWTClaims | None:
    """Returns JWTClaims from a real Entra Bearer token, or None in bypass mode.

    Bypass mode is active when ENTRA_CLIENT_ID is not configured — for local dev
    and CI only. In bypass mode, pass X-User-Role header to set the role.
    """
    if settings.entra_client_id and settings.entra_tenant_id:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization: Bearer <token> required")
        token = authorization.removeprefix("Bearer ")
        validator = EntraJWTValidator(settings.entra_tenant_id, settings.entra_client_id)
        try:
            return validator.validate(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    # Bypass mode — Entra not configured
    if settings.app_env == "production":
        raise HTTPException(status_code=500, detail="ENTRA_CLIENT_ID not configured in production")
    return JWTClaims(user_id="", role=x_user_role)


def _require_claims(
    claims: JWTClaims | None,
) -> JWTClaims:
    """Ensure claims are present (production mode only)."""
    if claims is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return claims


def _check_reviewer_rbac(claims: JWTClaims) -> str:
    """Return the action type for the reviewer's role.

    Normal roles with can_approve=True use 'approve'.
    Admin uses 'admin_override' (metadata-only).
    Auditor and roles without can_approve are blocked.
    """
    role = claims.role
    if not role:
        raise HTTPException(status_code=403, detail="Role is required.")

    try:
        role_enum = Role(role)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=f"Invalid role: {role}") from exc

    perms = ROLE_PERMISSIONS[role_enum]

    if role_enum == Role.AUDITOR:
        raise HTTPException(status_code=403, detail="Auditor cannot approve, reject, or request revision.")

    if role_enum == Role.ADMIN:
        return "admin_override"

    if not perms.can_approve:
        raise HTTPException(status_code=403, detail="Role is not authorized to review reports.")

    return "approve"


# ---------------------------------------------------------------------------
# Phase 2A backend additions — RBAC helpers and derivations
# ---------------------------------------------------------------------------


def _validated_role(claims: JWTClaims) -> Role:
    """Resolve and validate the caller's role enum. Raises 403 on missing/invalid."""
    role = claims.role
    if not role:
        raise HTTPException(status_code=403, detail="Role is required.")
    try:
        return Role(role)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=f"Invalid role: {role}") from exc


def _derive_external_state(audit: dict[str, Any]) -> str:
    """Map audit_log columns onto the external state name used by the UI.

    Precedence:
    1. Terminal review_state values (``final``, ``rejected``, ``approved``,
       ``revision_requested``, ``cancelled``) win regardless of quality_gate.
    2. ``quality_gate_status == "failed"`` -> ``failed`` (gate blocks downstream).
    3. ``quality_gate_status == "needs_review"`` -> ``needs_review``.
    4. Otherwise the workflow has produced a draft awaiting decision: ``staging``.
    """
    review_state = audit.get("review_state") or "staging"
    if review_state in {"final", "rejected", "approved", "revision_requested", "cancelled"}:
        return review_state
    quality_gate = audit.get("quality_gate_status")
    if quality_gate == "failed":
        return "failed"
    if quality_gate == "needs_review":
        return "needs_review"
    return "staging"


def _is_terminal_state(state: str) -> bool:
    return state in {"final", "rejected", "cancelled", "failed"}


def _query_excerpt(query: str | None, limit: int = 120) -> str | None:
    if not query:
        return None
    return query if len(query) <= limit else query[: limit - 1].rstrip() + "…"


def _exported_formats(audit: dict[str, Any]) -> list[str]:
    raw_keys = audit.get("artifact_keys")
    if isinstance(raw_keys, str):
        import json as _json

        try:
            keys = _json.loads(raw_keys)
        except _json.JSONDecodeError:
            return []
    else:
        keys = raw_keys or []
    formats: list[str] = []
    for key in keys:
        if isinstance(key, str) and key.endswith(".md") and "executive-decision-report" in key:
            formats.append("md")
        elif isinstance(key, str) and key.endswith(".docx"):
            formats.append("docx")
        elif isinstance(key, str) and key.endswith(".xlsx"):
            formats.append("xlsx")
        elif isinstance(key, str) and key.endswith(".pdf"):
            formats.append("pdf")
        elif isinstance(key, str) and key.endswith(".pptx"):
            formats.append("pptx")
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for fmt in formats:
        if fmt not in seen:
            seen.add(fmt)
            out.append(fmt)
    return out


def _check_can_read_own_report(
    claims: JWTClaims | None, audit: dict[str, Any]
) -> None:
    """Authorize a read against a single audit row.

    Rules (server-enforced; the UX guards in the frontend are cosmetic):
    - admin: forbidden — admins must not see business data per
      ``docs/admin/CONTROL_PLANE_LOCK.md`` and the locked UI contract.
    - auditor: allowed (read-only across all projects).
    - everyone else: only when the requester's hashed user_id matches the
      stored ``user_id_hash``.
    """
    # In bypass mode without configured Entra, only enforce admin denial when
    # a role is given. The download endpoint uses the same pattern.
    if settings.entra_client_id and settings.entra_tenant_id:
        if claims is None or not claims.user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")

    role_str = claims.role if claims else None
    if role_str == Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to view report data.",
        )

    # Bypass mode (no Entra): role is the only signal. Block admin (above);
    # allow everyone else through. The download endpoint applies the same
    # relaxation in bypass mode.
    if not (settings.entra_client_id and settings.entra_tenant_id):
        return

    if role_str == Role.AUDITOR.value:
        return

    requester_hash = hash_user_id(claims.user_id) if claims else ""
    if requester_hash != audit.get("user_id_hash", ""):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this report.",
        )


@app.get("/healthz")
def healthz() -> dict[str, object]:
    service_checks = {
        "postgres": _check_postgres,
        "redis": _check_redis,
        "qdrant": _check_qdrant,
        "minio": _check_minio,
    }
    response: dict[str, object] = {"status": "ok", "workflow_nodes": NODE_COUNT}
    errors: dict[str, str] = {}

    for service_name, check in service_checks.items():
        try:
            check()
            response[service_name] = "ok"
        except Exception as exc:
            response[service_name] = "error"
            errors[service_name] = str(exc)

    if errors:
        response["status"] = "error"
        response["errors"] = errors
        raise HTTPException(status_code=503, detail=response)

    return response


def _check_postgres() -> None:
    _tcp_connect(settings.postgres_host, settings.postgres_port)


def _check_redis() -> None:
    redis_url = urlparse(settings.redis_url)
    if redis_url.scheme != "redis" or not redis_url.hostname:
        raise ValueError("REDIS_URL must be a redis:// URL with a hostname")

    port = redis_url.port or 6379
    with socket.create_connection((redis_url.hostname, port), timeout=2) as sock:
        sock.sendall(b"*1\r\n$4\r\nPING\r\n")
        if not sock.recv(16).startswith(b"+PONG"):
            raise ConnectionError("Redis PING did not return PONG")


def _check_qdrant() -> None:
    _http_ok(f"{settings.qdrant_url.rstrip('/')}/collections")


def _check_minio() -> None:
    endpoint = settings.minio_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    _http_ok(f"{endpoint.rstrip('/')}/minio/health/ready")


def _tcp_connect(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=2):
        return


def _http_ok(url: str) -> None:
    with urlopen(url, timeout=2) as response:
        if response.status >= 400:
            raise ConnectionError(f"{url} returned HTTP {response.status}")


def _derive_status(outputs: dict[str, object]) -> str:
    """Compute the response status from the workflow outputs.

    The skeleton workflow still has stubbed downstream nodes for Phase 1E onward,
    so we report ``in_progress`` while the quality gate is in its default
    ``needs_review`` state, ``failed`` when the gate hard-fails, and ``ready``
    only when an export was produced.
    """
    gate = outputs.get("quality_gate")
    if gate == "passed" and outputs.get("markdown_report_status") == "generated":
        return "ready"
    if gate == "failed":
        return "failed"
    return "in_progress"


@app.post("/reports/staging")
async def stage_report(
    request: ReportRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict[str, object]:
    user_id = (claims.user_id if claims and claims.user_id else None) or request.user_id
    role = claims.role if claims else None

    state = DecisionState(
        request_id=str(uuid.uuid4()),
        user_id=user_id,
        role=role,
        project_code=request.project_code,
        query=request.query,
        inputs=request.model_dump(exclude_none=True),
        output_formats=list(request.output_formats),
    )
    try:
        result = await run_workflow(state)
    except RbacDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    exports = result.outputs.get("exported_reports", {})
    return {
        "request_id": result.request_id,
        "status": _derive_status(result.outputs),
        "quality_gate": result.outputs.get("quality_gate", "needs_review"),
        "visited_nodes": result.visited_nodes,
        "exported_formats": list(exports.keys()),
        "exports": exports,
    }


# ---------------------------------------------------------------------------
# Phase 2A backend additions — Reports list / detail / status / cancel
# ---------------------------------------------------------------------------


@app.get("/reports", response_model=ReportListResponse)
async def list_reports(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    state: Annotated[str | None, Query()] = None,
    project_code: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportListResponse:
    """List the caller's reports.

    RBAC scope:
    - ``admin`` is rejected (admins never see business data; see
      ``docs/admin/CONTROL_PLANE_LOCK.md``).
    - ``auditor`` sees every project's reports (read-only).
    - All other roles see only their own ``user_id_hash`` requests.
    """
    claims = _require_claims(claims)
    role = _validated_role(claims)

    if role == Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to list reports.",
        )

    if role == Role.AUDITOR:
        scoped_user_hash: str | None = None  # all users
    else:
        if not claims.user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        scoped_user_hash = hash_user_id(claims.user_id)

    pg = get_postgres_store()
    await pg.init_schema()
    rows, total = await pg.list_audits(
        user_id_hash=scoped_user_hash,
        state=state,
        project_code=project_code,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    summaries: list[ReportSummary] = []
    for row in rows:
        summaries.append(
            ReportSummary(
                request_id=row["request_id"],
                project_code=row.get("project_code"),
                query_excerpt=_query_excerpt(row.get("query")),
                state=_derive_external_state(row),
                quality_gate=row.get("quality_gate_status"),
                requires_approval=bool(row.get("requires_approval", True)),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
        )
    return ReportListResponse(
        reports=summaries, total=total, limit=limit, offset=offset
    )


@app.get("/reports/{request_id}", response_model=ReportDetail)
async def get_report(
    request_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> ReportDetail:
    """Return metadata + review history for a single report.

    Per the locked UI contract, the report body is fetched via the existing
    download endpoints (`GET /reports/{staging,final}/{id}/download/{fmt}`).
    This endpoint deliberately omits raw business content (query text is
    included because it is the requester's own input, but evidence/excerpts
    are not).
    """
    claims = _require_claims(claims)

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    _check_can_read_own_report(claims, audit)

    decisions = await pg.get_review_decisions(request_id)
    review_views = [
        ReviewDecisionView(
            action=d.get("action", ""),
            reason=d.get("reason"),
            comment=d.get("comment"),
            created_at=d.get("created_at"),
        )
        for d in decisions
    ]

    return ReportDetail(
        request_id=audit["request_id"],
        project_code=audit.get("project_code"),
        query=audit.get("query"),
        state=_derive_external_state(audit),
        quality_gate=audit.get("quality_gate_status"),
        requires_approval=bool(audit.get("requires_approval", True)),
        created_at=audit.get("created_at"),
        updated_at=audit.get("updated_at"),
        exported_formats=_exported_formats(audit),
        review_decisions=review_views,
    )


@app.get("/reports/{request_id}/status", response_model=ReportStatusResponse)
async def get_report_status(
    request_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> ReportStatusResponse:
    """Return processing-state metadata for the Processing View polling loop.

    The workflow is synchronous today (``POST /reports/staging`` blocks until
    the graph completes), so any audit row already represents a terminal state.
    The response shape leaves room for an async runtime in a later phase
    (``current_node``, ``is_terminal``).
    """
    claims = _require_claims(claims)

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    _check_can_read_own_report(claims, audit)

    state = _derive_external_state(audit)
    return ReportStatusResponse(
        request_id=audit["request_id"],
        state=state,
        quality_gate=audit.get("quality_gate_status"),
        total_nodes=NODE_COUNT,
        # Synchronous runner: by the time an audit row exists, every node has
        # been executed. The Processing View can use this to stop polling.
        current_node=NODE_COUNT,
        is_terminal=True,
        updated_at=audit.get("updated_at"),
    )


@app.delete("/reports/{request_id}", response_model=CancelReportResponse)
async def cancel_report(
    request_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> CancelReportResponse:
    """Cancel a report request.

    Only the requester may cancel; reports in terminal states (final, rejected,
    cancelled) cannot be cancelled. Cancellation is a soft state change on the
    audit row plus a ``review_decisions`` entry — the audit trail is preserved.
    """
    claims = _require_claims(claims)

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Owner-only: requester must match. Auditor/admin cannot cancel another
    # user's report. In bypass mode skip the user-match check (consistent with
    # other endpoints).
    if settings.entra_client_id and settings.entra_tenant_id:
        if not claims.user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        requester_hash = hash_user_id(claims.user_id)
        if requester_hash != audit.get("user_id_hash", ""):
            raise HTTPException(
                status_code=403, detail="Only the requester can cancel this report."
            )

    current = _derive_external_state(audit)
    if current in {"final", "rejected", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"Report cannot be cancelled (current state: {current}).",
        )

    canceller_hash = (
        hash_user_id(claims.user_id) if claims.user_id else audit.get("user_id_hash", "")
    )
    await pg.insert_review_decision(
        request_id=request_id,
        reviewer_id_hash=canceller_hash,
        action="cancelled",
        reason="Cancelled by requester.",
    )
    await pg.update_review_state(request_id, "cancelled")

    return CancelReportResponse(request_id=request_id, state="cancelled")


# ---------------------------------------------------------------------------
# Phase 2A backend additions — Upload
# ---------------------------------------------------------------------------


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(raw: str) -> str:
    """Reduce a user-supplied filename to a safe basename.

    Strips directory components, normalises whitespace, and replaces unsafe
    characters with ``_``. Empty results fall back to ``upload``.
    """
    basename = os.path.basename(raw or "").strip()
    if not basename:
        return "upload"
    cleaned = _FILENAME_SAFE_RE.sub("_", basename)
    return cleaned or "upload"


def _validate_upload_type(filename: str, content_type: str | None) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext in _ACCEPTED_UPLOAD_EXTENSIONS:
        return
    if content_type and content_type.lower() in _ACCEPTED_UPLOAD_CONTENT_TYPES:
        return
    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported file type. Accepted: PDF, DOCX, XLSX, TXT, MSG, EML."
        ),
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    file: UploadFile = File(...),
) -> UploadResponse:
    """Accept a single attachment and persist it to MinIO under the user's
    upload prefix.

    Validates type (PDF/DOCX/XLSX/TXT/MSG/EML) and size (≤10 MB) to match the
    Phase 2A Upload Zone client-side rules. Returns a stable
    ``upload_id`` plus a SHA-256 of the bytes so callers can attach the file
    to a future query.
    """
    claims = _require_claims(claims)

    safe_name = _safe_filename(file.filename or "")
    _validate_upload_type(safe_name, file.content_type)

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    content_hash = hashlib.sha256(data).hexdigest()
    upload_id = str(uuid.uuid4())
    user_id_hash = (
        hash_user_id(claims.user_id) if claims.user_id else "anonymous"
    )

    minio = get_minio_store()
    minio.put_upload(
        user_id_hash=user_id_hash,
        upload_id=upload_id,
        filename=safe_name,
        data=data,
        content_type=file.content_type or "application/octet-stream",
    )

    return UploadResponse(
        upload_id=upload_id,
        filename=safe_name,
        size=len(data),
        content_type=file.content_type or "application/octet-stream",
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# Review endpoints
# ---------------------------------------------------------------------------


@app.post("/reports/staging/{request_id}/approve")
async def approve_report(
    request_id: str,
    body: ApproveRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict[str, object]:
    """Approve a staged report.

    Normal reviewers with can_approve=True may approve.
    Admin may use metadata-only override with a mandatory comment.
    Auditor is blocked. Self-approval is blocked.
    """
    claims = _require_claims(claims)
    action = _check_reviewer_rbac(claims)

    if action == "admin_override" and (not body.comment or not body.comment.strip()):
        raise HTTPException(status_code=400, detail="Admin override requires a mandatory comment.")

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Block self-approval
    reviewer_hash = hash_user_id(claims.user_id)
    if reviewer_hash == audit.get("user_id_hash", ""):
        raise HTTPException(status_code=403, detail="Self-approval is not allowed.")

    # Block if already finalized or rejected
    current_state = audit.get("review_state", "staging")
    if current_state == "final":
        raise HTTPException(status_code=409, detail="Report is already finalized.")
    if current_state == "rejected":
        raise HTTPException(status_code=409, detail="Report has been rejected.")

    await pg.insert_review_decision(
        request_id=request_id,
        reviewer_id_hash=reviewer_hash,
        action=action,
        comment=body.comment,
    )
    await pg.update_review_state(request_id, "approved")

    return {"request_id": request_id, "action": action, "new_state": "approved"}


@app.post("/reports/staging/{request_id}/reject")
async def reject_report(
    request_id: str,
    body: RejectRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict[str, object]:
    """Reject a staged report. Requires a reason."""
    claims = _require_claims(claims)
    action = _check_reviewer_rbac(claims)

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Block self-rejection (treat as self-approval blocking)
    reviewer_hash = hash_user_id(claims.user_id)
    if reviewer_hash == audit.get("user_id_hash", ""):
        raise HTTPException(status_code=403, detail="Self-rejection is not allowed.")

    current_state = audit.get("review_state", "staging")
    if current_state == "final":
        raise HTTPException(status_code=409, detail="Report is already finalized.")

    await pg.insert_review_decision(
        request_id=request_id,
        reviewer_id_hash=reviewer_hash,
        action=action,
        reason=body.reason,
    )
    await pg.update_review_state(request_id, "rejected")

    return {"request_id": request_id, "action": "reject", "new_state": "rejected"}


@app.post("/reports/staging/{request_id}/request-revision")
async def request_revision(
    request_id: str,
    body: RequestRevisionRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict[str, object]:
    """Request revision for a staged report. Requires a reason/comment."""
    claims = _require_claims(claims)
    action = _check_reviewer_rbac(claims)

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    reviewer_hash = hash_user_id(claims.user_id)
    if reviewer_hash == audit.get("user_id_hash", ""):
        raise HTTPException(status_code=403, detail="Self-revision-request is not allowed.")

    current_state = audit.get("review_state", "staging")
    if current_state == "final":
        raise HTTPException(status_code=409, detail="Report is already finalized.")

    await pg.insert_review_decision(
        request_id=request_id,
        reviewer_id_hash=reviewer_hash,
        action=action,
        reason=body.reason,
        comment=body.comment,
    )
    await pg.update_review_state(request_id, "revision_requested")

    return {"request_id": request_id, "action": "request_revision", "new_state": "revision_requested"}


# ---------------------------------------------------------------------------
# Download endpoints
# ---------------------------------------------------------------------------


async def _download_artifact(
    request_id: str,
    fmt: str,
    claims: JWTClaims | None,
    prefix: str,
    allow_before_approval: bool = False,
) -> Response:
    """Shared download logic for staging and final prefixes."""
    if fmt not in MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}")

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Quality gate blocking (all paths)
    quality_gate_status = audit.get("quality_gate_status", "needs_review")
    if quality_gate_status == "failed":
        raise HTTPException(
            status_code=403,
            detail="Download blocked: quality gate failed.",
        )

    # Authorization (skip in bypass mode)
    if settings.entra_client_id and settings.entra_tenant_id:
        if claims is None or not claims.user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")

        requester_hash = hash_user_id(claims.user_id)
        stored_hash = audit.get("user_id_hash", "")
        role = claims.role

        # Admin and auditor can access metadata but admin cannot view report content.
        # For downloads, we allow admin/auditor on staging; on final we also allow.
        allowed = requester_hash == stored_hash or role in (
            Role.ADMIN.value,
            Role.AUDITOR.value,
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this report.",
            )

    review_state = audit.get("review_state", "staging")
    requires_approval = audit.get("requires_approval", True)

    # Staging download blocking before approval (for approval-required reports)
    if prefix == "staging" and requires_approval and review_state not in ("approved", "final"):
        raise HTTPException(
            status_code=403,
            detail="Download blocked: report awaiting approval.",
        )

    # Final download only after finalization
    if prefix == "final" and review_state != "final":
        raise HTTPException(
            status_code=403,
            detail="Download blocked: report not yet finalized.",
        )

    minio = get_minio_store()
    filename = f"executive-decision-report.{fmt}"
    try:
        data = minio.get_object(request_id, filename, prefix=prefix)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {exc}")

    return Response(
        content=data,
        media_type=MIME_TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/reports/staging/{request_id}/download/{fmt}")
async def download_report(
    request_id: str,
    fmt: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> Response:
    """Download a specific format of a staged report from MinIO."""
    return await _download_artifact(request_id, fmt, claims, prefix="staging")


@app.get("/reports/final/{request_id}/download/{fmt}")
async def download_final_report(
    request_id: str,
    fmt: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> Response:
    """Download a specific format of a finalized report from MinIO."""
    return await _download_artifact(request_id, fmt, claims, prefix="final")
