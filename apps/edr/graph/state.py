from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionState:
    request_id: str
    user_id: str
    query: str
    inputs: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    visited_nodes: list[str] = field(default_factory=list)

    def mark(self, node_name: str) -> "DecisionState":
        self.visited_nodes.append(node_name)
        return self
