import hashlib
import json
import os
import re
import socket
import time
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
from apps.edr.exporters.markdown import to_markdown
from apps.edr.graph.runner import NODE_COUNT, run_workflow
from apps.edr.graph.state import DecisionState
from apps.edr.graph import node_17_publish
from apps.edr.persistence import get_minio_store, get_postgres_store, hash_user_id
from apps.edr.admin import services_catalog
from apps.edr.rbac.project_mapping import ProjectMapping, RbacDeniedError
from apps.edr.rbac.roles import ROLE_PERMISSIONS, VALID_ROLES, Role

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


class WorkspaceProject(BaseModel):
    project_code: str
    contract_numbers: list[str] = Field(default_factory=list)


class WorkspaceContextResponse(BaseModel):
    user_id: str
    role: str
    allowed_projects: list[WorkspaceProject]
    can_generate_report: bool
    can_approve: bool
    can_access_odoo_budget: bool


class EvidencePanelEntry(BaseModel):
    evidence_id: str
    citation_label: str
    source_type: str
    title: str
    confidence: str
    hash_sha256: str
    hash_short: str
    excerpt: str
    source_uri: str
    timestamp: str | None = None


class ReportContentResponse(BaseModel):
    request_id: str
    project_code: str | None
    query: str | None
    state: str
    quality_gate: str | None
    requires_approval: bool
    markdown: str | None = None
    evidence: list[EvidencePanelEntry] = Field(default_factory=list)
    quality_gate_flags: list[str] = Field(default_factory=list)
    content_available: bool
    content_unavailable_reason: str | None = None
    can_review: bool
    is_requester: bool
    immutable: bool


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
    x_user_id: Annotated[str | None, Header()] = None,
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
    return JWTClaims(user_id=x_user_id or "", role=x_user_role)


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


def _role_permissions(role: Role):
    return ROLE_PERMISSIONS[role]


def _require_admin(claims: JWTClaims | None) -> JWTClaims:
    """Authorise the caller as ``admin`` for every ``/admin/*`` endpoint.

    Returns the validated ``JWTClaims`` on success. Raises ``HTTPException``
    with the matching status code on failure:

    - 401 when ``claims`` is ``None`` (production mode without a token).
    - 403 when the role is missing, not a canonical role, or not ``admin``.

    Phase 2B Slice 1: this helper is the shared gate that every admin
    endpoint added in subsequent slices will use. UI client guards in
    ``frontend/src/routing/guards.ts`` are cosmetic; this is authoritative.
    """
    claims = _require_claims(claims)
    role_enum = _validated_role(claims)
    if role_enum != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required.")
    return claims


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


def _is_requester(claims: JWTClaims, audit: dict[str, Any]) -> bool:
    if not claims.user_id:
        return False
    return hash_user_id(claims.user_id) == audit.get("user_id_hash", "")


def _can_review_report(claims: JWTClaims, audit: dict[str, Any]) -> bool:
    try:
        role = _validated_role(claims)
    except HTTPException:
        return False
    if role in (Role.ADMIN, Role.AUDITOR):
        return False
    perms = _role_permissions(role)
    if not perms.can_approve:
        return False
    return not _is_requester(claims, audit)


def _check_can_read_report_content(claims: JWTClaims, audit: dict[str, Any]) -> None:
    role = _validated_role(claims)
    if role == Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to view report content.",
        )

    if not (settings.entra_client_id and settings.entra_tenant_id):
        return

    if _is_requester(claims, audit) or role == Role.AUDITOR or _can_review_report(claims, audit):
        return

    raise HTTPException(status_code=403, detail="Not authorized to access this report.")


def _load_json_artifact(request_id: str, filename: str, prefix: str) -> dict[str, Any]:
    minio = get_minio_store()
    try:
        raw = minio.get_object(request_id, filename, prefix=prefix)
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_text_artifact(request_id: str, filename: str, prefix: str) -> str | None:
    minio = get_minio_store()
    try:
        return minio.get_object(request_id, filename, prefix=prefix).decode("utf-8")
    except Exception:
        return None


def _quality_gate_flags(qg_result: dict[str, Any]) -> list[str]:
    checks = qg_result.get("checks")
    if not isinstance(checks, list):
        return []
    flags: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        verdict = check.get("verdict")
        if verdict == "supported":
            continue
        reason = check.get("reason") or check.get("claim_id") or "Quality gate flag"
        flags.append(str(reason))
    return flags


