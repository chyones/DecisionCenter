import json
from typing import Any

from apps.edr.config import settings
from apps.edr.connectors.base import N8NWebhookClient
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


async def read_odoo(payload: dict[str, Any]) -> list[EvidenceObject]:
    """Call the n8n Odoo read webhook and validate the response."""
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(settings.odoo_read_webhook, payload)
    return validate_evidence_payload(response)
