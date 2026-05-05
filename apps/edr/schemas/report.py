from pydantic import BaseModel, Field


class ReportClaim(BaseModel):
    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "unchecked"


class ExecutiveDecisionReport(BaseModel):
    request_id: str
    question: str
    executive_summary: str
    recommendation: str | None = None
    financials: dict[str, object] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    claims: list[ReportClaim] = Field(default_factory=list)