def _evidence_entries(evidence_pack: dict[str, Any]) -> list[EvidencePanelEntry]:
    raw_evidence = evidence_pack.get("evidence")
    if not isinstance(raw_evidence, list):
        return []
    entries: list[EvidencePanelEntry] = []
    for idx, item in enumerate(raw_evidence, start=1):
        if not isinstance(item, dict):
            continue
        full_hash = str(item.get("hash_sha256") or "")
        entries.append(
            EvidencePanelEntry(
                evidence_id=str(item.get("evidence_id") or ""),
                citation_label=str(idx),
                source_type=str(item.get("source_type") or "unknown"),
                title=str(item.get("title") or "Untitled evidence"),
                confidence=str(item.get("confidence") or "unknown"),
                hash_sha256=full_hash,
                hash_short=full_hash[-8:] if len(full_hash) >= 8 else full_hash,
                excerpt=str(item.get("excerpt") or ""),
                source_uri=str(item.get("source_uri") or ""),
                timestamp=item.get("timestamp") if isinstance(item.get("timestamp"), str) else None,
            )
        )
    return entries


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

    # A-20: block if source_mappings table is seeded and project has no complete mapping
    if request.project_code:
        try:
            _pg = get_postgres_store()
            await _pg.init_schema()
            _all = await _pg.list_source_mappings()
            if _all:  # table is seeded — enforce the mapping constraint
                _row = await _pg.get_source_mapping(request.project_code)
                if _row is None or _row.get("mapping_status") != "complete":
                    raise HTTPException(
                        status_code=422,
                        detail=f"Project {request.project_code!r} has no complete source mapping. "
                               "Configure it in the Source Mapping admin screen.",
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # DB unavailable — allow through; production will fail at retrieval

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


@app.get("/workspace/context", response_model=WorkspaceContextResponse)
async def get_workspace_context(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> WorkspaceContextResponse:
    """Return the role-scoped workspace context used by the Phase 2A UI."""
    claims = _require_claims(claims)
    role = _validated_role(claims)
    if role == Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to access the user workspace.",
        )
    perms = _role_permissions(role)

    projects: list[WorkspaceProject] = []
    if perms.can_generate_report:
        mapping = ProjectMapping.load()
        projects = [
            WorkspaceProject(
                project_code=str(entry.get("project_code", "")),
                contract_numbers=list(entry.get("contract_numbers", [])),
            )
            for entry in mapping.all_projects()
        ]

    return WorkspaceContextResponse(
        user_id=claims.user_id,
        role=role.value,
        allowed_projects=projects,
        can_generate_report=perms.can_generate_report,
        can_approve=perms.can_approve,
        can_access_odoo_budget=perms.can_access_odoo_budget,
    )


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


@app.get("/reports/{request_id}/content", response_model=ReportContentResponse)
async def get_report_content(
    request_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> ReportContentResponse:
    """Return report content and evidence for the Phase 2A Report View.

    Requesters whose reports need mandatory review receive quality-gate flags
    only. Reviewers can inspect the staged draft, but export/download remains
    blocked until approval/finalization by the existing download endpoints.
    """
    claims = _require_claims(claims)

    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    _check_can_read_report_content(claims, audit)

    state = _derive_external_state(audit)
    prefix = "final" if state == "final" else "staging"
    qg_result = _load_json_artifact(request_id, "quality-gate-result.json", prefix)
    flags = _quality_gate_flags(qg_result)
    evidence_pack = _load_json_artifact(request_id, "evidence-pack.json", prefix)
    evidence = _evidence_entries(evidence_pack)

    is_requester = _is_requester(claims, audit)
    can_review = _can_review_report(claims, audit) and state in {"staging", "needs_review"}
    markdown: str | None = None
    unavailable_reason: str | None = None

    if audit.get("quality_gate_status") == "failed":
        unavailable_reason = "Download blocked: quality gate failed."
    elif state == "needs_review" and is_requester:
        unavailable_reason = "Report content is hidden until reviewer approval."
    else:
        markdown = _load_text_artifact(
            request_id,
            "executive-decision-report.md",
            prefix,
        )
        if not markdown or markdown.startswith("# No Report Generated"):
            draft = _load_json_artifact(request_id, "report-draft.json", prefix)
            if draft:
                markdown = to_markdown(draft)
        if not markdown:
            unavailable_reason = "Report content is not available."

    content_available = markdown is not None and unavailable_reason is None
    if not content_available and not can_review:
        evidence = []

    return ReportContentResponse(
        request_id=audit["request_id"],
        project_code=audit.get("project_code"),
        query=audit.get("query"),
        state=state,
        quality_gate=audit.get("quality_gate_status"),
        requires_approval=bool(audit.get("requires_approval", True)),
        markdown=markdown if content_available else None,
        evidence=evidence if content_available or can_review else [],
        quality_gate_flags=flags,
        content_available=content_available,
        content_unavailable_reason=unavailable_reason,
        can_review=can_review,
        is_requester=is_requester,
        immutable=state == "final",
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
    if claims.role == Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to cancel workspace reports.",
        )

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
        action="report.cancelled",
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
    if ext:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Accepted: PDF, DOCX, XLSX, TXT, MSG, EML."
            ),
        )
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
    if claims.role == Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to upload workspace files.",
        )

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

    publish_state = await node_17_publish.run(
        DecisionState(
            request_id=request_id,
            user_id=claims.user_id,
            role=claims.role,
            project_code=audit.get("project_code"),
            query=audit.get("query") or "",
        )
    )

    return {
        "request_id": request_id,
        "action": action,
        "new_state": "approved",
        "publish_status": publish_state.outputs.get("publish_status"),
    }


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
    if claims and claims.role == Role.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Admin role is not authorized to download report content.",
        )

    # Authorization (skip in bypass mode)
    if settings.entra_client_id and settings.entra_tenant_id:
        if claims is None or not claims.user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")

        requester_hash = hash_user_id(claims.user_id)
        stored_hash = audit.get("user_id_hash", "")
        role = claims.role

        # Auditor can access read-only report content; admin remains metadata-only.
        allowed = requester_hash == stored_hash or role == Role.AUDITOR.value
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


