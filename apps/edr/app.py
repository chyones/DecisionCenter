from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from apps.edr.exporters.base import MIME_TYPES
from apps.edr.graph.runner import NODE_COUNT, run_workflow
from apps.edr.graph.state import DecisionState

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


@app.get("/healthz")
def healthz() -> dict[str, str | int]:
    return {"status": "ok", "workflow_nodes": NODE_COUNT}


@app.post("/reports/staging")
def stage_report(request: ReportRequest) -> dict[str, object]:
    state = DecisionState(
        request_id="local-preview",
        user_id=request.user_id,
        query=request.query,
        inputs=request.model_dump(exclude_none=True),
        output_formats=list(request.output_formats),
    )
    result = run_workflow(state)
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
