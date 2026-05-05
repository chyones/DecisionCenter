from typing import Literal

from pydantic import BaseModel, Field


class EvidenceObject(BaseModel):
    evidence_id: str
    source_type: Literal["sharepoint", "owncloud", "email", "odoo", "cad"]
    source_uri: str
    title: str
    project_code: str | None = None
    contract_no: str | None = None
    revision: str | None = None
    timestamp: str | None = None
    excerpt: str
    hash_sha256: str
    confidence: Literal["high", "medium", "low"]
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    request_id: str
    evidence: list[EvidenceObject] = Field(default_factory=list)