# ---------------------------------------------------------------------------
# Phase 2B Slice 1 — Admin RBAC base
#
# Self-test endpoint that exercises ``_require_admin`` end-to-end. Used by
# integration tests in ``apps/edr/tests/integration/test_phase2b_admin_rbac.py``
# and by future ops smoke probes. It returns no business data and no
# credential values; it confirms only that the caller is authenticated as
# ``admin``.
# ---------------------------------------------------------------------------


@app.get("/admin/_authcheck")
async def admin_authcheck(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict[str, object]:
    """Return ``{\"ok\": true, \"role\": \"admin\"}`` when the caller is admin.

    Returns 403 for every other canonical role and 403/401 for missing/invalid
    role or claims. No business-data fields are returned.
    """
    claims = _require_admin(claims)
    return {"ok": True, "role": claims.role}


# ---------------------------------------------------------------------------
# Phase 2B Slice 2 — Connectors & APIs (read + probe)
# Implements GET /admin/services, GET /admin/services/{name}, and
# POST /admin/services/{name}/probe per docs/execution/PHASE_2B_PLAN.md §E
# row 2. Admin-only via the shared ``_require_admin`` gate added in Slice 1.
# ---------------------------------------------------------------------------


def _service_or_404(name: str) -> services_catalog.ServiceDef:
    service = services_catalog.SERVICE_REGISTRY.get(name)
    if service is None:
        raise HTTPException(status_code=404, detail=f"Unknown service: {name}")
    return service


def _format_event_view(row: dict) -> services_catalog.ConnectorEventView:
    ts = row.get("ts")
    return services_catalog.ConnectorEventView(
        ts=ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else "",
        event_type=row["event_type"],
        latency_ms=row.get("latency_ms"),
        status_code=row.get("status_code"),
        detail=services_catalog._sanitize_detail(row.get("detail") or ""),
    )


def _summary_from(
    service: services_catalog.ServiceDef,
    latest: dict | None,
) -> services_catalog.ServiceSummary:
    last_probe_status: str = "unknown"
    last_probe_at: str | None = None
    last_latency_ms: int | None = None
    if latest is not None:
        event_type = latest.get("event_type")
        if event_type == "connector.probe_success":
            last_probe_status = "pass"
        elif event_type == "connector.error":
            last_probe_status = "fail"
        elif event_type == "connector.latency_spike":
            last_probe_status = "pass"
        ts = latest.get("ts")
        last_probe_at = (
            ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else None
        )
        last_latency_ms = latest.get("latency_ms")
    return services_catalog.ServiceSummary(
        name=service.name,
        display_name=service.display_name,
        category=service.category,
        auth_mechanism=service.auth_mechanism,
        hostname=service.hostname_source(),
        last_probe_status=last_probe_status,  # type: ignore[arg-type]
        last_probe_at=last_probe_at,
        last_latency_ms=last_latency_ms,
        workflow_status=services_catalog.workflow_status_for(service),
    )


@app.get("/admin/services")
async def list_admin_services(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> list[services_catalog.ServiceSummary]:
    """Admin-only service list with per-service status pills.

    No credential values are returned — only key-presence is exposed via the
    detail endpoint. Workflow status (``empty``/``deployed``) is computed
    from the local n8n JSON files (A-05).
    """
    _require_admin(claims)
    store = get_postgres_store()
    try:
        latest = await store.latest_connector_event_per_service()
    except Exception:
        latest = {}
    return [
        _summary_from(service, latest.get(service.name))
        for service in services_catalog.SERVICE_REGISTRY.values()
    ]


@app.get("/admin/services/{name}")
async def get_admin_service(
    name: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> services_catalog.ServiceDetail:
    """Admin-only service detail: env-key presence, last probe summary,
    workflow node count (A-05), and recent events."""
    _require_admin(claims)
    service = _service_or_404(name)
    store = get_postgres_store()
    try:
        latest_per = await store.latest_connector_event_per_service()
    except Exception:
        latest_per = {}
    try:
        events = await store.recent_connector_events(name, limit=10)
    except Exception:
        events = []
    summary = _summary_from(service, latest_per.get(name))
    return services_catalog.ServiceDetail(
        **summary.model_dump(),
        description=service.description,
        env_keys=services_catalog.env_key_statuses(service),
        workflow_node_count=services_catalog.workflow_node_count(service),
        recent_events=[_format_event_view(row) for row in events],
    )


@app.post("/admin/services/{name}/probe")
async def probe_admin_service(
    name: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> services_catalog.ProbeResult:
    """Admin-only read-only probe.

    Behaviour:
    - On success: writes one ``connector.probe_success`` event.
    - On failure: writes one ``connector.error`` event; the HTTP response is
      still 200 with ``status="fail"`` — pass/fail is in-band, like a
      browser ``Test connection`` button (A-04).
    - On latency >= ``LATENCY_SPIKE_THRESHOLD_MS``: writes a *second*
      ``connector.latency_spike`` row in addition to the pass/fail row.

    Event rows are written **before** the response is constructed, per
    PHASE_2B_PLAN §C.6 "audit-before-side-effect" rule.
    """
    _require_admin(claims)
    service = _service_or_404(name)
    outcome = services_catalog.run_probe(service)

    primary_event = (
        "connector.probe_success" if outcome.status == "pass" else "connector.error"
    )
    store = get_postgres_store()
    await store.insert_connector_event(
        service=name,
        event_type=primary_event,
        latency_ms=outcome.latency_ms,
        status_code=outcome.status_code,
        detail=services_catalog._sanitize_detail(
            outcome.detail, hostname=service.hostname_source()
        ),
    )
    if outcome.latency_ms >= services_catalog.LATENCY_SPIKE_THRESHOLD_MS:
        await store.insert_connector_event(
            service=name,
            event_type="connector.latency_spike",
            latency_ms=outcome.latency_ms,
            status_code=outcome.status_code,
            detail=services_catalog._sanitize_detail(
                f"latency_spike@{service.hostname_source() or service.name}"
            ),
        )

    return services_catalog.ProbeResult(
        service=name,
        status=outcome.status,
        latency_ms=outcome.latency_ms,
        status_code=outcome.status_code,
        detail=outcome.detail,
        probed_at=services_catalog.now_iso(),
    )


# ---------------------------------------------------------------------------
# Phase 2B Slice 3 — System Health + cost monitor
# Implements GET /admin/health/live and GET /admin/cost per
# docs/execution/PHASE_2B_PLAN.md §E row 3. Admin-only via _require_admin.
# ---------------------------------------------------------------------------


class HealthServiceStatus(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    display_name: str
    status: Literal["ok", "error", "unknown"]
    latency_ms: int
    sla_ms: int
    sparkline_24h: list[int]


class HealthLiveResponse(BaseModel):
    model_config = {"extra": "forbid"}

    services: list[HealthServiceStatus]
    checked_at: str


class LlmBreakdownItem(BaseModel):
    model_config = {"extra": "forbid"}

    model: str
    calls: int
    cost_usd: float


class CostResponse(BaseModel):
    model_config = {"extra": "forbid"}

    daily_cost: float
    daily_cap: float
    daily_percent: float
    monthly_cost: float
    monthly_cap: float
    monthly_percent: float
    llm_breakdown: list[LlmBreakdownItem]
    warning: bool
    exceeded: bool


#: SLA targets in milliseconds for each service surfaced in System Health.
#  Workflow services share the n8n/webhook SLA. Values are aligned with the
#  UI contract §3.7 and the connector probe timeout budget.
_HEALTH_SLA_MS: dict[str, int] = {
    "postgres": 200,
    "redis": 100,
    "qdrant": 300,
    "minio": 500,
    "n8n": 500,
    "sharepoint": 1000,
    "microsoft_graph": 1000,
    "owncloud": 500,
    "odoo": 500,
    "langfuse": 500,
}


def _probe_with_latency(name: str) -> tuple[str, int]:
    """Run the registered health check for *name* and return (status, latency_ms).

    Infrastructure services reuse the existing ``_check_*`` helpers.
    Workflow services are probed via n8n reachability (same as Slice 2).
    """
    check_map = {
        "postgres": _check_postgres,
        "redis": _check_redis,
        "qdrant": _check_qdrant,
        "minio": _check_minio,
        "n8n": lambda: _http_ok(
            f"{settings.n8n_base_url.rstrip('/')}/healthz"
        ),
        "langfuse": lambda: _http_ok(
            f"{settings.langfuse_host.rstrip('/')}/api/public/health"
        ),
    }
    # Workflow services: probe n8n base URL (same lightweight check)
    for wf_name in ("sharepoint", "microsoft_graph", "owncloud", "odoo"):
        check_map[wf_name] = check_map["n8n"]

    check = check_map.get(name)
    if check is None:
        return ("unknown", 0)

    t0 = time.monotonic()
    try:
        check()
        status = "ok"
    except Exception:
        status = "error"
    latency_ms = int((time.monotonic() - t0) * 1000)
    return (status, latency_ms)


@app.get("/admin/health/live")
async def admin_health_live(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> HealthLiveResponse:
    """Admin-only live health status with per-service latency and 24h sparkline.

    Returns no business data (C-1) and no credential values (C-6).
    """
    _require_admin(claims)
    store = get_postgres_store()
    services: list[HealthServiceStatus] = []

    for name in services_catalog.SERVICE_REGISTRY.keys():
        status, latency_ms = _probe_with_latency(name)
        sla_ms = _HEALTH_SLA_MS.get(name, 500)

        # Fetch 24h sparkline buckets (up to 24 hourly averages)
        sparkline: list[int] = []
        try:
            buckets = await store.connector_events_24h_buckets(name)
            sparkline = [int(b.get("avg_latency_ms", 0)) for b in buckets]
        except Exception:
            sparkline = []

        services.append(
            HealthServiceStatus(
                name=name,
                display_name=services_catalog.SERVICE_REGISTRY[name].display_name,
                status=status,  # type: ignore[arg-type]
                latency_ms=latency_ms,
                sla_ms=sla_ms,
                sparkline_24h=sparkline,
            )
        )

    return HealthLiveResponse(
        services=services,
        checked_at=datetime.now().isoformat(),
    )


@app.get("/admin/cost")
async def admin_cost(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> CostResponse:
    """Admin-only cost monitor: daily / monthly caps, LLM breakdown, warnings.

    Emits ``cost.daily_cap_warning`` or ``cost.daily_cap_exceeded`` events
    when thresholds are crossed.  No business content (C-1); no credentials
    (C-6).
    """
    _require_admin(claims)

    from apps.edr.llm import _cost_tracker

    daily_cost = _cost_tracker.daily_cost
    daily_cap = settings.daily_cost_cap_usd
    daily_percent = round((daily_cost / daily_cap * 100), 2) if daily_cap > 0 else 0.0

    store = get_postgres_store()
    try:
        monthly_cost = await store.monthly_cost_aggregate()
    except Exception:
        monthly_cost = 0.0
    monthly_cap = settings.monthly_cost_target_usd
    monthly_percent = (
        round((monthly_cost / monthly_cap * 100), 2) if monthly_cap > 0 else 0.0
    )

    llm_breakdown = [
        LlmBreakdownItem(
            model=item["model"],
            calls=item["calls"],
            cost_usd=item["cost_usd"],
        )
        for item in _cost_tracker.get_model_breakdown()
    ]

    warning = daily_cost >= daily_cap * 0.8
    exceeded = daily_cost >= daily_cap

    # Emit threshold events (idempotent-ish: we emit on every poll when
    # threshold is active; the audit read-model in Slice 4 will dedupe
    # if needed).
    if exceeded:
        try:
            await store.insert_cost_event(
                "cost.daily_cap_exceeded",
                f"daily_cost={daily_cost:.4f} cap={daily_cap:.2f}",
            )
        except Exception:
            pass
    elif warning:
        try:
            await store.insert_cost_event(
                "cost.daily_cap_warning",
                f"daily_cost={daily_cost:.4f} cap={daily_cap:.2f}",
            )
        except Exception:
            pass

    return CostResponse(
        daily_cost=round(daily_cost, 4),
        daily_cap=daily_cap,
        daily_percent=daily_percent,
        monthly_cost=round(monthly_cost, 4),
        monthly_cap=monthly_cap,
        monthly_percent=monthly_percent,
        llm_breakdown=llm_breakdown,
        warning=warning,
        exceeded=exceeded,
    )


# ---------------------------------------------------------------------------
# Phase 2B Slice 4 — Audit Log screen
# Implements GET /admin/audit, GET /admin/audit/export.csv, and
# GET /admin/audit/{event_id} per docs/execution/PHASE_2B_PLAN.md §E row 4.
# Admin-only via _require_admin.  C-1 / C-6 compliant.
# ---------------------------------------------------------------------------


class AuditEventSummary(BaseModel):
    model_config = {"extra": "forbid"}

    event_id: str
    event_type: str
    ts: str
    user_id_hash: str | None
    project_code: str | None
    service: str | None
    detail: str


class AuditEventDetail(AuditEventSummary):
    pass


class AuditEventListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    events: list[AuditEventSummary]
    total: int
    limit: int
    offset: int


@app.get("/admin/audit")
async def list_admin_audit(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditEventListResponse:
    """Admin-only paginated audit log over all event tables.

    Filters: date_from, date_to, event_type.  Hard limit ≤ 200.
    No business content (C-1); no credentials (C-6).
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    rows, total = await pg.list_audit_events(
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    events = [
        AuditEventSummary(
            event_id=str(r["event_id"]),
            event_type=str(r["event_type"]),
            ts=r["ts"].isoformat() if isinstance(r["ts"], datetime) else str(r["ts"]),
            user_id_hash=r.get("user_id_hash"),
            project_code=r.get("project_code"),
            service=r.get("service"),
            detail=str(r.get("detail", "")),
        )
        for r in rows
    ]
    return AuditEventListResponse(
        events=events,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/admin/audit/export.csv")
async def export_admin_audit_csv(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
) -> Response:
    """Admin-only CSV export of up to 200 audit events."""
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    rows, _total = await pg.list_audit_events(
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        limit=200,
        offset=0,
    )
    lines = ["event_id,event_type,ts,user_id_hash,project_code,service,detail"]
    for r in rows:
        ts = r["ts"].isoformat() if isinstance(r["ts"], datetime) else str(r["ts"])
        lines.append(
            ",".join(
                [
                    _csv_escape(str(r["event_id"])),
                    _csv_escape(str(r["event_type"])),
                    _csv_escape(ts),
                    _csv_escape(str(r.get("user_id_hash") or "")),
                    _csv_escape(str(r.get("project_code") or "")),
                    _csv_escape(str(r.get("service") or "")),
                    _csv_escape(str(r.get("detail", ""))),
                ]
            )
        )
    csv_text = "\n".join(lines) + "\n"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )


def _csv_escape(value: str) -> str:
    """Escape a string for safe inclusion in CSV."""
    if "," in value or '"' in value or "\n" in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def _ts_iso(ts: datetime | Any) -> str:
    """Normalise a timestamp to ISO-8601 string."""
    return ts.isoformat() if isinstance(ts, datetime) else str(ts)


@app.get("/admin/audit/{event_id}")
async def get_admin_audit_event(
    event_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> AuditEventDetail:
    """Admin-only single event detail by composite event_id."""
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    row = await pg.get_audit_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return AuditEventDetail(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        ts=row["ts"].isoformat() if isinstance(row["ts"], datetime) else str(row["ts"]),
        user_id_hash=row.get("user_id_hash"),
        project_code=row.get("project_code"),
        service=row.get("service"),
        detail=str(row.get("detail", "")),
    )


# ---------------------------------------------------------------------------
# Phase 2B Slice 6 — Project Source Mapping
# Implements GET /admin/source-mappings, GET /admin/source-mappings/{code},
# POST /admin/source-mappings/{code}/validate, PUT /admin/source-mappings/{code},
# POST /admin/source-mappings/{code}/disable per docs/execution/PHASE_2B_PLAN.md §E row 6.
# Admin-only via _require_admin.  C-1 / C-6 compliant.  A-21 audit-before-save.
# ---------------------------------------------------------------------------


class SourceMappingSharePoint(BaseModel):
    model_config = {"extra": "forbid"}
    site_id: str = ""
    drive_id: str = ""
    root_path: str = ""


class SourceMappingOwnCloud(BaseModel):
    model_config = {"extra": "forbid"}
    base_path: str = ""


class SourceMappingEmail(BaseModel):
    model_config = {"extra": "forbid"}
    shared_mailboxes: list[str] = []
    document_control_mailbox: str = ""
    client_domains: list[str] = []
    consultant_domains: list[str] = []
    contractor_domains: list[str] = []


class SourceMappingOdoo(BaseModel):
    model_config = {"extra": "forbid"}
    project_model: str = ""
    cost_model: str = ""
    project_external_id: str = ""
    project_name: str = ""


class RelatedPeople(BaseModel):
    model_config = {"extra": "forbid"}
    project_manager: str = ""
    commercial_manager: str = ""
    finance_owner: str = ""
    document_controller: str = ""
    other: list[str] = []


class SourceMappingSummary(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    project_name: str
    mapping_status: str
    contract_numbers: list[str]


class SourceMappingDetail(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    project_name: str
    contract_numbers: list[str]
    sharepoint: SourceMappingSharePoint
    owncloud: SourceMappingOwnCloud
    email: SourceMappingEmail
    odoo: SourceMappingOdoo
    related_people: RelatedPeople
    enabled_sources: list[str]
    allowed_roles: list[str]
    mapping_status: str
    last_validation_result: dict[str, Any] | None = None
    last_validated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    created_by_hash: str | None = None
    updated_by_hash: str | None = None


class SourceMappingListResponse(BaseModel):
    model_config = {"extra": "forbid"}
    mappings: list[SourceMappingSummary]


class SourceMappingUpsertRequest(BaseModel):
    model_config = {"extra": "forbid"}
    project_name: str = Field(default="", min_length=0)
    contract_numbers: list[str] = []
    sharepoint: SourceMappingSharePoint = Field(default_factory=SourceMappingSharePoint)
    owncloud: SourceMappingOwnCloud = Field(default_factory=SourceMappingOwnCloud)
    email: SourceMappingEmail = Field(default_factory=SourceMappingEmail)
    odoo: SourceMappingOdoo = Field(default_factory=SourceMappingOdoo)
    related_people: RelatedPeople = Field(default_factory=RelatedPeople)
    enabled_sources: list[str] = []
    allowed_roles: list[str] = []


class ValidationFieldError(BaseModel):
    model_config = {"extra": "forbid"}
    field: str
    message: str


class SourceMappingValidateResponse(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    valid: bool
    status: str
    errors: list[ValidationFieldError]


def _compute_mapping_status(
    code: str, body: SourceMappingUpsertRequest
) -> tuple[str, list[ValidationFieldError]]:
    """Pure function: returns (status, errors). status ∈ {'complete', 'incomplete'}."""
    errors: list[ValidationFieldError] = []
    enabled = set(body.enabled_sources)

    if "sharepoint" in enabled:
        if not body.sharepoint.site_id:
            errors.append(ValidationFieldError(field="sharepoint.site_id", message="Required for SharePoint source"))
        if not body.sharepoint.drive_id:
            errors.append(ValidationFieldError(field="sharepoint.drive_id", message="Required for SharePoint source"))
        if not body.sharepoint.root_path:
            errors.append(ValidationFieldError(field="sharepoint.root_path", message="Required for SharePoint source"))

    if "owncloud" in enabled:
        if not body.owncloud.base_path:
            errors.append(ValidationFieldError(field="owncloud.base_path", message="Required for ownCloud source"))

    if "email" in enabled:
        if not body.email.shared_mailboxes and not body.email.client_domains:
            errors.append(ValidationFieldError(
                field="email.shared_mailboxes",
                message="At least one mailbox or client domain required for Email source",
            ))

    if "odoo" in enabled:
        if not body.odoo.project_external_id and not body.odoo.project_name:
            errors.append(ValidationFieldError(
                field="odoo.project_external_id",
                message="Odoo project external ID or project name required",
            ))

    status = "complete" if not errors else "incomplete"
    return status, errors


def _row_to_source_mapping_detail(row: dict[str, Any]) -> SourceMappingDetail:
    import json as _json

    def _j(val: Any) -> Any:
        return _json.loads(val) if isinstance(val, str) else (val or {})

    def _jlist(val: Any) -> list:
        parsed = _json.loads(val) if isinstance(val, str) else (val or [])
        return parsed if isinstance(parsed, list) else []

    sp = _j(row.get("sharepoint"))
    oc = _j(row.get("owncloud"))
    em = _j(row.get("email"))
    od = _j(row.get("odoo"))
    rp = _j(row.get("related_people"))

    return SourceMappingDetail(
        project_code=str(row["project_code"]),
        project_name=str(row.get("project_name") or ""),
        contract_numbers=_jlist(row.get("contract_numbers")),
        sharepoint=SourceMappingSharePoint(
            site_id=sp.get("site_id", ""),
            drive_id=sp.get("drive_id", ""),
            root_path=sp.get("root_path", ""),
        ),
        owncloud=SourceMappingOwnCloud(base_path=oc.get("base_path", "")),
        email=SourceMappingEmail(
            shared_mailboxes=em.get("shared_mailboxes", []),
            document_control_mailbox=em.get("document_control_mailbox", ""),
            client_domains=em.get("client_domains", []),
            consultant_domains=em.get("consultant_domains", []),
            contractor_domains=em.get("contractor_domains", []),
        ),
        odoo=SourceMappingOdoo(
            project_model=od.get("project_model", ""),
            cost_model=od.get("cost_model", ""),
            project_external_id=od.get("project_external_id", ""),
            project_name=od.get("project_name", ""),
        ),
        related_people=RelatedPeople(
            project_manager=rp.get("project_manager", ""),
            commercial_manager=rp.get("commercial_manager", ""),
            finance_owner=rp.get("finance_owner", ""),
            document_controller=rp.get("document_controller", ""),
            other=rp.get("other", []),
        ),
        enabled_sources=_jlist(row.get("enabled_sources")),
        allowed_roles=_jlist(row.get("allowed_roles")),
        mapping_status=str(row.get("mapping_status") or "incomplete"),
        last_validation_result=_j(row.get("last_validation_result")) if row.get("last_validation_result") else None,
        last_validated_at=_ts_iso(row["last_validated_at"]) if row.get("last_validated_at") else None,
        created_at=_ts_iso(row["created_at"]) if row.get("created_at") else None,
        updated_at=_ts_iso(row["updated_at"]) if row.get("updated_at") else None,
        created_by_hash=row.get("created_by_hash"),
        updated_by_hash=row.get("updated_by_hash"),
    )


@app.get("/admin/source-mappings")
async def list_source_mappings(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> SourceMappingListResponse:
    """Admin-only list of all project source mappings."""
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    rows = await pg.list_source_mappings()
    import json as _json
    return SourceMappingListResponse(
        mappings=[
            SourceMappingSummary(
                project_code=str(r["project_code"]),
                project_name=str(r.get("project_name") or ""),
                mapping_status=str(r.get("mapping_status") or "incomplete"),
                contract_numbers=(
                    _json.loads(r["contract_numbers"])
                    if isinstance(r.get("contract_numbers"), str)
                    else list(r.get("contract_numbers") or [])
                ),
            )
            for r in rows
        ]
    )


@app.get("/admin/source-mappings/{code}")
async def get_source_mapping(
    code: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> SourceMappingDetail:
    """Admin-only single source mapping detail."""
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    row = await pg.get_source_mapping(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return _row_to_source_mapping_detail(row)


@app.post("/admin/source-mappings/{code}/validate")
async def validate_source_mapping(
    code: str,
    body: SourceMappingUpsertRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> SourceMappingValidateResponse:
    """Admin-only structural validation; no side effects."""
    _require_admin(claims)
    status, errors = _compute_mapping_status(code, body)
    return SourceMappingValidateResponse(
        project_code=code,
        valid=len(errors) == 0,
        status=status,
        errors=errors,
    )


@app.put("/admin/source-mappings/{code}")
async def upsert_source_mapping(
    code: str,
    body: SourceMappingUpsertRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> SourceMappingDetail:
    """Admin-only upsert of a source mapping.

    A-21: audit event is emitted BEFORE the database write.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    status, _ = _compute_mapping_status(code, body)
    actor_hash = hash_user_id(claims.user_id) if claims else ""
    # A-21 audit-before-save
    await pg.insert_admin_event(
        event_type="admin.source_mapping_changed",
        actor_hash=actor_hash,
        project_code=code,
        detail=f"status={status}",
    )
    await pg.upsert_source_mapping(
        project_code=code,
        project_name=body.project_name,
        contract_numbers=body.contract_numbers,
        sharepoint=body.sharepoint.model_dump(),
        owncloud=body.owncloud.model_dump(),
        email=body.email.model_dump(),
        odoo=body.odoo.model_dump(),
        related_people=body.related_people.model_dump(),
        enabled_sources=body.enabled_sources,
        allowed_roles=body.allowed_roles,
        mapping_status=status,
        actor_hash=actor_hash,
    )
    row = await pg.get_source_mapping(code)
    if row is None:
        raise HTTPException(status_code=500, detail="Upsert failed.")
    return _row_to_source_mapping_detail(row)


@app.post("/admin/source-mappings/{code}/disable")
async def disable_source_mapping(
    code: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> Response:
    """Admin-only soft-disable of a source mapping.

    404 if missing; 409 if already disabled.  A-21: audit event emitted
    before the status change.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    row = await pg.get_source_mapping(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    if row.get("mapping_status") == "disabled":
        raise HTTPException(status_code=409, detail="Mapping already disabled")
    actor_hash = hash_user_id(claims.user_id) if claims else ""
    await pg.insert_admin_event(
        event_type="admin.source_mapping_disabled",
        actor_hash=actor_hash,
        project_code=code,
        detail="mapping disabled",
    )
    await pg.disable_source_mapping(code)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Phase 2B Slice 5 — Permissions & Roles (Entra Group Mapping)
# Implements GET /admin/entra-mappings, PUT /admin/entra-mappings/{group_id},
# DELETE /admin/entra-mappings/{group_id} per docs/execution/PHASE_2B_PLAN.md §E row 5.
# Admin-only via _require_admin.  C-1 / C-6 compliant.  A-17 audit-before-save.
# ---------------------------------------------------------------------------


class EntraGroupMapping(BaseModel):
    model_config = {"extra": "forbid"}

    entra_group_id: str
    role: str
    created_at: str
    updated_at: str


class EntraGroupMappingUpsertRequest(BaseModel):
    model_config = {"extra": "forbid"}

    role: str = Field(min_length=1)


class EntraGroupMappingListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    mappings: list[EntraGroupMapping]


def _validate_canonical_role(role: str) -> None:
    """Raise 400 if role is not one of the nine canonical roles."""
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {role}. Must be one of: {sorted(VALID_ROLES)}",
        )


@app.get("/admin/entra-mappings")
async def list_entra_mappings(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> EntraGroupMappingListResponse:
    """Admin-only list of all Entra group → role mappings."""
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    rows = await pg.list_entra_mappings()
    mappings = [
        EntraGroupMapping(
            entra_group_id=str(r["entra_group_id"]),
            role=str(r["role"]),
            created_at=_ts_iso(r["created_at"]),
            updated_at=_ts_iso(r["updated_at"]),
        )
        for r in rows
    ]
    return EntraGroupMappingListResponse(mappings=mappings)


@app.put("/admin/entra-mappings/{group_id}")
async def upsert_entra_mapping(
    group_id: str,
    body: EntraGroupMappingUpsertRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> EntraGroupMapping:
    """Admin-only upsert of an Entra group → role mapping.

    A-17: audit event is emitted BEFORE the database write.
    """
    _require_admin(claims)
    _validate_canonical_role(body.role)
    pg = get_postgres_store()
    await pg.init_schema()

    actor_hash = hash_user_id(claims.user_id) if claims else ""
    # A-17 audit-before-save
    await pg.insert_admin_event(
        event_type="admin.role_mapping_changed",
        actor_hash=actor_hash,
        project_code=None,
        detail=f"group={group_id} role={body.role}",
    )
    await pg.upsert_entra_mapping(entra_group_id=group_id, role=body.role)

    row = await pg.get_entra_mapping(group_id)
    assert row is not None  # we just wrote it
    return EntraGroupMapping(
        entra_group_id=str(row["entra_group_id"]),
        role=str(row["role"]),
        created_at=_ts_iso(row["created_at"]),
        updated_at=_ts_iso(row["updated_at"]),
    )


@app.delete("/admin/entra-mappings/{group_id}")
async def delete_entra_mapping(
    group_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> Response:
    """Admin-only delete of an Entra group → role mapping.

    404 if the mapping does not exist.  A-17: audit event emitted
    only after confirming existence and before the delete.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()

    row = await pg.get_entra_mapping(group_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")

    actor_hash = hash_user_id(claims.user_id) if claims else ""
    await pg.insert_admin_event(
        event_type="admin.role_mapping_changed",
        actor_hash=actor_hash,
        project_code=None,
        detail=f"deleted group={group_id} role={row['role']}",
    )
    await pg.delete_entra_mapping(group_id)
    return Response(status_code=204)
