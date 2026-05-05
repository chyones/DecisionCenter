from fastapi import FastAPI
from pydantic import BaseModel, Field

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
    )
    result = run_workflow(state)
    return {
        "request_id": result.request_id,
        "status": "stubbed",
        "visited_nodes": result.visited_nodes,
        "message": "Skeleton workflow executed. Connectors and LLM calls are not enabled yet.",
    }
