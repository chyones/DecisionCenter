"""Per-source connector coverage tracking for project reports.

A project report must always *attempt* every source enabled for the project
(Odoo, SharePoint, Email) and must surface the outcome of each attempt — never
silently drop a source that returned zero evidence. Each retrieval node records
a coverage entry here; node_12 renders it into the report and node_13 uses it to
distinguish *partial* from *full* evidence.

Status vocabulary (controlled):
- ``ok``            attempted, >=1 evidence item
- ``zero_no_match`` attempted, connector healthy, 0 evidence (e.g. no documents matched)
- ``error``         attempted, connector failed (HTTP / transport error)
- ``blocked``       not attempted; a documented operator/tenant blocker prevents it
- ``rbac_denied``   not attempted; caller's role/allowlist forbids it
- ``not_enabled``   source is not in the project's enabled_sources
"""

from __future__ import annotations

from typing import Any

#: Sources that a project report must always consider.
PROJECT_SOURCES: tuple[str, ...] = ("odoo", "sharepoint", "email")

def record(
    state: Any,
    source: str,
    *,
    enabled: bool,
    attempted: bool,
    status: str,
    evidence_count: int = 0,
    reason: str = "",
) -> None:
    """Record the coverage outcome for one source on ``state.outputs``."""
    cov = state.outputs.setdefault("source_coverage", {})
    cov[source] = {
        "enabled": bool(enabled),
        "attempted": bool(attempted),
        "status": status,
        "evidence_count": int(evidence_count),
        "reason": reason,
    }


def summary(state: Any) -> dict[str, Any]:
    """Compute the coverage summary used by the report and the quality gate.

    Returns a dict with per-source entries plus aggregate flags:
      - ``completeness``: "full" | "partial" | "none_enabled"
      - ``all_enabled_attempted``: every enabled source was attempted or blocked
      - ``connector_errors``: list of enabled sources whose status is ``error``
      - ``zero_evidence_sources``: enabled sources that returned zero evidence
    """
    cov: dict[str, dict] = dict(state.outputs.get("source_coverage", {}))
    # Ensure every project source has an entry so nothing is silently missing.
    for src in PROJECT_SOURCES:
        cov.setdefault(
            src,
            {"enabled": False, "attempted": False, "status": "not_enabled",
             "evidence_count": 0, "reason": "Source produced no coverage record."},
        )

    enabled = [s for s in PROJECT_SOURCES if cov[s].get("enabled")]
    zero_evidence = [
        s for s in enabled if (cov[s].get("evidence_count") or 0) == 0
    ]
    connector_errors = [s for s in enabled if cov[s].get("status") == "error"]
    # "attempted", "blocked" (documented operator/tenant blocker) and
    # "rbac_denied" (legitimate role restriction) all satisfy the coverage
    # obligation; only a silent non-attempt is a coverage failure.
    _documented_skips = {"blocked", "rbac_denied"}
    not_attempted = [
        s for s in enabled
        if not cov[s].get("attempted") and cov[s].get("status") not in _documented_skips
    ]

    if not enabled:
        completeness = "none_enabled"
    elif all((cov[s].get("evidence_count") or 0) > 0 for s in enabled):
        completeness = "full"
    else:
        completeness = "partial"

    return {
        "sources": cov,
        "completeness": completeness,
        "all_enabled_attempted": not not_attempted,
        "connector_errors": connector_errors,
        "zero_evidence_sources": zero_evidence,
        "not_attempted_sources": not_attempted,
    }


def report_section(state: Any) -> list[dict[str, Any]]:
    """Build the ordered connector_coverage list embedded in the report JSON."""
    cov = summary(state)["sources"]
    section: list[dict[str, Any]] = []
    for src in PROJECT_SOURCES:
        e = cov[src]
        section.append({
            "source": src,
            "enabled": e.get("enabled", False),
            "attempted": e.get("attempted", False),
            "evidence_count": e.get("evidence_count", 0),
            "status": e.get("status", "not_enabled"),
            "reason": e.get("reason", ""),
        })
    return section
