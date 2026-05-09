"""Node 6 - ownCloud Retrieval. Spec: Sections 4.2 and 16."""

from apps.edr.config import settings
from apps.edr.connectors.owncloud import list_owncloud
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore


async def run(state: DecisionState) -> DecisionState:
    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_owncloud:
            state.outputs["owncloud_status"] = "rbac_denied"
            return state.mark("node_06_owncloud")

    try:
        mapping = ProjectMapping.load().get(state.project_code)
        oc_config = mapping.get("owncloud", {})
        # Service-account credentials live in n8n's environment ($env.OWNCLOUD_*).
        # The Python wrapper only carries the request-scoped fields.
        payload = {
            "project_code": state.project_code,
            "root_path": oc_config.get("base_path", ""),
            "base_url": settings.public_base_url,
        }
        evidence = await list_owncloud(payload)
        state.evidence.extend([e.model_dump() for e in evidence])
        state.outputs["owncloud_status"] = f"ok ({len(evidence)} items)"

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
            state.outputs["owncloud_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["owncloud_qdrant_status"] = f"error: {exc}"
    except Exception as exc:
        state.outputs["owncloud_status"] = f"error: {exc}"

    return state.mark("node_06_owncloud")
