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
