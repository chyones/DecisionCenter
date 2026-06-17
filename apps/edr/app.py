import asyncio
import hashlib
import json
import os
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
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
from apps.edr.admin import connector_status
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
    # IDs returned by POST /upload for files attached to this request. Recorded
    # in the workflow inputs/audit trail; node-level ingestion is a later phase.
    upload_ids: list[str] = []


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
    project_name: str | None = None
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
    qg_failure_reason: str | None = None


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
    project_name: str = ""
    contract_numbers: list[str] = Field(default_factory=list)


class WorkspaceContextResponse(BaseModel):
    user_id: str
    role: str
    allowed_projects: list[WorkspaceProject]
    can_generate_report: bool
    can_approve: bool
    can_access_odoo_budget: bool


class MeResponse(BaseModel):
    user_id_hash: str
    role: str


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
    project_name: str | None = None
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
    if settings.app_env == "production" and (x_user_role or x_user_id):
        raise HTTPException(
            status_code=400,
            detail="dev bypass headers are not accepted in production",
        )
    if settings.entra_client_id and settings.entra_tenant_id:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization: Bearer <token> required")
        token = authorization.removeprefix("Bearer ")
        validator = EntraJWTValidator(settings.entra_tenant_id, settings.entra_client_id)
        try:
            return validator.validate(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
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

    # Owner-operator model (SPEC_CHANGE 2026-05-31): admin is a full owner and
    # approves via the normal path. Admin retains the separate metadata-only
    # override endpoints under /admin/approvals.
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

    Owner-operator model (SPEC_CHANGE 2026-05-31): shared decision-support for
    ~5 equal company owners.
    - owner roles (``can_view_all_reports``: executive, admin): read all reports.
    - auditor: allowed (read-only across all projects).
    - everyone else: only when the requester's hashed user_id matches the
      stored ``user_id_hash``.
    """
    if settings.entra_client_id and settings.entra_tenant_id:
        if claims is None or not claims.user_id:
            raise HTTPException(status_code=401, detail="Authentication required.")

    role_str = claims.role if claims else None

    # Bypass mode (no Entra): role is the only signal; allow any role through.
    if not (settings.entra_client_id and settings.entra_tenant_id):
        return

    if role_str == Role.AUDITOR.value:
        return

    try:
        if ROLE_PERMISSIONS[Role(role_str)].can_view_all_reports:
            return
    except (ValueError, KeyError):
        pass

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
    if role == Role.AUDITOR:
        return False
    perms = _role_permissions(role)
    # Owner-operator model: self-approval allowed, so a requester may review
    # their own report; two-person rule removed (SPEC_CHANGE 2026-05-31).
    return perms.can_approve


def _check_can_read_report_content(claims: JWTClaims, audit: dict[str, Any]) -> None:
    role = _validated_role(claims)

    if not (settings.entra_client_id and settings.entra_tenant_id):
        return

    perms = _role_permissions(role)
    if (
        _is_requester(claims, audit)
        or role == Role.AUDITOR
        or perms.can_view_all_reports
        or _can_review_report(claims, audit)
    ):
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

    Report ``in_progress`` while the quality gate is still in its default
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


@app.get("/me", response_model=MeResponse)
async def get_me(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> MeResponse:
    """Return the caller's resolved canonical role and hashed user id.

    Identity metadata only — a hashed user id plus the canonical role, never any
    business data — so every authenticated canonical role (admin included) may
    call it. The production frontend uses this as the authoritative role source
    after Entra login. Server-side RBAC on every other route is unaffected.
    """
    claims = _require_claims(claims)
    role = _validated_role(claims)
    return MeResponse(
        user_id_hash=hash_user_id(claims.user_id) if claims.user_id else "",
        role=role.value,
    )


@app.get("/workspace/context", response_model=WorkspaceContextResponse)
async def get_workspace_context(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> WorkspaceContextResponse:
    """Return the role-scoped workspace context used by the Phase 2A UI."""
    claims = _require_claims(claims)
    role = _validated_role(claims)
    perms = _role_permissions(role)

    projects: list[WorkspaceProject] = []
    if perms.can_generate_report:
        mapping = ProjectMapping.load()
        projects = [
            WorkspaceProject(
                project_code=str(entry.get("project_code", "")),
                project_name=str(entry.get("display_name") or entry.get("project_code", "")),
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

    perms = _role_permissions(role)
    if role == Role.AUDITOR or perms.can_view_all_reports:
        scoped_user_hash: str | None = None  # all reports (owners + auditor)
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

    try:
        _pm = ProjectMapping.load()
    except Exception:
        _pm = None

    def _lookup_name(code: str | None) -> str | None:
        if not code or _pm is None:
            return None
        try:
            return _pm.get(code).get("display_name") or code
        except Exception:
            return code

    summaries: list[ReportSummary] = []
    for row in rows:
        _code = row.get("project_code")
        summaries.append(
            ReportSummary(
                request_id=row["request_id"],
                project_code=_code,
                project_name=_lookup_name(_code),
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
        qg_failure_reason=audit.get("qg_failure_reason"),
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
    elif state == "needs_review" and is_requester and not can_review:
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

    _report_code = audit.get("project_code")
    try:
        _rp_name: str | None = ProjectMapping.load().get(_report_code).get("display_name") if _report_code else None
    except Exception:
        _rp_name = _report_code

    return ReportContentResponse(
        request_id=audit["request_id"],
        project_code=_report_code,
        project_name=_rp_name,
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

    # Owner-operator model: self-approval allowed (two-person rule removed,
    # SPEC_CHANGE 2026-05-31). The automated quality gate still gates publish.
    reviewer_hash = hash_user_id(claims.user_id)

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

    # Owner-operator model: self-action allowed (SPEC_CHANGE 2026-05-31).
    reviewer_hash = hash_user_id(claims.user_id)

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

    # Owner-operator model: self-action allowed (SPEC_CHANGE 2026-05-31).
    reviewer_hash = hash_user_id(claims.user_id)

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

        # Auditor reads all; owner roles (can_view_all_reports) read all.
        allowed = requester_hash == stored_hash or role == Role.AUDITOR.value
        try:
            if ROLE_PERMISSIONS[Role(role)].can_view_all_reports:
                allowed = True
        except (ValueError, KeyError):
            pass
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


@app.get(
    "/admin/connectors/truth",
    response_model=connector_status.ConnectorTruthReport,
)
def admin_connectors_truth(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    probe: Annotated[bool, Query()] = True,
) -> connector_status.ConnectorTruthReport:
    """Admin-only connector truth report (Connector Status Truth model).

    Honest per-connector states (NOT_CONFIGURED / CONFIGURED_NOT_TESTED /
    LIVE_OK / AUTH_FAILED / ...) plus a readiness banner. Never reports a
    connector green without a real live probe. No credential values are ever
    returned (C-6) — only non-secret config key names and presence booleans.
    ``?probe=false`` returns the config-only view (skips live network probes).
    """
    _require_admin(claims)
    return connector_status.build_report(run_probes=probe)


@app.post("/admin/connectors/entra/revalidate-current-token")
async def admin_entra_revalidate_token(
    request: Request,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict:
    """Revalidate Entra auth using the caller's current browser bearer token.

    The auth dependency and evidence writer validate the same API-audience token.
    Only redacted validation evidence is persisted or returned.
    """
    admin_claims = _require_admin(claims)
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=400,
            detail="Current Microsoft session token required",
        )
    _raw_token = auth_header[7:].strip()
    try:
        evidence = await run_in_threadpool(
            connector_status.write_entra_validation_evidence_marker,
            _raw_token,
            expected_user_id=admin_claims.user_id,
            expected_role=admin_claims.role or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        del _raw_token
    return evidence


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


#: Maps the authoritative connector-truth state to the System Health tri-state.
#  Workflow connectors (Odoo/SharePoint/Graph/ownCloud) are surfaced from the
#  same truth as GET /admin/connectors/truth so System Health never shows a
#  false green and stays consistent with the Connectors page.
_CONNECTOR_STATE_TO_HEALTH: dict[connector_status.ConnectorState, str] = {
    connector_status.ConnectorState.LIVE_OK: "ok",
    connector_status.ConnectorState.VALIDATED: "ok",
    connector_status.ConnectorState.VERIFIED_FROM_EVIDENCE: "ok",
    connector_status.ConnectorState.CONNECTED_NO_DATA: "ok",
    connector_status.ConnectorState.PREVIOUSLY_VALIDATED_TOKEN_EXPIRED: "unknown",
    connector_status.ConnectorState.CONFIGURED_NOT_TESTED: "unknown",
    connector_status.ConnectorState.MOCK_ONLY: "unknown",
    connector_status.ConnectorState.DISABLED: "unknown",
    connector_status.ConnectorState.UNKNOWN: "unknown",
    connector_status.ConnectorState.NOT_CONFIGURED: "error",
    connector_status.ConnectorState.AUTH_FAILED: "error",
    connector_status.ConnectorState.PERMISSION_FAILED: "error",
    connector_status.ConnectorState.NETWORK_FAILED: "error",
}


def _probe_with_latency(name: str) -> tuple[str, int]:
    """Run the registered health check for *name* and return (status, latency_ms).

    Infrastructure services reuse the existing ``_check_*`` helpers.
    Workflow connectors mirror the authoritative connector_status.classify()
    truth (same source as GET /admin/connectors/truth) so there is no false
    green: Odoo runs a live probe, SharePoint/Graph stay unknown (no safe
    server-side probe), ownCloud reports error when config is missing.
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
    check = check_map.get(name)
    if check is not None:
        t0 = time.monotonic()
        try:
            check()
            status = "ok"
        except Exception:
            status = "error"
        latency_ms = int((time.monotonic() - t0) * 1000)
        return (status, latency_ms)

    # Workflow connectors: mirror the authoritative per-connector truth from
    # connector_status.classify() instead of n8n reachability (which was a
    # false green). Odoo runs a real live probe; SharePoint/Graph have no safe
    # server-side probe (-> unknown); ownCloud -> error when config missing.
    spec = connector_status.CONNECTOR_SPEC_BY_NAME.get(name)
    if spec is not None:
        t0 = time.monotonic()
        truth = connector_status.classify(spec, run_probe=True)
        latency_ms = int((time.monotonic() - t0) * 1000)
        status = _CONNECTOR_STATE_TO_HEALTH.get(truth.state, "unknown")
        # Latency is only meaningful when we actually reached the service.
        return (status, latency_ms if status == "ok" else 0)

    return ("unknown", 0)


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
        status, latency_ms = await run_in_threadpool(_probe_with_latency, name)
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
        checked_at=datetime.now(timezone.utc).isoformat(),
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


class SourceMappingMicrosoftGroup(BaseModel):
    model_config = {"extra": "forbid"}
    id: str = ""
    display_name: str = ""
    mail: str = ""
    mail_enabled: bool = False


class SourceMappingMicrosoftGroupMember(BaseModel):
    model_config = {"extra": "forbid"}
    id: str = ""
    display_name: str = ""
    mail: str = ""
    user_principal_name: str = ""
    job_title: str = ""
    department: str = ""
    email: str = ""


class SourceMappingMicrosoft(BaseModel):
    model_config = {"extra": "forbid"}
    group: SourceMappingMicrosoftGroup = Field(default_factory=SourceMappingMicrosoftGroup)
    group_members: list[SourceMappingMicrosoftGroupMember] = []
    group_membership_status: str = ""
    member_count: int = 0
    missing_permissions: list[str] = []
    blockers: list[str] = []


class SourceMappingOdoo(BaseModel):
    model_config = {"extra": "forbid"}
    project_model: str = ""
    cost_model: str = ""
    project_external_id: str = ""
    project_name: str = ""
    analytic_account_id: str = ""


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
    microsoft: SourceMappingMicrosoft = Field(default_factory=SourceMappingMicrosoft)
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
    microsoft: SourceMappingMicrosoft = Field(default_factory=SourceMappingMicrosoft)
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

    def add_error(field: str, message: str) -> None:
        if not any(e.field == field and e.message == message for e in errors):
            errors.append(ValidationFieldError(field=field, message=message))

    def is_placeholder(value: str) -> bool:
        lower = value.strip().lower()
        return (
            "example-" in lower
            or "example.com" in lower
            or bool(re.search(r"^/projects/prj-\d+(?:/|$)", lower))
        )

    def validate_no_placeholder(field: str, value: str) -> None:
        if value and is_placeholder(value):
            add_error(field, "Placeholder value is not allowed in a complete mapping")

    def validate_no_placeholder_list(field: str, values: list[str]) -> None:
        for value in values:
            validate_no_placeholder(field, value)

    def real_email(value: str) -> bool:
        stripped = value.strip()
        return bool(stripped and "@" in stripped and not is_placeholder(stripped))

    def real_domain(value: str) -> bool:
        stripped = value.strip()
        return bool(stripped and "." in stripped and "@" not in stripped and not is_placeholder(stripped))

    if not enabled:
        add_error("enabled_sources", "At least one verified source must be enabled")

    validate_no_placeholder("project_name", body.project_name)
    validate_no_placeholder_list("contract_numbers", body.contract_numbers)
    validate_no_placeholder("sharepoint.site_id", body.sharepoint.site_id)
    validate_no_placeholder("sharepoint.drive_id", body.sharepoint.drive_id)
    validate_no_placeholder("sharepoint.root_path", body.sharepoint.root_path)
    validate_no_placeholder("owncloud.base_path", body.owncloud.base_path)
    validate_no_placeholder_list("email.shared_mailboxes", body.email.shared_mailboxes)
    validate_no_placeholder("email.document_control_mailbox", body.email.document_control_mailbox)
    validate_no_placeholder_list("email.client_domains", body.email.client_domains)
    validate_no_placeholder_list("email.consultant_domains", body.email.consultant_domains)
    validate_no_placeholder_list("email.contractor_domains", body.email.contractor_domains)
    validate_no_placeholder("microsoft.group.id", body.microsoft.group.id)
    validate_no_placeholder("microsoft.group.display_name", body.microsoft.group.display_name)
    validate_no_placeholder("microsoft.group.mail", body.microsoft.group.mail)
    validate_no_placeholder("microsoft.group_membership_status", body.microsoft.group_membership_status)
    validate_no_placeholder_list("microsoft.missing_permissions", body.microsoft.missing_permissions)
    validate_no_placeholder_list("microsoft.blockers", body.microsoft.blockers)
    for member in body.microsoft.group_members:
        validate_no_placeholder("microsoft.group_members.id", member.id)
        validate_no_placeholder("microsoft.group_members.display_name", member.display_name)
        validate_no_placeholder("microsoft.group_members.mail", member.mail)
        validate_no_placeholder("microsoft.group_members.user_principal_name", member.user_principal_name)
        validate_no_placeholder("microsoft.group_members.job_title", member.job_title)
        validate_no_placeholder("microsoft.group_members.department", member.department)
        validate_no_placeholder("microsoft.group_members.email", member.email)
    validate_no_placeholder("odoo.project_external_id", body.odoo.project_external_id)
    validate_no_placeholder("odoo.project_name", body.odoo.project_name)
    validate_no_placeholder("odoo.project_model", body.odoo.project_model)
    validate_no_placeholder("odoo.cost_model", body.odoo.cost_model)
    validate_no_placeholder("odoo.analytic_account_id", body.odoo.analytic_account_id)
    validate_no_placeholder("related_people.project_manager", body.related_people.project_manager)
    validate_no_placeholder("related_people.commercial_manager", body.related_people.commercial_manager)
    validate_no_placeholder("related_people.finance_owner", body.related_people.finance_owner)
    validate_no_placeholder("related_people.document_controller", body.related_people.document_controller)
    validate_no_placeholder_list("related_people.other", body.related_people.other)

    group_status = body.microsoft.group_membership_status.strip()
    if group_status.upper().startswith("BLOCKED"):
        add_error(
            field="microsoft.group_membership_status",
            message="Email group enrichment is blocked by Microsoft Graph permission or source availability",
        )
    if body.microsoft.missing_permissions:
        add_error(
            field="microsoft.missing_permissions",
            message="Required Microsoft Graph group/member permission is missing",
        )
    if body.microsoft.blockers:
        add_error(
            field="microsoft.blockers",
            message="Source mapping has unresolved Microsoft group/email blockers",
        )

    if "sharepoint" in enabled:
        if not body.sharepoint.site_id:
            add_error("sharepoint.site_id", "Required for SharePoint source")
        if not body.sharepoint.drive_id:
            add_error("sharepoint.drive_id", "Required for SharePoint source")
        if not body.sharepoint.root_path:
            add_error("sharepoint.root_path", "Required for SharePoint source")
        if body.sharepoint.site_id and is_placeholder(body.sharepoint.site_id):
            add_error("sharepoint.site_id", "Real SharePoint site_id is required")
        if body.sharepoint.drive_id and is_placeholder(body.sharepoint.drive_id):
            add_error("sharepoint.drive_id", "Real SharePoint drive_id is required")
        if body.sharepoint.root_path and is_placeholder(body.sharepoint.root_path):
            add_error("sharepoint.root_path", "Root path must not use an internal PRJ placeholder")

    if "owncloud" in enabled:
        if not (settings.owncloud_username and settings.owncloud_password):
            add_error("enabled_sources", "ownCloud cannot be enabled until ownCloud is configured")
        if not body.owncloud.base_path:
            add_error("owncloud.base_path", "Required for ownCloud source")

    if "email" in enabled:
        mailboxes = [*body.email.shared_mailboxes, body.email.document_control_mailbox]
        group_mailbox_valid = (
            body.microsoft.group.mail_enabled and real_email(body.microsoft.group.mail)
        )
        member_emails = {
            member.email.strip().lower()
            for member in body.microsoft.group_members
            if real_email(member.email)
        }
        for mailbox in mailboxes:
            if real_email(mailbox) and mailbox.strip().lower() in member_emails:
                add_error(
                    field="email.shared_mailboxes",
                    message="Group members must be stored under microsoft.group_members, not Shared Mailboxes",
                )
        if body.microsoft.group.mail.strip() and not body.microsoft.group.mail_enabled:
            add_error(
                field="microsoft.group.mail_enabled",
                message="Microsoft group mailbox must be mailEnabled before Email source can use it",
            )
        if not any(real_email(v) for v in mailboxes) and not group_mailbox_valid:
            add_error(
                field="email.shared_mailboxes",
                message="At least one real mailbox or Microsoft 365 group mailbox required for Email source",
            )

    if "odoo" in enabled:
        external_id = body.odoo.project_external_id.strip()
        if not external_id:
            add_error(
                field="odoo.project_external_id",
                message="Real Odoo project ID is required",
            )
        elif re.fullmatch(r"PRJ-\d+", external_id, flags=re.IGNORECASE):
            add_error(
                field="odoo.project_external_id",
                message="Internal PRJ codes cannot be used as Odoo external IDs",
            )
        elif not external_id.isdigit():
            add_error(
                field="odoo.project_external_id",
                message="Odoo project external ID must be the numeric project.project id",
            )
        if not body.odoo.project_name.strip():
            add_error("odoo.project_name", "Odoo project name is required")
        if (
            body.project_name.strip()
            and body.odoo.project_name.strip()
            and body.project_name.strip() != body.odoo.project_name.strip()
        ):
            add_error("project_name", "Project Name must match Odoo project.project.name")
        if body.odoo.project_model and body.odoo.project_model != "project.project":
            add_error("odoo.project_model", "Odoo project model must be project.project")
        if body.odoo.cost_model and body.odoo.cost_model != "account.analytic.line":
            add_error("odoo.cost_model", "Cost model must remain account.analytic.line")
        if not body.odoo.project_model:
            add_error("odoo.project_model", "Odoo project model is required")
        if not body.odoo.cost_model:
            add_error("odoo.cost_model", "Odoo cost model is required")

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
    ms = _j(row.get("microsoft"))
    od = _j(row.get("odoo"))
    rp = _j(row.get("related_people"))

    detail = SourceMappingDetail(
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
        microsoft=SourceMappingMicrosoft(
            group=SourceMappingMicrosoftGroup(
                id=(ms.get("group") or {}).get("id", ""),
                display_name=(ms.get("group") or {}).get("display_name", ""),
                mail=(ms.get("group") or {}).get("mail", ""),
                mail_enabled=bool((ms.get("group") or {}).get("mail_enabled", False)),
            ),
            group_members=[
                SourceMappingMicrosoftGroupMember(
                    id=str(member.get("id", "")),
                    display_name=str(member.get("display_name", "")),
                    mail=str(member.get("mail", "")),
                    user_principal_name=str(member.get("user_principal_name", "")),
                    job_title=str(member.get("job_title", "")),
                    department=str(member.get("department", "")),
                    email=str(member.get("email", "")),
                )
                for member in ms.get("group_members", [])
                if isinstance(member, dict)
            ],
            group_membership_status=str(ms.get("group_membership_status", "")),
            member_count=int(ms.get("member_count", len(ms.get("group_members", [])))),
            missing_permissions=ms.get("missing_permissions", []),
            blockers=ms.get("blockers", []),
        ),
        odoo=SourceMappingOdoo(
            project_model=od.get("project_model", ""),
            cost_model=od.get("cost_model", ""),
            project_external_id=od.get("project_external_id", ""),
            project_name=od.get("project_name", ""),
            analytic_account_id=str(od.get("analytic_account_id", "")),
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
    if detail.mapping_status == "disabled":
        return detail

    body = SourceMappingUpsertRequest(
        project_name=detail.project_name,
        contract_numbers=detail.contract_numbers,
        sharepoint=detail.sharepoint,
        owncloud=detail.owncloud,
        email=detail.email,
        microsoft=detail.microsoft,
        odoo=detail.odoo,
        related_people=detail.related_people,
        enabled_sources=detail.enabled_sources,
        allowed_roles=detail.allowed_roles,
    )
    status, errors = _compute_mapping_status(detail.project_code, body)
    if status == detail.mapping_status and not errors:
        return detail

    return detail.model_copy(
        update={
            "mapping_status": status,
            "last_validation_result": {
                "status": status,
                "errors": [error.model_dump() for error in errors],
            },
        }
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

    def _summary_status(row: dict[str, Any]) -> str:
        if "enabled_sources" not in row:
            return str(row.get("mapping_status") or "incomplete")
        return _row_to_source_mapping_detail(row).mapping_status

    return SourceMappingListResponse(
        mappings=[
            SourceMappingSummary(
                project_code=str(r["project_code"]),
                project_name=str(r.get("project_name") or ""),
                mapping_status=_summary_status(r),
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
        microsoft=body.microsoft.model_dump(),
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
# Odoo Source Map (visibility)
# GET  /admin/source-mappings/{code}/odoo-source-map  — generic map + runtime ids
# POST /admin/source-mappings/{code}/odoo-source-map/scan — read-only count scan
# Admin-only. Built from the proven Odoo source registry, never hardcoded.
# ---------------------------------------------------------------------------

from apps.edr.admin.odoo_source_map import (  # noqa: E402
    OdooSourceMapResponse,
    build_source_map,
)
from apps.edr.admin import odoo_scan_session as scan_engine  # noqa: E402


async def _load_odoo_map_context(code: str) -> tuple[dict, str, bool, list[str]]:
    """Return (odoo_config, mapping_status, odoo_enabled, allowed_odoo_ids).

    404 if the mapping does not exist. No project ids are hardcoded — values are
    read from the saved mapping row at runtime.
    """
    pg = get_postgres_store()
    await pg.init_schema()
    row = await pg.get_source_mapping(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    detail = _row_to_source_mapping_detail(row)
    odoo_config = detail.odoo.model_dump()
    odoo_enabled = "odoo" in detail.enabled_sources
    ext_id = str(odoo_config.get("project_external_id") or "").strip()
    allowed_odoo_ids = [ext_id] if ext_id else []
    return odoo_config, detail.mapping_status, odoo_enabled, allowed_odoo_ids


# ---------------------------------------------------------------------------
# Batched scan session plumbing. The scan runs in a background asyncio task so
# the POST endpoint returns instantly and never holds the reverse proxy open
# while Odoo is queried (the old single-request scan could exceed the 120s proxy
# timeout). Progress is flushed to Postgres after every source so the UI can poll
# live, and a failed/partial source can be retried or resumed.
# ---------------------------------------------------------------------------


def _scan_cfg() -> "scan_engine.ScanConfig":
    return scan_engine.ScanConfig.from_settings(settings)


async def _persist_scan(snapshot: dict) -> None:
    pg = get_postgres_store()
    await pg.save_scan_session(
        session_id=snapshot["session_id"],
        project_code=snapshot["project_code"],
        state=snapshot["state"],
        snapshot=snapshot,
    )


def _launch_scan_task(
    session: "scan_engine.ScanSession",
    *,
    odoo_config: dict,
    allowed_odoo_ids: list[str],
    sources: list,
) -> None:
    """Register the session and run it to completion in a background task."""
    scan_engine.register(session)

    async def _runner() -> None:
        try:
            await scan_engine.run_scan_session(
                session,
                odoo_config=odoo_config,
                allowed_odoo_ids=allowed_odoo_ids,
                sources=sources,
                cfg=_scan_cfg(),
                on_progress=_persist_scan,
            )
        except Exception:  # noqa: BLE001 — never let a scan crash the worker
            session.state = scan_engine.S_FAILED
            session.summary = "Scan task crashed unexpectedly."
            try:
                await _persist_scan(session.snapshot())
            except Exception:  # noqa: BLE001
                pass

    asyncio.create_task(_runner())


async def _resolve_scan_snapshot(code: str, session_id: str) -> dict | None:
    """Live in-process snapshot if present, else the durable Postgres copy."""
    live = scan_engine.get_active(session_id)
    if live is not None and live.project_code == code:
        return live.snapshot()
    pg = get_postgres_store()
    snap = await pg.get_scan_session(session_id)
    if snap is None or snap.get("project_code") != code:
        return None
    return snap


@app.get("/admin/source-mappings/{code}/odoo-source-map")
async def get_odoo_source_map(
    code: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> OdooSourceMapResponse:
    """Admin-only: the generic Odoo Source Map with this project's runtime ids.

    Shows every registry source (where DecisionCenter will search in Odoo), the
    proven project-link path, key fields, gap type, confidence, warnings, and the
    denylisted/ambiguous paths that are never queried. Merges the latest scan for
    this project (live session if one is running, else the last saved snapshot) so
    counts/statuses persist across reloads.
    """
    _require_admin(claims)
    odoo_config, mapping_status, odoo_enabled, _ = await _load_odoo_map_context(code)
    session: dict | None = None
    live = scan_engine.active_running_for_project(code)
    if live is not None:
        session = live.snapshot()
    else:
        pg = get_postgres_store()
        try:
            session = await pg.get_latest_scan_session(code)
        except Exception:  # noqa: BLE001 — map must render even if history read fails
            session = None
    return build_source_map(
        project_code=code,
        odoo_config=odoo_config,
        mapping_status=mapping_status,
        odoo_enabled=odoo_enabled,
        extended_enabled=settings.odoo_extended_sources_enabled,
        session=session,
    )


@app.post("/admin/source-mappings/{code}/odoo-source-map/scan")
async def scan_odoo_source_map(
    code: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> OdooSourceMapResponse:
    """Admin-only: START a read-only batched scan session and return immediately.

    The scan does NOT run inline — it is processed source-by-source in small
    batches by a background session (see apps.edr.admin.odoo_scan_session). The
    response carries the initial snapshot (all sources ``pending``) plus the
    ``scan_session_id`` the UI then polls via GET …/scan/{session_id}. This makes
    a scan impossible to time out at the reverse proxy regardless of source count.
    No writes to Odoo, ever; queries are project-scoped + denylist-safe.
    """
    claims = _require_admin(claims)
    odoo_config, mapping_status, odoo_enabled, allowed_odoo_ids = (
        await _load_odoo_map_context(code)
    )
    pg = get_postgres_store()
    actor_hash = hash_user_id(claims.user_id) if claims else ""
    await pg.insert_admin_event(
        event_type="admin.odoo_source_map_scan",
        actor_hash=actor_hash,
        project_code=code,
        detail="batched_read_only_scan_started",
    )

    session_snapshot: dict | None = None
    if odoo_enabled:
        existing = scan_engine.active_running_for_project(code)
        if existing is not None:
            session_snapshot = existing.snapshot()  # idempotent: reuse running scan
        else:
            session = scan_engine.init_full_session(code)
            await _persist_scan(session.snapshot())
            _launch_scan_task(
                session,
                odoo_config=odoo_config,
                allowed_odoo_ids=allowed_odoo_ids,
                sources=scan_engine.sources_for_keys(scan_engine.all_source_keys()),
            )
            session_snapshot = session.snapshot()

    return build_source_map(
        project_code=code,
        odoo_config=odoo_config,
        mapping_status=mapping_status,
        odoo_enabled=odoo_enabled,
        extended_enabled=settings.odoo_extended_sources_enabled,
        session=session_snapshot,
    )


@app.get("/admin/source-mappings/{code}/odoo-source-map/scan/{session_id}")
async def get_odoo_scan_status(
    code: str,
    session_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> OdooSourceMapResponse:
    """Admin-only: poll live progress + partial results of a scan session."""
    _require_admin(claims)
    odoo_config, mapping_status, odoo_enabled, _ = await _load_odoo_map_context(code)
    snapshot = await _resolve_scan_snapshot(code, session_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Scan session not found")
    return build_source_map(
        project_code=code,
        odoo_config=odoo_config,
        mapping_status=mapping_status,
        odoo_enabled=odoo_enabled,
        extended_enabled=settings.odoo_extended_sources_enabled,
        session=snapshot,
    )


@app.post("/admin/source-mappings/{code}/odoo-source-map/scan/{session_id}/retry")
async def retry_odoo_scan(
    code: str,
    session_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    mode: str = "failed",
) -> OdooSourceMapResponse:
    """Admin-only: re-run only failed sources (``mode=failed``) or resume all
    incomplete sources (``mode=incomplete``) within an existing scan session.

    Already-completed sources are left untouched — the scan never restarts from
    zero. Returns immediately; poll the same session id for progress.
    """
    claims = _require_admin(claims)
    odoo_config, mapping_status, odoo_enabled, allowed_odoo_ids = (
        await _load_odoo_map_context(code)
    )

    live = scan_engine.get_active(session_id)
    if (
        live is not None
        and live.project_code == code
        and live.state in (scan_engine.S_PENDING, scan_engine.S_RUNNING)
    ):
        return build_source_map(
            project_code=code, odoo_config=odoo_config, mapping_status=mapping_status,
            odoo_enabled=odoo_enabled,
            extended_enabled=settings.odoo_extended_sources_enabled,
            session=live.snapshot(),
        )

    if live is not None and live.project_code == code:
        session = live
    else:
        snap = await _resolve_scan_snapshot(code, session_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="Scan session not found")
        session = scan_engine.ScanSession.from_snapshot(snap)

    keys = scan_engine.select_retry_keys(session, mode=mode)
    if not keys:
        return build_source_map(
            project_code=code, odoo_config=odoo_config, mapping_status=mapping_status,
            odoo_enabled=odoo_enabled,
            extended_enabled=settings.odoo_extended_sources_enabled,
            session=session.snapshot(),
        )

    for k in keys:
        prev = session.sources.get(k)
        session.sources[k] = scan_engine.SourceScanState(
            key=k,
            status=scan_engine.PENDING,
            pages_done=prev.pages_done if prev else 0,
            next_offset=prev.next_offset if prev else 0,
        )
    session.state = scan_engine.S_RUNNING

    pg = get_postgres_store()
    actor_hash = hash_user_id(claims.user_id) if claims else ""
    await pg.insert_admin_event(
        event_type="admin.odoo_source_map_scan",
        actor_hash=actor_hash,
        project_code=code,
        detail=f"scan_retry:{mode}:{len(keys)}",
    )

    _launch_scan_task(
        session,
        odoo_config=odoo_config,
        allowed_odoo_ids=allowed_odoo_ids,
        sources=scan_engine.sources_for_keys(keys),
    )
    return build_source_map(
        project_code=code, odoo_config=odoo_config, mapping_status=mapping_status,
        odoo_enabled=odoo_enabled,
        extended_enabled=settings.odoo_extended_sources_enabled,
        session=session.snapshot(),
    )


# ---------------------------------------------------------------------------
# Odoo + SharePoint Exact-Name Sync
# POST /admin/source-mappings/sync-odoo-sharepoint
# Admin-only. Read-only Odoo (XML-RPC). Read-only Microsoft Graph.
# Exact match: normalized_odoo_name == normalized_sharepoint_displayName
# No fuzzy matching, no token scoring, no guessing.
# A-21 audit-before-save.  C-1/C-6 compliant.
# ---------------------------------------------------------------------------

from apps.edr.admin.odoo_sharepoint_sync import (  # noqa: E402
    OdooSharePointSyncResult,
    run_odoo_sharepoint_sync,
)


@app.post("/admin/source-mappings/sync-odoo-sharepoint")
async def sync_odoo_sharepoint(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> OdooSharePointSyncResult:
    """Admin-only: exact-name sync between Odoo projects and SharePoint sites.

    Pulls active Odoo project.project records and SharePoint sites, then
    compares normalized Odoo project name against normalized SharePoint
    displayName (100% exact, no fuzzy matching).

    For each exact 1:1 match where site_id and drive_id are available and
    no MANUALLY_CONFIRMED mapping already holds the site_id, the mapping is
    auto-saved with project_code = "odoo-{odoo_project_id}".

    Safety: read-only Odoo and Graph. No writes to SharePoint or Mail.
    Odoo follower and email data are never read. A-21: audit before writes.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()

    existing_rows = await pg.list_source_mappings_full()
    actor_hash = hash_user_id(claims.user_id) if claims else ""

    # A-21 audit event before any DB writes
    await pg.insert_admin_event(
        event_type="admin.odoo_sharepoint_sync_run",
        actor_hash=actor_hash,
        project_code=None,
        detail="scope=all",
    )

    result = await run_odoo_sharepoint_sync(existing_rows)

    # Persist auto-save decisions returned by the sync engine
    saved_count = 0
    for pair in result.matched_pairs:
        if not pair.auto_saved:
            continue
        # A-21 audit before each save
        await pg.insert_admin_event(
            event_type="admin.source_mapping_changed",
            actor_hash=actor_hash,
            project_code=pair.internal_key,
            detail=(
                f"auto_sync method={pair.mapping_method} "
                f"confidence={pair.match_confidence}"
            ),
        )
        await pg.upsert_source_mapping(
            project_code=pair.internal_key,
            project_name=pair.odoo_project_name,
            contract_numbers=[],
            sharepoint={
                "site_id": pair.sharepoint_site_id,
                "drive_id": pair.sharepoint_drive_id or "",
                "root_path": "/",
                "web_url": pair.sharepoint_web_url,
                "site_name": pair.sharepoint_site_name,
                "display_name": pair.sharepoint_display_name,
            },
            owncloud={"base_path": ""},
            email={
                "shared_mailboxes": [],
                "document_control_mailbox": "",
                "client_domains": [],
                "consultant_domains": [],
                "contractor_domains": [],
            },
            microsoft={
                "group": {},
                "group_members": [],
                "group_membership_status": "",
                "member_count": 0,
                "missing_permissions": [],
                "blockers": [],
            },
            odoo={
                "project_external_id": str(pair.odoo_project_id),
                "project_name": pair.odoo_project_name,
                "project_model": "project.project",
                "cost_model": "account.analytic.line",
                "mapping_method": pair.mapping_method,
                "match_confidence": pair.match_confidence,
                "internal_key": pair.internal_key,
            },
            related_people={
                "project_manager": "",
                "commercial_manager": "",
                "finance_owner": "",
                "document_controller": "",
                "other": [],
            },
            enabled_sources=["sharepoint", "odoo"],
            allowed_roles=[],
            mapping_status="complete",
            actor_hash=actor_hash,
        )
        saved_count += 1

    if saved_count != result.auto_saved_count:
        result = result.model_copy(update={"auto_saved_count": saved_count})

    return result


# ---------------------------------------------------------------------------
# Microsoft 365 Group Email Enrichment
# POST /admin/source-mappings/enrich-email-groups
# Admin-only. Read-only Microsoft Graph. PRJ-001 / PRJ-002 only.
# ---------------------------------------------------------------------------

from apps.edr.admin.email_group_enrichment import (  # noqa: E402
    EmailGroupEnrichmentResponse,
    VERDICT_BLOCKED_PERMISSION,
    run_email_group_enrichment,
)


class EmailGroupEnrichmentRequest(BaseModel):
    model_config = {"extra": "forbid"}
    project_codes: list[str] = ["PRJ-001", "PRJ-002"]


@app.post("/admin/source-mappings/enrich-email-groups")
async def enrich_email_groups(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    body: EmailGroupEnrichmentRequest | None = None,
) -> EmailGroupEnrichmentResponse:
    """Read-only Microsoft 365 group enrichment for PRJ-001 and PRJ-002."""
    _require_admin(claims)
    request = body or EmailGroupEnrichmentRequest()
    requested = request.project_codes or ["PRJ-001", "PRJ-002"]
    unsupported = sorted(set(requested) - {"PRJ-001", "PRJ-002"})
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail="Email group enrichment scope is limited to PRJ-001 and PRJ-002.",
        )

    pg = get_postgres_store()
    await pg.init_schema()
    rows = await pg.list_source_mappings()
    row_by_code = {str(row["project_code"]): row for row in rows}
    projects: list[dict[str, Any]] = []
    for code in requested:
        row = row_by_code.get(code)
        if row is None:
            continue
        detail = _row_to_source_mapping_detail(row)
        projects.append({
            "project_code": detail.project_code,
            "project_name": detail.project_name,
            "sharepoint": detail.sharepoint.model_dump(),
            "email": detail.email.model_dump(),
            "microsoft": detail.microsoft.model_dump(),
            "related_people": detail.related_people.model_dump(),
            "enabled_sources": detail.enabled_sources,
            "mapping_status": detail.mapping_status,
        })

    actor_hash = hash_user_id(claims.user_id) if claims else ""
    await pg.insert_admin_event(
        event_type="admin.email_group_enrichment_run",
        actor_hash=actor_hash,
        project_code=None,
        detail=f"scope={','.join(requested)} projects={len(projects)}",
    )

    result = await run_email_group_enrichment(projects)
    if result.verdict == VERDICT_BLOCKED_PERMISSION:
        return result

    for project_result in result.project_results:
        row = row_by_code.get(project_result.project_code)
        if row is None:
            continue
        existing = _row_to_source_mapping_detail(row)
        member_email_set = {
            member.email.strip().lower()
            for member in project_result.group_members
            if member.email.strip()
        }
        email = SourceMappingEmail(
            shared_mailboxes=[
                mailbox
                for mailbox in existing.email.shared_mailboxes
                if mailbox.strip().lower() not in member_email_set
            ],
            document_control_mailbox=existing.email.document_control_mailbox,
            client_domains=existing.email.client_domains,
            consultant_domains=existing.email.consultant_domains,
            contractor_domains=existing.email.contractor_domains,
        )
        microsoft = SourceMappingMicrosoft(
            group=SourceMappingMicrosoftGroup(**project_result.group.model_dump()),
            group_members=[
                SourceMappingMicrosoftGroupMember(**member.model_dump())
                for member in project_result.group_members
            ],
            group_membership_status=project_result.group_membership_status,
            member_count=project_result.member_count,
            missing_permissions=project_result.missing_permissions,
            blockers=project_result.blockers,
        )
        enabled_sources = {
            source for source in existing.enabled_sources if source != "owncloud"
        }
        if project_result.email_enabled:
            enabled_sources.add("email")
        else:
            enabled_sources.discard("email")
        upsert_body = SourceMappingUpsertRequest(
            project_name=existing.project_name,
            contract_numbers=existing.contract_numbers,
            sharepoint=existing.sharepoint,
            owncloud=SourceMappingOwnCloud(base_path=""),
            email=email,
            microsoft=microsoft,
            odoo=existing.odoo,
            related_people=RelatedPeople(**project_result.related_people),
            enabled_sources=sorted(enabled_sources),
            allowed_roles=existing.allowed_roles,
        )
        status, _ = _compute_mapping_status(project_result.project_code, upsert_body)
        await pg.insert_admin_event(
            event_type="admin.source_mapping_changed",
            actor_hash=actor_hash,
            project_code=project_result.project_code,
            detail=f"email_group_enrichment status={status}",
        )
        await pg.upsert_source_mapping(
            project_code=project_result.project_code,
            project_name=upsert_body.project_name,
            contract_numbers=upsert_body.contract_numbers,
            sharepoint=upsert_body.sharepoint.model_dump(),
            owncloud=upsert_body.owncloud.model_dump(),
            email=upsert_body.email.model_dump(),
            microsoft=upsert_body.microsoft.model_dump(),
            odoo=upsert_body.odoo.model_dump(),
            related_people=upsert_body.related_people.model_dump(),
            enabled_sources=upsert_body.enabled_sources,
            allowed_roles=upsert_body.allowed_roles,
            mapping_status=status,
            actor_hash=actor_hash,
        )

    return result


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


# ---------------------------------------------------------------------------
# Phase 2B Slice 7 — Approval Queue + Admin Override
# Implements GET /admin/approvals, GET /admin/approvals/{request_id},
# POST /admin/approvals/{request_id}/override-approve,
# POST /admin/approvals/{request_id}/override-reject
# per docs/execution/PHASE_2B_PLAN.md §E row 7.
# Admin-only via _require_admin.  C-1 / C-6 compliant.  A-10 / R13 enforced.
# ---------------------------------------------------------------------------


class ApprovalQueueItem(BaseModel):
    model_config = {"extra": "forbid"}
    request_id: str
    project_code: str | None
    review_state: str
    quality_gate_status: str | None
    submitted_at: str
    requester_hash: str | None
    cost_total_usd: float


class ApprovalQueueResponse(BaseModel):
    model_config = {"extra": "forbid"}
    items: list[ApprovalQueueItem]
    total: int
    limit: int
    offset: int


class ApprovalQueueDetail(BaseModel):
    model_config = {"extra": "forbid"}
    request_id: str
    project_code: str | None
    review_state: str
    quality_gate_status: str | None
    submitted_at: str
    requester_hash: str | None
    cost_total_usd: float
    token_counts: dict[str, int] | None
    requires_approval: bool
    quality_gate_flags: list[str]


class AdminOverrideRequest(BaseModel):
    model_config = {"extra": "forbid"}
    comment: str = Field(min_length=1)


class AdminOverrideResponse(BaseModel):
    model_config = {"extra": "forbid"}
    request_id: str
    action: str
    new_state: str


@app.get("/admin/approvals")
async def list_approval_queue(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
    project_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApprovalQueueResponse:
    """Admin-only paginated approval queue.

    Returns reports with review_state='staging' and quality_gate != 'failed'.
    Both external 'staging' and 'needs_review' states are included (A-09).
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    rows, total = await pg.list_approval_queue(
        project_code=project_code,
        limit=limit,
        offset=offset,
    )
    items = [
        ApprovalQueueItem(
            request_id=str(r["request_id"]),
            project_code=r.get("project_code"),
            review_state=_derive_external_state(r),
            quality_gate_status=r.get("quality_gate_status"),
            submitted_at=_ts_iso(r["created_at"]),
            requester_hash=r.get("user_id_hash"),
            cost_total_usd=float(r.get("cost_total_usd") or 0.0),
        )
        for r in rows
    ]
    return ApprovalQueueResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/admin/approvals/{request_id}")
async def get_approval_queue_item(
    request_id: str,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> ApprovalQueueDetail:
    """Admin-only single approval-queue item detail.

    404 if absent. 409 if not in approval queue (already finalized or failed).
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found")
    state = _derive_external_state(audit)
    if state not in {"staging", "needs_review"}:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not in the approval queue (current state: {state}).",
        )
    qg_result = _load_json_artifact(request_id, "quality-gate-result.json", "staging")
    flags = _quality_gate_flags(qg_result)
    token_counts_raw = audit.get("token_counts")
    token_counts: dict[str, int] | None = None
    if token_counts_raw:
        try:
            token_counts = dict(token_counts_raw) if isinstance(token_counts_raw, dict) else None
        except Exception:
            token_counts = None
    return ApprovalQueueDetail(
        request_id=str(audit["request_id"]),
        project_code=audit.get("project_code"),
        review_state=state,
        quality_gate_status=audit.get("quality_gate_status"),
        submitted_at=_ts_iso(audit["created_at"]),
        requester_hash=audit.get("user_id_hash"),
        cost_total_usd=float(audit.get("cost_total_usd") or 0.0),
        token_counts=token_counts,
        requires_approval=bool(audit.get("requires_approval", True)),
        quality_gate_flags=flags,
    )


@app.post("/admin/approvals/{request_id}/override-approve")
async def admin_override_approve(
    request_id: str,
    body: AdminOverrideRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> AdminOverrideResponse:
    """Admin-only override approval of a pending report.

    A-10: self-approval is blocked.  N-1: audit event before action.
    Calls node_17_publish to finalize the report.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found")
    reviewer_hash = hash_user_id(claims.user_id) if claims else ""
    if reviewer_hash == audit.get("user_id_hash", ""):
        raise HTTPException(status_code=403, detail="Self-approval is not allowed.")
    state = _derive_external_state(audit)
    if state not in {"staging", "needs_review"}:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not in the approval queue (current state: {state}).",
        )
    # N-1 audit-before-action
    await pg.insert_admin_event(
        event_type="report.admin_override_approved",
        actor_hash=reviewer_hash,
        project_code=audit.get("project_code"),
        detail=f"request_id={request_id}",
    )
    await pg.insert_review_decision(
        request_id=request_id,
        reviewer_id_hash=reviewer_hash,
        action="admin_override",
        comment=body.comment,
    )
    await pg.update_review_state(request_id, "approved")
    # Publish to final
    publish_state = await node_17_publish.run(
        DecisionState(
            request_id=request_id,
            user_id=claims.user_id if claims else "",
            role=claims.role if claims else "",
            project_code=audit.get("project_code") or None,
            query=audit.get("query") or "",
        )
    )
    return AdminOverrideResponse(
        request_id=request_id,
        action="admin_override_approved",
        new_state="approved" if publish_state else "approved",
    )


@app.post("/admin/approvals/{request_id}/override-reject")
async def admin_override_reject(
    request_id: str,
    body: AdminOverrideRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> AdminOverrideResponse:
    """Admin-only override rejection of a pending report.

    A-10: self-rejection is blocked.  N-1: audit event before action.
    Does NOT call node_17_publish.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()
    audit = await pg.get_audit(request_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Report not found")
    reviewer_hash = hash_user_id(claims.user_id) if claims else ""
    if reviewer_hash == audit.get("user_id_hash", ""):
        raise HTTPException(status_code=403, detail="Self-rejection is not allowed.")
    state = _derive_external_state(audit)
    if state not in {"staging", "needs_review"}:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not in the approval queue (current state: {state}).",
        )
    # N-1 audit-before-action
    await pg.insert_admin_event(
        event_type="report.admin_override_rejected",
        actor_hash=reviewer_hash,
        project_code=audit.get("project_code"),
        detail=f"request_id={request_id}",
    )
    await pg.insert_review_decision(
        request_id=request_id,
        reviewer_id_hash=reviewer_hash,
        action="admin_override",
        comment=body.comment,
    )
    await pg.update_review_state(request_id, "rejected")
    return AdminOverrideResponse(
        request_id=request_id,
        action="admin_override_rejected",
        new_state="rejected",
    )


# Phase 2B Slice 8 — Dashboard

class DashboardServiceStatus(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    display_name: str
    status: str   # "ok", "error", "unknown"


class DashboardSummary(BaseModel):
    model_config = {"extra": "forbid"}
    services_ok: int
    services_total: int
    approvals_pending: int
    daily_cost: float
    daily_cap: float
    daily_percent: float
    requests_today: int
    failed_qg_today: int
    monthly_cost: float
    monthly_cap: float
    monthly_percent: float
    services: list[DashboardServiceStatus]
    recent_events: list[AuditEventSummary]   # reuse existing model; last 10
    checked_at: str                          # ISO-8601; A-02


@app.get("/admin/dashboard/summary", response_model=DashboardSummary)
async def admin_dashboard_summary(
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> DashboardSummary:
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()

    # 1. Service health probes
    svc_statuses: list[DashboardServiceStatus] = []
    for name, svc in services_catalog.SERVICE_REGISTRY.items():
        status, _ = _probe_with_latency(name)
        svc_statuses.append(DashboardServiceStatus(
            name=name,
            display_name=svc.display_name,
            status=status,
        ))
    services_ok = sum(1 for s in svc_statuses if s.status == "ok")

    # 2. Approval queue count
    try:
        _, approvals_pending = await pg.list_approval_queue(limit=1, offset=0)
    except Exception:
        approvals_pending = 0

    # 3. Cost data
    from apps.edr.llm import _cost_tracker
    daily_cost = _cost_tracker.daily_cost
    daily_cap = settings.daily_cost_cap_usd
    daily_percent = round((daily_cost / daily_cap * 100), 2) if daily_cap > 0 else 0.0
    try:
        monthly_cost = await pg.monthly_cost_aggregate()
    except Exception:
        monthly_cost = 0.0
    monthly_cap = settings.monthly_cost_target_usd
    monthly_percent = (
        round((monthly_cost / monthly_cap * 100), 2) if monthly_cap > 0 else 0.0
    )

    # 4. Today's request counts
    try:
        counts = await pg.dashboard_counts_today()
        requests_today = counts["requests_today"]
        failed_qg_today = counts["failed_qg_today"]
    except Exception:
        requests_today = 0
        failed_qg_today = 0

    # 5. Recent events (last 10)
    try:
        rows, _ = await pg.list_audit_events(limit=10, offset=0)
    except Exception:
        rows = []
    recent: list[AuditEventSummary] = [
        AuditEventSummary(
            event_id=str(r.get("event_id", "")),
            event_type=str(r.get("event_type", "")),
            ts=_ts_iso(r["ts"]) if r.get("ts") else "",
            user_id_hash=r.get("user_id_hash"),
            project_code=r.get("project_code"),
            service=r.get("service"),
            detail=str(r.get("detail") or ""),
        )
        for r in rows
    ]

    return DashboardSummary(
        services_ok=services_ok,
        services_total=len(svc_statuses),
        approvals_pending=approvals_pending,
        daily_cost=daily_cost,
        daily_cap=daily_cap,
        daily_percent=daily_percent,
        requests_today=requests_today,
        failed_qg_today=failed_qg_today,
        monthly_cost=monthly_cost,
        monthly_cap=monthly_cap,
        monthly_percent=monthly_percent,
        services=svc_statuses,
        recent_events=recent,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Microsoft Mapping Rescan — admin read-only Graph discovery + confirm.
# POST /admin/microsoft-mapping/rescan
# POST /admin/microsoft-mapping/{code}/confirm
# Admin-only via _require_admin.  C-1/C-6 compliant.  A-21 audit-before-save.
# Read-only Microsoft Graph: no writes to SharePoint, Mail, or other Graph API.
# ---------------------------------------------------------------------------

from apps.edr.admin.microsoft_rescan import (  # noqa: E402
    MicrosoftRescanResponse,
    _is_placeholder_site,
    run_microsoft_rescan,
)


class MicrosoftRescanRequest(BaseModel):
    model_config = {"extra": "forbid"}
    project_codes: list[str] = []  # empty list = scan all projects


class MicrosoftMappingConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}
    site_id: str = Field(min_length=1)
    drive_id: str = Field(min_length=1)
    root_path: str = ""
    mailboxes: list[str] = []
    document_control_mailbox: str = ""


@app.post("/admin/microsoft-mapping/rescan")
async def rescan_microsoft_mapping(
    body: MicrosoftRescanRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> MicrosoftRescanResponse:
    """Admin-only: read-only Microsoft Graph discovery for all or selected projects.

    Discovers SharePoint sites, drives, and mailboxes and scores them against
    existing source mappings.  Returns candidates; does NOT write to the database.
    A-21: audit event emitted before the scan begins.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()

    import json as _json

    def _j(val: Any) -> Any:
        return _json.loads(val) if isinstance(val, str) else (val or {})

    rows = await pg.list_source_mappings()
    projects = []
    for row in rows:
        code = str(row["project_code"])
        if body.project_codes and code not in body.project_codes:
            continue
        projects.append({
            "project_code": code,
            "project_name": str(row.get("project_name") or ""),
            "sharepoint": _j(row.get("sharepoint")),
            "email": _j(row.get("email")),
            "mapping_status": str(row.get("mapping_status") or "incomplete"),
        })

    actor_hash = hash_user_id(claims.user_id) if claims else ""
    scope = ",".join(body.project_codes) if body.project_codes else "all"
    await pg.insert_admin_event(
        event_type="admin.microsoft_rescan_run",
        actor_hash=actor_hash,
        project_code=None,
        detail=f"scope={scope} projects={len(projects)}",
    )

    return await run_microsoft_rescan(projects)


@app.post("/admin/microsoft-mapping/{code}/confirm")
async def confirm_microsoft_mapping(
    code: str,
    body: MicrosoftMappingConfirmRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> SourceMappingDetail:
    """Admin-only: apply a confirmed site_id/drive_id to a source mapping.

    Safety: refuses to overwrite a confirmed (non-placeholder) site_id with a
    different value — use PUT /admin/source-mappings/{code} for full override.
    A-21: audit event before the database write.
    """
    _require_admin(claims)
    pg = get_postgres_store()
    await pg.init_schema()

    row = await pg.get_source_mapping(code)
    if row is None:
        raise HTTPException(status_code=404, detail="Mapping not found")

    existing = _row_to_source_mapping_detail(row)
    existing_site_id = existing.sharepoint.site_id

    if not _is_placeholder_site(existing_site_id) and existing_site_id != body.site_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "Mapping already has a confirmed site_id different from the candidate. "
                f"Use PUT /admin/source-mappings/{code} to perform a full override."
            ),
        )

    new_root_path = body.root_path or existing.sharepoint.root_path or "/"
    new_sp = SourceMappingSharePoint(
        site_id=body.site_id,
        drive_id=body.drive_id,
        root_path=new_root_path,
    )
    new_em = SourceMappingEmail(
        shared_mailboxes=body.mailboxes if body.mailboxes else existing.email.shared_mailboxes,
        document_control_mailbox=(
            body.document_control_mailbox or existing.email.document_control_mailbox
        ),
        client_domains=existing.email.client_domains,
        consultant_domains=existing.email.consultant_domains,
        contractor_domains=existing.email.contractor_domains,
    )

    upsert_body = SourceMappingUpsertRequest(
        project_name=existing.project_name,
        contract_numbers=existing.contract_numbers,
        sharepoint=new_sp,
        owncloud=existing.owncloud,
        email=new_em,
        microsoft=existing.microsoft,
        odoo=existing.odoo,
        related_people=existing.related_people,
        enabled_sources=existing.enabled_sources,
        allowed_roles=existing.allowed_roles,
    )
    status, _ = _compute_mapping_status(code, upsert_body)

    actor_hash = hash_user_id(claims.user_id) if claims else ""
    await pg.insert_admin_event(
        event_type="admin.microsoft_mapping_confirmed",
        actor_hash=actor_hash,
        project_code=code,
        detail=f"status={status} site=[REDACTED] drive=[REDACTED]",
    )
    await pg.upsert_source_mapping(
        project_code=code,
        project_name=upsert_body.project_name,
        contract_numbers=upsert_body.contract_numbers,
        sharepoint=new_sp.model_dump(),
        owncloud=upsert_body.owncloud.model_dump(),
        email=new_em.model_dump(),
        microsoft=upsert_body.microsoft.model_dump(),
        odoo=upsert_body.odoo.model_dump(),
        related_people=upsert_body.related_people.model_dump(),
        enabled_sources=upsert_body.enabled_sources,
        allowed_roles=upsert_body.allowed_roles,
        mapping_status=status,
        actor_hash=actor_hash,
    )

    updated = await pg.get_source_mapping(code)
    if updated is None:
        raise HTTPException(status_code=500, detail="Confirm failed.")
    return _row_to_source_mapping_detail(updated)
