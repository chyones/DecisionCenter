from typing import Literal

from pydantic import BaseModel, Field


class ClaimCheck(BaseModel):
    claim_id: str
    verdict: Literal["supported", "unsupported", "needs_review"]
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str


class QualityGateResult(BaseModel):
    request_id: str
    verdict: Literal["passed", "failed", "needs_review"]
    checks: list[ClaimCheck] = Field(default_factory=list)
