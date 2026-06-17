import json
from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient
from apps.edr.connectors.odoo_sources import (
    ODOO_SOURCES,
    OdooSource,
    active_sources,
    assert_path_allowed,
)
from apps.edr.connectors.validation import validate_evidence_payload
from apps.edr.schemas.evidence import EvidenceObject

# project.project columns proven to exist on the live Odoo instance. budget /
# actual_cost are NOT columns on project.project (financial data lives in
# account.analytic.line) — requesting them makes search_read return nothing.
PROJECT_FIELDS = ["name", "date_start", "date", "user_id", "partner_id"]

# account.analytic.line columns proven to exist on the live Odoo instance.
# These carry real posted cost lines (amount is negative for costs).
COST_FIELDS = ["name", "amount", "date"]
DEFAULT_COST_MODEL = "account.analytic.line"


def build_project_query(odoo_config: dict[str, Any], project_code: str) -> tuple[str, str]:
    """Build the (domain, fields) JSON for a project.project lookup.

    The mapped ``project_external_id`` is the Odoo record id (numeric, enforced at
    the admin source-mapping surface). Query by ``id`` when it is numeric, else
    fall back to an exact project-name match. json.dumps keeps any value safely
    contained in the domain literal so mapping values cannot break out of the
    JSON (injection-safe).
    """
    external_id = odoo_config.get("project_external_id")
    if external_id is not None and str(external_id).strip().isdigit():
        domain = json.dumps([["id", "=", int(external_id)]])
    else:
        name = odoo_config.get("project_name") or project_code
        domain = json.dumps([["name", "=", name]])
    fields = json.dumps(PROJECT_FIELDS)
    return domain, fields


def build_cost_query(odoo_config: dict[str, Any]) -> tuple[str, str, str] | None:
    """Build the (model, domain, fields) JSON for the project's cost lines.

    Returns ``None`` when the mapping has no verified analytic account, so the
    caller records "financial data not available in verified Odoo evidence"
    rather than inventing figures. Cost lives in ``account.analytic.line`` keyed
    by the analytic account id — never as ``budget``/``actual_cost`` columns on
    ``project.project`` (those do not exist).
    """
    analytic_id = odoo_config.get("analytic_account_id")
    if analytic_id is None or not str(analytic_id).strip().isdigit():
        return None
    model = odoo_config.get("cost_model") or DEFAULT_COST_MODEL
    domain = json.dumps([["account_id", "=", int(analytic_id)]])
    fields = json.dumps(COST_FIELDS)
    return model, domain, fields


def _resolve_link_value(source: OdooSource, odoo_config: dict[str, Any]) -> int | None:
    """Resolve the numeric project-link value for a source, or None if unmapped.

    ``project`` scope uses ``project_external_id`` (the project.project id);
    ``analytic`` scope uses ``analytic_account_id``. A non-numeric/absent value
    yields None so the caller skips the source instead of guessing.
    """
    raw = (
        odoo_config.get("project_external_id")
        if source.link_scope == "project"
        else odoo_config.get("analytic_account_id")
    )
    if raw is None or not str(raw).strip().isdigit():
        return None
    return int(raw)


def build_source_query(
    source: OdooSource, odoo_config: dict[str, Any]
) -> tuple[str, str, str, int] | None:
    """Build the (model, domain, fields, limit) for one proven Odoo source.

    Returns ``None`` when the project mapping lacks the id this source needs.
    The link path is checked against the denylist (defensive — registry entries
    are already validated at import) so a denylisted path can never be queried.
    json.dumps keeps every value injection-safe inside the JSON literal.
    """
    assert_path_allowed(source.model, source.link_path)
    value = _resolve_link_value(source, odoo_config)
    if value is None:
        return None
    domain = json.dumps([[source.link_path, "=", value]])
    fields = json.dumps(list(source.fields))
    return source.model, domain, fields, source.limit


def build_all_source_queries(
    odoo_config: dict[str, Any], *, include_medium: bool = True
) -> list[dict[str, Any]]:
    """Build query specs for every active proven source the mapping can scope.

    Each spec carries the source ``key``/``category``/``confidence`` so the
    caller can tag the resulting evidence and report per-source counts. Sources
    the mapping cannot scope (missing id) are returned with ``"query": None`` so
    the caller can record them as a connector gap rather than dropping silently.
    """
    specs: list[dict[str, Any]] = []
    for source in active_sources(include_medium=include_medium):
        query = build_source_query(source, odoo_config)
        specs.append(
            {
                "key": source.key,
                "category": source.category,
                "model": source.model,
                "link_path": source.link_path,
                "link_scope": source.link_scope,
                "confidence": source.confidence,
                "query": query,  # (model, domain, fields, limit) or None
            }
        )
    return specs


async def read_odoo(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Call the n8n Odoo read webhook and validate the response.

    The payload may carry an optional ``offset`` (for paged sampling). Workflows
    that predate offset support simply ignore it and return the first page —
    callers that need true pagination detect that via :func:`count_odoo`.
    """
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(settings.odoo_read_webhook, payload)
    return validate_evidence_payload(response)


async def count_odoo(payload: dict[str, Any]) -> int | None:
    """Return an exact ``search_count`` total for a scoped query, or ``None``.

    Sends ``operation: "count"`` to the Odoo read webhook. The enhanced workflow
    answers ``{"count": N}``; an older workflow ignores the flag and answers with
    ``{"evidence": [...]}`` — in that case we return ``None`` so the caller knows
    exact totals are unavailable and must fall back to a capped single page.

    Read-only and project-scoped: ``payload["domain"]`` is the same scoped leaf
    the read uses; count never widens the filter.
    """
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    body = {**payload, "operation": "count"}
    response = await client.post(settings.odoo_read_webhook, body)
    if isinstance(response, dict):
        if response.get("error"):
            raise RuntimeError(str(response["error"]))
        value = response.get("count")
        if isinstance(value, bool):  # guard: bool is an int subclass
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value)
    return None  # legacy workflow / no count → totals unavailable


__all__ = [
    "PROJECT_FIELDS",
    "COST_FIELDS",
    "DEFAULT_COST_MODEL",
    "ODOO_SOURCES",
    "build_project_query",
    "build_cost_query",
    "build_source_query",
    "build_all_source_queries",
    "read_odoo",
    "count_odoo",
]
