from typing import Any, Literal

from pydantic import BaseModel, Field


class SummaryClaim(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class FinancialValue(BaseModel):
    value: float | None = None
    currency: str = "AED"
    evidence_id: str | None = None
    status: Literal["available", "not_available", "inconclusive"] = "not_available"


class FinancialVariance(BaseModel):
    value: float | None = None
    currency: str = "AED"
    formula: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class FinancialSnapshot(BaseModel):
    """Distinct project financial figures — never merged into one number.

    Each figure is sourced and evidence-bound independently:
    - budget: legacy field; not present as an Odoo column (kept not_available).
    - contract_value: project.project wo_amount (work-order/contract value).
    - estimate: project.project estimation_amount.
    - actual_cost: posted account.analytic.line / account.move.line cost total.
    - payroll_cost: project payroll / staff cost (hr.payslip.cost.allocation).
    - expense_cost: HR expenses — petty cash, vehicle, fuel (hr.expense).
    - committed_cost: purchase orders / PO lines (open commitments).
    - total_incurred: sum of evidence-backed incurred cost categories (see note).
    - variance: derived comparison (only when its inputs are evidence-bound).
    Labour/supplier/invoice detail is surfaced as findings, not collapsed here.
    """

    budget: FinancialValue = Field(default_factory=FinancialValue)
    contract_value: FinancialValue = Field(default_factory=FinancialValue)
    estimate: FinancialValue = Field(default_factory=FinancialValue)
    actual_cost: FinancialValue = Field(default_factory=FinancialValue)
    payroll_cost: FinancialValue = Field(default_factory=FinancialValue)
    expense_cost: FinancialValue = Field(default_factory=FinancialValue)
    committed_cost: FinancialValue = Field(default_factory=FinancialValue)
    total_incurred: FinancialValue = Field(default_factory=FinancialValue)
    variance: FinancialVariance = Field(default_factory=FinancialVariance)
    note: str | None = None


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


class BusinessImpact(BaseModel):
    schedule_impact: str = ""
    cost_commercial_impact: str = ""
    operational_client_impact: str = ""


class RecommendedActionDetail(BaseModel):
    specific_action: str = ""
    owner_role: str = ""
    timeframe: str = ""


class ManagementQuestionAnswer(BaseModel):
    """Executive decision-memo answer to a focused management question.

    Used when the query asks for a decision, a single biggest problem,
    or a recommendation.  Populated by node_12 and validated by the
    quality gate.
    """

    executive_answer: str = ""
    why_biggest_problem: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    business_impact: BusinessImpact = Field(default_factory=BusinessImpact)
    decision_required: str = ""
    recommended_action: RecommendedActionDetail = Field(default_factory=RecommendedActionDetail)
    risks_if_no_action: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    missing_evidence_or_assumptions: str = ""


class ProjectIdentity(BaseModel):
    """Verified real project identity used in every report/export/fallback."""

    project_code: str
    project_name: str
    identity_source: str
    identity_confidence: Literal["verified", "partial", "not_verified"] = "not_verified"
    missing_identity_evidence: list[str] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)


class ExecutiveDecisionReport(BaseModel):
    """Canonical internal JSON report. All export formats derive from this model.

    Spec: Section 14 (schema-first), Section 29 (output structure).
    """

    request_id: str
    project_code: str | None = None
    project_identity: ProjectIdentity = Field(default_factory=ProjectIdentity)
    query: str
    language: str = "en"
    executive_summary: list[SummaryClaim] = Field(default_factory=list)
    financial_snapshot: FinancialSnapshot = Field(default_factory=FinancialSnapshot)
    key_findings: list[FindingItem] = Field(default_factory=list)
    root_causes: list[FindingItem] = Field(default_factory=list)
    delay_analysis: list[FindingItem] = Field(default_factory=list)
    contractual_implications: list[FindingItem] = Field(default_factory=list)
    recommended_actions: list[FindingItem] = Field(default_factory=list)
    management_question_answer: ManagementQuestionAnswer = Field(
        default_factory=ManagementQuestionAnswer
    )
    missing_data: list[str] = Field(default_factory=list)
    conflicts: list[ConflictItem] = Field(default_factory=list)
    sources: list[SourceEntry] = Field(default_factory=list)
    quality_gate_status: Literal["passed", "failed", "needs_review", "not_run"] = "not_run"
    report_type: str = "executive_decision"
    connector_coverage: list[dict[str, Any]] = Field(default_factory=list)
    what_was_checked: list[str] = Field(default_factory=list)
    required_data: list[str] = Field(default_factory=list)
