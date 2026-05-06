from typing import Literal

from pydantic import BaseModel, Field


class SummaryClaim(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class FinancialValue(BaseModel):
    value: float | None = None
    currency: str = "AED"
    evidence_id: str | None = None
    status: Literal["available", "not_available"] = "not_available"


class FinancialVariance(BaseModel):
    value: float | None = None
    currency: str = "AED"
    formula: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class FinancialSnapshot(BaseModel):
    budget: FinancialValue = Field(default_factory=FinancialValue)
    actual_cost: FinancialValue = Field(default_factory=FinancialValue)
    variance: FinancialVariance = Field(default_factory=FinancialVariance)


class FindingItem(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class ConflictItem(BaseModel):
    conflict_type: str
    description: str
    source_a_ref: str
    source_b_ref: str
    confidence_a: Literal["high", "medium", "low"] = "medium"
    confidence_b: Literal["high", "medium", "low"] = "medium"


class SourceEntry(BaseModel):
    source_id: str
    source_type: Literal["sharepoint", "owncloud", "email", "odoo", "cad"]
    title: str
    reference: str
    date: str | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    used_in: list[str] = Field(default_factory=list)


class ExecutiveDecisionReport(BaseModel):
    """Canonical internal JSON report. All export formats derive from this model.

    Spec: Section 14 (schema-first), Section 29 (output structure).
    """

    request_id: str
    project_code: str | None = None
    query: str
    language: str = "en"
    executive_summary: list[SummaryClaim] = Field(default_factory=list)
    financial_snapshot: FinancialSnapshot = Field(default_factory=FinancialSnapshot)
    key_findings: list[FindingItem] = Field(default_factory=list)
    root_causes: list[FindingItem] = Field(default_factory=list)
    delay_analysis: list[FindingItem] = Field(default_factory=list)
    contractual_implications: list[FindingItem] = Field(default_factory=list)
    recommended_actions: list[FindingItem] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    conflicts: list[ConflictItem] = Field(default_factory=list)
    sources: list[SourceEntry] = Field(default_factory=list)
    quality_gate_status: Literal["passed", "failed", "needs_review", "not_run"] = "not_run"
