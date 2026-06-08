"""Node 8 - Odoo Facts Retrieval. Spec: Sections 4.4 and 16."""

import json

from apps.edr.config import settings
from apps.edr.connectors.odoo import read_odoo
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore


async def run(state: DecisionState) -> DecisionState:
    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_odoo_budget:
            state.outputs["odoo_status"] = "rbac_denied"
            return state.mark("node_08_odoo")

    try:
        mapping = ProjectMapping.load().get(state.project_code)
        odoo_config = mapping.get("odoo", {})
        # Build the Odoo search domain via json.dumps so mapped Odoo ids or
        # fallback project_code values cannot break out of the JSON literal.
        odoo_project_id = odoo_config.get("project_external_id") or state.project_code
        domain = json.dumps([["project_external_id", "=", odoo_project_id]])
        fields = json.dumps(["name", "budget", "actual_cost"])
        # Service-account credentials (database/username/api_key) live in n8n's
        # environment ($env.ODOO_*); they are not transmitted via the webhook
        # body. settings.odoo_url is left here only so callers/tests can audit
        # what the n8n server is *expected* to use.
        payload = {
            "project_code": state.project_code,
            "model": odoo_config.get("project_model", "project.project"),
            "domain": domain,
            "fields": fields,
            "allowed_odoo_ids": state.allowed_odoo_ids,
        }
        evidence = await read_odoo(payload)
        state.evidence.extend([e.model_dump() for e in evidence])
        state.outputs["odoo_status"] = f"ok ({len(evidence)} items)"

        try:
            embedder = EmbeddingClient(settings.voyage_api_key)
            store = EvidenceStore()
            store.ensure_collection(state.project_code)
            texts = [e.excerpt for e in evidence]
            vectors = await embedder.embed(texts)
            for ev, vec in zip(evidence, vectors):
                store.insert(
                    state.project_code,
                    ev.evidence_id,
                    vec,
                    ev.model_dump(),
                )
            state.outputs["odoo_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["odoo_qdrant_status"] = f"error: {exc}"
    except Exception as exc:
        state.outputs["odoo_status"] = f"error: {exc}"

    return state.mark("node_08_odoo")
