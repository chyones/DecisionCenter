"""Node 8 - Odoo Facts Retrieval. Spec: Sections 4.4 and 16.

Retrieves the project record (project.project) and, when the project mapping
declares a verified analytic account, the real posted cost lines
(account.analytic.line). Financial figures are NEVER taken from nonexistent
project.project columns (budget/actual_cost) and are NEVER invented — if no
verified cost evidence exists, that is recorded so the report can state
"financial data not available in verified Odoo evidence".
"""

from apps.edr.config import settings
from apps.edr.connectors.odoo import build_cost_query, build_project_query, read_odoo
from apps.edr.graph import coverage
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore


def _enabled(mapping: dict) -> bool:
    return "odoo" in set(mapping.get("enabled_sources", []))


async def run(state: DecisionState) -> DecisionState:
    try:
        mapping = ProjectMapping.load().get(state.project_code)
    except Exception:
        mapping = {}
    enabled = _enabled(mapping)

    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_odoo_budget:
            state.outputs["odoo_status"] = "rbac_denied"
            coverage.record(state, "odoo", enabled=enabled, attempted=False,
                            status="rbac_denied", evidence_count=0,
                            reason="Role not permitted to access Odoo budget data.")
            return state.mark("node_08_odoo")

    odoo_config = mapping.get("odoo", {})
    added = 0
    financial_available = False
    try:
        # 1) Project record (always)
        domain, fields = build_project_query(odoo_config, state.project_code)
        payload = {
            "project_code": state.project_code,
            "model": odoo_config.get("project_model", "project.project"),
            "domain": domain,
            "fields": fields,
            "allowed_odoo_ids": state.allowed_odoo_ids,
        }
        project_ev = await read_odoo(payload)
        state.evidence.extend([e.model_dump() for e in project_ev])
        added += len(project_ev)

        # 2) Cost lines from the verified analytic account (real posted costs only)
        cost_ev: list = []
        cost_q = build_cost_query(odoo_config)
        if cost_q is not None:
            cost_model, cost_domain, cost_fields = cost_q
            cost_payload = {
                "project_code": state.project_code,
                "model": cost_model,
                "domain": cost_domain,
                "fields": cost_fields,
                "limit": 100,
                "allowed_odoo_ids": state.allowed_odoo_ids,
            }
            try:
                cost_ev = await read_odoo(cost_payload)
                state.evidence.extend([e.model_dump() for e in cost_ev])
                added += len(cost_ev)
                financial_available = len(cost_ev) > 0
            except Exception as exc:
                state.outputs["odoo_cost_status"] = f"error: {exc}"
        else:
            state.outputs["odoo_cost_status"] = "no_verified_analytic_account"

        state.outputs["odoo_status"] = f"ok ({added} items)"
        state.outputs["odoo_financial_available"] = financial_available
        if not financial_available:
            state.outputs["odoo_financial_note"] = (
                "financial data not available in verified Odoo evidence"
            )

        if added > 0:
            cov_status, cov_reason = "ok", ""
        else:
            cov_status = "zero_no_match"
            cov_reason = "Odoo returned no records for the mapped project id."
        coverage.record(state, "odoo", enabled=enabled, attempted=True,
                        status=cov_status, evidence_count=added, reason=cov_reason)

        # Embeddings/Qdrant insert is supplementary; failure does not drop evidence.
        try:
            embedder = EmbeddingClient(settings.voyage_api_key)
            store = EvidenceStore()
            store.ensure_collection(state.project_code)
            all_ev = list(project_ev) + list(cost_ev)
            texts = [e.excerpt for e in all_ev]
            vectors = await embedder.embed(texts)
            for ev, vec in zip(all_ev, vectors):
                store.insert(state.project_code, ev.evidence_id, vec, ev.model_dump())
            state.outputs["odoo_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["odoo_qdrant_status"] = f"error: {exc}"
    except Exception as exc:
        state.outputs["odoo_status"] = f"error: {exc}"
        coverage.record(state, "odoo", enabled=enabled, attempted=True,
                        status="error", evidence_count=added,
                        reason=f"Odoo connector error: {exc}")

    return state.mark("node_08_odoo")
