"""Global Project Identity Contract.

Resolves and validates the real business project name once, after project/context
resolution, and propagates it to every downstream report, export, and fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping


ProjectIdentityConfidence = Literal["verified", "partial", "not_verified"]


@dataclass
class ProjectIdentity:
    """Canonical project identity object used across JSON, Markdown, PDF, etc."""

    project_code: str
    project_name: str
    identity_source: str
    identity_confidence: ProjectIdentityConfidence
    missing_identity_evidence: list[str] = field(default_factory=list)
    conflict_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectIdentity":
        return cls(
            project_code=data.get("project_code", ""),
            project_name=data.get("project_name", ""),
            identity_source=data.get("identity_source", ""),
            identity_confidence=data.get("identity_confidence", "not_verified"),
            missing_identity_evidence=list(data.get("missing_identity_evidence", [])),
            conflict_notes=list(data.get("conflict_notes", [])),
        )


def _is_verified_mapping(mapping: dict) -> bool:
    method = mapping.get("mapping_method", "")
    status = mapping.get("mapping_status_gate", "")
    return bool("VERIFIED" in method or status in ("EMAIL_GROUP_ENRICHED", "COMPLETE"))


def _extract_odoo_project_name(evidence: list[dict]) -> tuple[str, str] | None:
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        if ev.get("source_type") != "odoo":
            continue
        uri = str(ev.get("source_uri", "")).lower()
        if "project.project" not in uri:
            continue
        # Prefer title, then a clean excerpt line.
        name = (ev.get("title") or "").strip()
        if name and name.lower() not in ("odoo record", "odoo project record"):
            return ("odoo project.project", name)
        excerpt = (ev.get("excerpt") or "").strip()
        if excerpt:
            # Excerpt may be multi-field; take first non-empty line.
            for line in excerpt.splitlines():
                line = line.strip()
                if line:
                    return ("odoo project.project", line)
    return None


def _extract_sharepoint_project_name(evidence: list[dict]) -> tuple[str, str] | None:
    # Prefer the first SharePoint item title that is not a filename/path slug.
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        if ev.get("source_type") != "sharepoint":
            continue
        title = (ev.get("title") or "").strip()
        if title and "/" not in title and "\\" not in title:
            return ("sharepoint displayName", title)
    return None


def resolve_project_identity(state: DecisionState) -> ProjectIdentity:
    """Resolve the verified real project name from mapping, Odoo, or SharePoint.

    Never guesses or derives the name from URL slugs.
    """
    code = state.project_code
    if not code:
        return ProjectIdentity(
            project_code="",
            project_name="Not verified",
            identity_source="none",
            identity_confidence="not_verified",
            missing_identity_evidence=["project_code not provided"],
        )

    mapping: dict = {}
    try:
        mapping = ProjectMapping.load().get(code)
    except Exception:
        pass

    candidates: list[tuple[str, str]] = []
    sources_used: list[str] = []
    missing: list[str] = []

    # 1. Approved source mapping / project registry.
    mapping_verified = _is_verified_mapping(mapping)
    mapping_name = (mapping.get("project_name") or mapping.get("display_name") or "").strip()
    if mapping_name:
        source_label = "approved project registry" if mapping_verified else "source_mappings table"
        candidates.append((source_label, mapping_name))
        sources_used.append(source_label)

    odoo_config = mapping.get("odoo", {}) if isinstance(mapping, dict) else {}
    odoo_mapping_name = (odoo_config.get("project_name") or "").strip()
    if odoo_mapping_name:
        candidates.append(("odoo project.project", odoo_mapping_name))
        sources_used.append("odoo project.project")

    # 2. Evidence already retrieved (if identity is resolved after retrieval).
    evidence = state.evidence if isinstance(state.evidence, list) else []
    odoo_ev_name = _extract_odoo_project_name(evidence)
    if odoo_ev_name:
        candidates.append(odoo_ev_name)
        if "odoo project.project" not in sources_used:
            sources_used.append("odoo project.project")

    sp_ev_name = _extract_sharepoint_project_name(evidence)
    if sp_ev_name:
        candidates.append(sp_ev_name)
        if "sharepoint displayName" not in sources_used:
            sources_used.append("sharepoint displayName")

    if not sources_used:
        missing.extend(["project mapping", "odoo project.project", "sharepoint displayName"])

    # Consolidate: unique names in order of trust.
    seen_names: list[str] = []
    for _, name in candidates:
        if name not in seen_names:
            seen_names.append(name)

    if not seen_names:
        return ProjectIdentity(
            project_code=code,
            project_name="Not verified",
            identity_source="none",
            identity_confidence="not_verified",
            missing_identity_evidence=missing
            or ["project mapping / odoo project / sharepoint displayName"],
        )

    if len(seen_names) == 1:
        return ProjectIdentity(
            project_code=code,
            project_name=seen_names[0],
            identity_source=candidates[0][0],
            identity_confidence="verified" if mapping_verified else "partial",
            missing_identity_evidence=missing,
        )

    # Multiple distinct names -> partial with conflict notes.
    primary_name = seen_names[0]
    primary_source = candidates[0][0]
    conflict_notes = [f"Conflicting project names found: {seen_names}"]
    missing.append("conflict resolution between identity sources")
    return ProjectIdentity(
        project_code=code,
        project_name=primary_name,
        identity_source=f"{primary_source} (conflict)",
        identity_confidence="partial",
        missing_identity_evidence=missing,
        conflict_notes=conflict_notes,
    )
