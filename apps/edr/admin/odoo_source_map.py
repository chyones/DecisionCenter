"""Odoo Source Map — admin visibility over where DecisionCenter searches in Odoo.

Builds the GENERIC Odoo source map straight from the proven source registry
(`apps/edr/connectors/odoo_sources.py`) and layers each project's RUNTIME values
(Odoo project id + analytic account id, from its saved source mapping) on top.

This module never hardcodes project ids. PRJ-001 / PRJ-002 are audit validation
samples only and carry no special logic here — the same code path runs for any
project that has an Odoo project id and an analytic account id.

The optional scan is strictly read-only: it reuses the same proven, denylist-safe
queries the connector issues and reports per-source record counts. It is fully
independent of report generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from apps.edr.connectors.odoo import build_source_query, read_odoo
from apps.edr.connectors.odoo_sources import (
    DISPLAY_GROUPS,
    ODOO_SOURCES,
    denylisted_path_strings,
    source_map_entries,
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OdooSourceMapEntry(BaseModel):
    model_config = {"extra": "forbid"}
    key: str
    group: str
    groups: list[str]
    source_name: str
    model: str
    link_path: str
    link_scope: str
    key_fields: list[str]
    confidence: str
    gap_type: str
    aggregation: str
    handled_inline: bool
    warning: str
    # Per-project runtime resolution (no project ids baked into logic):
    mappable: bool
    link_value: str | None
    # Per-source scan result (populated only after a scan):
    last_scan_status: str
    record_count: int | None
    capped: bool


class OdooSourceMapResponse(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    generic: bool
    odoo_enabled: bool
    extended_enabled: bool
    odoo_project_id: str | None
    analytic_account_id: str | None
    project_source_status: str
    groups: list[str]
    enabled_categories: list[str]
    sources: list[OdooSourceMapEntry]
    denylisted_paths: list[str]
    missing_sources: list[str]
    notes: list[str]
    last_scanned_at: str | None


class OdooSourceScanResult(BaseModel):
    model_config = {"extra": "forbid"}
    project_code: str
    scanned_at: str
    reachable: bool
    capped_at: int
    counts: dict[str, int]
    statuses: dict[str, str]
    summary: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _numeric(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text.isdigit() else None


def _link_value_for(scope: str, project_id: str | None, analytic_id: str | None) -> str | None:
    return project_id if scope == "project" else analytic_id


GENERIC_NOTES: tuple[str, ...] = (
    "This Source Map is generic: it is built from the Odoo source registry, not "
    "from per-project hardcoded data.",
    "Project values shown here are runtime values read from this project's saved "
    "source mapping.",
    "PRJ-001 and PRJ-002 are audit validation samples only — they are not fixed "
    "logic. Any project with an Odoo project id and an analytic account id works.",
    "Record counts appear only after a read-only scan and are capped by the "
    "deployed Odoo read workflow (search_read limit). True totals require the "
    "structured workflow and an uncapped count.",
    "Denylisted/ambiguous Odoo paths are never queried.",
    "Not a go-live signal.",
)


# ---------------------------------------------------------------------------
# Build (no network)
# ---------------------------------------------------------------------------


def build_source_map(
    *,
    project_code: str,
    odoo_config: dict[str, Any],
    mapping_status: str,
    odoo_enabled: bool,
    extended_enabled: bool,
    scan: OdooSourceScanResult | None = None,
) -> OdooSourceMapResponse:
    """Compose the per-project Source Map from the generic registry + runtime ids."""
    project_id = _numeric(odoo_config.get("project_external_id"))
    analytic_id = _numeric(odoo_config.get("analytic_account_id"))

    generic = source_map_entries()
    entries: list[OdooSourceMapEntry] = []
    enabled_categories: set[str] = set()
    missing_sources: list[str] = []

    counts = scan.counts if scan else {}
    statuses = scan.statuses if scan else {}

    for g in generic:
        scope = g["link_scope"]
        link_value = _link_value_for(scope, project_id, analytic_id)
        mappable = bool(odoo_enabled and link_value is not None)

        warnings = g["warning"]
        if not mappable:
            missing_sources.append(g["key"])

        record_count = counts.get(g["key"])
        last_scan_status = statuses.get(g["key"], "not_scanned")
        capped = record_count is not None and record_count >= 100

        if mappable:
            for grp in g["groups"]:
                enabled_categories.add(grp)

        entries.append(
            OdooSourceMapEntry(
                key=g["key"],
                group=g["group"],
                groups=g["groups"],
                source_name=g["source_name"],
                model=g["model"],
                link_path=g["link_path"],
                link_scope=scope,
                key_fields=g["key_fields"],
                confidence=g["confidence"],
                gap_type=g["gap_type"],
                aggregation=g["aggregation"],
                handled_inline=g["handled_inline"],
                warning=warnings,
                mappable=mappable,
                link_value=link_value,
                last_scan_status=last_scan_status,
                record_count=record_count,
                capped=capped,
            )
        )

    notes = list(GENERIC_NOTES)
    if not odoo_enabled:
        notes.append("Odoo is not in this project's enabled sources — all sources are disabled.")
    if project_id is None:
        notes.append("Odoo project id is not set on this mapping — project-scoped sources cannot run.")
    if analytic_id is None:
        notes.append("Analytic account id is not set on this mapping — analytic-scoped sources cannot run.")
    if not extended_enabled:
        notes.append(
            "Extended multi-source retrieval is OFF (ODOO_EXTENDED_SOURCES_ENABLED). "
            "Report generation currently uses only project identity + actual cost."
        )

    ordered_categories = [g for g in DISPLAY_GROUPS if g in enabled_categories]

    return OdooSourceMapResponse(
        project_code=project_code,
        generic=True,
        odoo_enabled=odoo_enabled,
        extended_enabled=extended_enabled,
        odoo_project_id=project_id,
        analytic_account_id=analytic_id,
        project_source_status=mapping_status,
        groups=list(DISPLAY_GROUPS),
        enabled_categories=ordered_categories,
        sources=entries,
        denylisted_paths=denylisted_path_strings(),
        missing_sources=missing_sources,
        notes=notes,
        last_scanned_at=scan.scanned_at if scan else None,
    )


# ---------------------------------------------------------------------------
# Scan (read-only, live)
# ---------------------------------------------------------------------------


async def scan_source_counts(
    *,
    project_code: str,
    odoo_config: dict[str, Any],
    allowed_odoo_ids: list[str],
) -> OdooSourceScanResult:
    """Read-only per-source record-count scan via the existing n8n Odoo webhook.

    Every source is isolated: one failing/unmappable source never aborts the
    others. No writes, ever. Counts are capped by the deployed workflow.
    """
    counts: dict[str, int] = {}
    statuses: dict[str, str] = {}
    reachable = False
    any_attempted = False

    for source in ODOO_SOURCES:
        query = build_source_query(source, odoo_config)
        if query is None:
            statuses[source.key] = "unmapped"
            continue
        model, domain, fields, limit = query
        payload = {
            "project_code": project_code,
            "model": model,
            "domain": domain,
            "fields": fields,
            "limit": limit,
            "allowed_odoo_ids": allowed_odoo_ids,
        }
        any_attempted = True
        try:
            evidence = await read_odoo(payload)
        except Exception as exc:  # noqa: BLE001 - record, never raise
            statuses[source.key] = f"error: {type(exc).__name__}"
            continue
        reachable = True
        count = len(evidence)
        counts[source.key] = count
        if count >= 100:
            statuses[source.key] = "capped"
        elif count > 0:
            statuses[source.key] = "ok"
        else:
            statuses[source.key] = "empty"

    if not any_attempted:
        summary = "No mappable Odoo sources — set the project and analytic ids first."
    elif reachable:
        ok = sum(1 for s in statuses.values() if s in ("ok", "capped"))
        summary = f"Scanned {len(statuses)} source(s); {ok} returned records (counts capped)."
    else:
        summary = "Odoo read endpoint was not reachable or returned errors for all sources."

    return OdooSourceScanResult(
        project_code=project_code,
        scanned_at=datetime.now(timezone.utc).isoformat(),
        reachable=reachable,
        capped_at=100,
        counts=counts,
        statuses=statuses,
        summary=summary,
    )
