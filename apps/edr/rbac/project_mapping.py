"""Project source mapping loader. Source: docs/config/project_source_mapping.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Resolved relative to this file: apps/edr/rbac/ -> apps/edr/ -> apps/ -> DecisionCenter/
_DEFAULT_MAPPING_PATH = Path(__file__).parents[3] / "docs" / "config" / "project_source_mapping.json"


class ProjectNotFoundError(ValueError):
    pass


class RbacDeniedError(PermissionError):
    """Raised by node_01_auth when RBAC check fails. API layer converts to HTTP 403."""


class ProjectMapping:
    def __init__(self, mapping: dict[str, dict[str, Any]]) -> None:
        self._mapping = mapping

    @classmethod
    def load(cls, path: Path | None = None) -> "ProjectMapping":
        p = path or _DEFAULT_MAPPING_PATH
        with open(p) as f:
            raw = json.load(f)
        if isinstance(raw, list):
            indexed = {entry["project_code"]: entry for entry in raw}
        elif isinstance(raw, dict):
            indexed = raw
        else:
            raise ValueError("project_source_mapping.json must be a list or object")
        return cls(indexed)

    def get(self, project_code: str) -> dict[str, Any]:
        if project_code not in self._mapping:
            raise ProjectNotFoundError(f"Unknown project_code: {project_code!r}")
        return self._mapping[project_code]

    def allowed_mailboxes(self, project_code: str) -> list[str]:
        entry = self.get(project_code)
        email = entry.get("email", {})
        mailboxes: list[str] = list(email.get("shared_mailboxes", []))
        if dc_mb := email.get("document_control_mailbox"):
            mailboxes.append(dc_mb)
        return mailboxes

    def allowed_odoo_ids(self, project_code: str) -> list[str]:
        entry = self.get(project_code)
        ext_id = entry.get("odoo", {}).get("project_external_id")
        return [ext_id] if ext_id else []
