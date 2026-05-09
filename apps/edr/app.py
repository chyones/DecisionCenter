import socket
import uuid
from typing import Annotated, Literal
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import Depends, FastAPI, Header, HTTPException
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
