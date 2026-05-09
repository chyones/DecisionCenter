"""Audit schemas. Spec: Section 30."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    timestamp: str
    node: str
    action: str
    status: str
    details: dict[str, object] = Field(default_factory=dict)


class AuditLog(BaseModel):
    request_id: str
    user_id_hash: str
    events: list[AuditEvent] = Field(default_factory=list)


class AuditArtifact(BaseModel):
    """Shape of the audit-log.json artifact persisted to MinIO.

    Mirrors Section 30 of the spec but stores user_id_hash instead of raw user_id
    and omits full confidential source content.
    """

    request_id: str
    user_id_hash: str
    timestamp: str
    query: str
    detected_language: str = "en"
    authorized_projects: list[str] = Field(default_factory=list)
    authorized_mailboxes: list[str] = Field(default_factory=list)
    blocked_sources: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    tool_budgets_used: dict[str, int] = Field(default_factory=dict)
    retrieval_loops: int = 0
    quality_gate_status: str = "needs_review"
    final_status: str = "staging"
    token_counts: dict[str, int] = Field(default_factory=dict)
    cost_total_usd: float = 0.0
    artifact_keys: list[str] = Field(default_factory=list)
