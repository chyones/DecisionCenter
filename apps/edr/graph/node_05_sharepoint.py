"""Node 5 - SharePoint Retrieval. Spec: Sections 4.1 and 16."""

from apps.edr.config import settings
from apps.edr.connectors.sharepoint import search_sharepoint
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore


async def run(state: DecisionState) -> DecisionState:
    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_sharepoint:
            state.outputs["sharepoint_status"] = "rbac_denied"
            return state.mark("node_05_sharepoint")

    try:
        mapping = ProjectMapping.load().get(state.project_code)
        sp_config = mapping.get("sharepoint", {})
        payload = {
            "query": state.query,
            "project_code": state.project_code,
            "site_id": sp_config.get("site_id"),
            "drive_id": sp_config.get("drive_id"),
        }
        evidence = await search_sharepoint(payload)
        state.evidence.extend([e.model_dump() for e in evidence])
        state.outputs["sharepoint_status"] = f"ok ({len(evidence)} items)"

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
            state.outputs["sharepoint_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["sharepoint_qdrant_status"] = f"error: {exc}"
    except Exception as exc:
        state.outputs["sharepoint_status"] = f"error: {exc}"

    return state.mark("node_05_sharepoint")
