from typing import Literal, Union

from pydantic import BaseModel, Field

# Allowed metadata value types: scalars (str/int/float/bool/None) and lists of scalars.
# The n8n email workflow returns ``recipients`` as a list of strings; the SharePoint
# workflow returns scalar fields. Both shapes must validate cleanly.
_MetadataScalar = Union[str, int, float, bool, None]
_MetadataValue = Union[_MetadataScalar, list[_MetadataScalar]]


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
    metadata: dict[str, _MetadataValue] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    request_id: str
    evidence: list[EvidenceObject] = Field(default_factory=list)
