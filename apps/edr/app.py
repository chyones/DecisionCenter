import socket
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
from apps.edr.rbac.project_mapping import RbacDeniedError

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


@app.post("/reports/staging")
def stage_report(
    request: ReportRequest,
    claims: Annotated[JWTClaims | None, Depends(_extract_claims)],
) -> dict[str, object]:
    user_id = (claims.user_id if claims and claims.user_id else None) or request.user_id
    role = claims.role if claims else None

    state = DecisionState(
        request_id="local-preview",
        user_id=user_id,
        role=role,
        project_code=request.project_code,
        query=request.query,
        inputs=request.model_dump(exclude_none=True),
        output_formats=list(request.output_formats),
    )
    try:
        result = run_workflow(state)
    except RbacDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    exports = result.outputs.get("exported_reports", {})
    return {
        "request_id": result.request_id,
        "status": "stubbed",
        "visited_nodes": result.visited_nodes,
        "exported_formats": list(exports.keys()),
        "exports": exports,
        "message": "Skeleton workflow executed. Connectors and LLM calls are not enabled yet.",
    }


@app.get("/reports/staging/{request_id}/download/{fmt}")
def download_report(request_id: str, fmt: str) -> Response:
    """Download a specific format of a staged report.

    In stub mode reports are not persisted; returns 404.
    Real implementation will fetch from MinIO at /staging/{request_id}/.
    """
    if fmt not in MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}")
    raise HTTPException(
        status_code=404,
        detail="Report not found. Persistence is not yet implemented in stub mode.",
    )
