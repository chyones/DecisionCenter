from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionState:
    request_id: str
    user_id: str
    query: str
    # RBAC fields — set by API layer (JWT) or directly in tests
    role: str | None = None
    project_code: str | None = None
    allowed_projects: list[str] = field(default_factory=list)
    allowed_mailboxes: list[str] = field(default_factory=list)
    allowed_odoo_ids: list[str] = field(default_factory=list)
    # Workflow state
    inputs: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    visited_nodes: list[str] = field(default_factory=list)
    output_formats: list[str] = field(default_factory=lambda: ["md"])
    report_json: dict[str, Any] | None = None
    # Phase 1E — cost and loop tracking
    cost_accumulated_usd: float = 0.0
    loop_count: int = 0

    def mark(self, node_name: str) -> "DecisionState":
        self.visited_nodes.append(node_name)
        return self
