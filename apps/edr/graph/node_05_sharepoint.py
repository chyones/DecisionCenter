"""Node 5 - SharePoint Retrieval. Spec: Sections 4.1 and 16.

The project's SharePoint drive (site_id/drive_id) is already scoped to the
project, so any term that matches documents returns project-relevant evidence.
A raw natural-language query (e.g. "give me a small summary") often matches no
documents, so for generic queries we derive search terms from the project code,
project name, known aliases and the user query, and try them in priority order
until documents are found.
"""

import re

from apps.edr.config import settings
from apps.edr.connectors.sharepoint import search_sharepoint
from apps.edr.graph import coverage
from apps.edr.graph.financial_evidence import filter_financial_evidence, financial_search_terms
from apps.edr.graph.intent import classify_report_type
from apps.edr.graph.state import DecisionState
from apps.edr.rbac.project_mapping import ProjectMapping
from apps.edr.rbac.roles import ROLE_PERMISSIONS, Role
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.qdrant_store import EvidenceStore

# Instruction/filler words that carry no document-search signal.
_STOPWORDS = {
    "give", "me", "a", "an", "the", "small", "summary", "sumary", "for", "this",
    "that", "project", "please", "report", "of", "on", "about", "what", "is",
    "are", "show", "tell", "get", "provide", "generate", "status", "overview",
    "brief", "and", "to", "in", "with", "please", "kindly", "do", "you", "can",
}
_MAX_TERM_ATTEMPTS = 3


def _query_keywords(query: str) -> str:
    toks = re.findall(r"[A-Za-z0-9]+", (query or "").lower())
    kept = [t for t in toks if t not in _STOPWORDS and len(t) > 2]
    return " ".join(kept)


def derive_search_terms(query: str, sp_config: dict, mapping: dict, project_code: str) -> list[str]:
    """Ordered, de-duplicated candidate search terms for the project drive.

    Priority: meaningful query keywords -> project name -> known SharePoint
    aliases -> project code. Generic queries that reduce to nothing fall through
    to project-derived terms so a project report still surfaces documents.
    """
    terms: list[str] = []

    def add(t: str | None) -> None:
        if t and t.strip() and t.strip() not in terms:
            terms.append(t.strip())

    if classify_report_type(query) == "financial":
        for term in financial_search_terms(query):
            add(term)
        return terms or ["BOQ"]

    add(_query_keywords(query))
    add(mapping.get("project_name") or sp_config.get("project_name"))
    for alias in mapping.get("sharepoint_aliases", []) or []:
        add(alias)
    add(project_code)
    return terms or [query]


def _enabled(mapping: dict) -> bool:
    return "sharepoint" in set(mapping.get("enabled_sources", []))


async def run(state: DecisionState) -> DecisionState:
    try:
        mapping = ProjectMapping.load().get(state.project_code)
    except Exception:
        mapping = {}
    enabled = _enabled(mapping)

    role = state.role
    if role:
        perms = ROLE_PERMISSIONS.get(Role(role))
        if perms and not perms.can_access_sharepoint:
            state.outputs["sharepoint_status"] = "rbac_denied"
            coverage.record(state, "sharepoint", enabled=enabled, attempted=False,
                            status="rbac_denied", evidence_count=0,
                            reason="Role not permitted to access SharePoint.")
            return state.mark("node_05_sharepoint")

    sp_config = mapping.get("sharepoint", {})
    terms = derive_search_terms(state.query, sp_config, mapping, state.project_code or "")
    tried: list[str] = []
    evidence: list = []
    used_term = None
    try:
        max_attempts = 6 if classify_report_type(state.query) == "financial" else _MAX_TERM_ATTEMPTS
        raw_count = 0
        filtered_count = 0
        for term in terms[:max_attempts]:
            tried.append(term)
            payload = {
                "query": term,
                "project_code": state.project_code,
                "site_id": sp_config.get("site_id"),
                "drive_id": sp_config.get("drive_id"),
            }
            raw_evidence = await search_sharepoint(payload)
            raw_count += len(raw_evidence)
            if classify_report_type(state.query) == "financial":
                evidence_dicts = [e.model_dump() for e in raw_evidence]
                filtered_dicts = filter_financial_evidence(evidence_dicts, query=state.query)
                filtered_count += len(filtered_dicts)
                evidence = [e for e in raw_evidence if e.evidence_id in {d["evidence_id"] for d in filtered_dicts}]
            else:
                evidence = raw_evidence
            if evidence:
                used_term = term
                break

        state.evidence.extend([e.model_dump() for e in evidence])
        state.outputs["sharepoint_status"] = f"ok ({len(evidence)} items)"
        state.outputs["sharepoint_search_term_used"] = used_term
        state.outputs["sharepoint_terms_tried"] = tried

        if evidence:
            cov_status, cov_reason = "ok", ""
        else:
            cov_status = "zero_no_match"
            if classify_report_type(state.query) == "financial" and raw_count:
                cov_reason = (
                    "SharePoint returned documents, but none matched the financial "
                    f"evidence policy after filtering (raw={raw_count}, kept={filtered_count})."
                )
            else:
                cov_reason = f"No SharePoint documents matched terms tried: {tried}."
        coverage.record(state, "sharepoint", enabled=enabled, attempted=True,
                        status=cov_status, evidence_count=len(evidence), reason=cov_reason)

        try:
            embedder = EmbeddingClient(settings.voyage_api_key)
            store = EvidenceStore()
            store.ensure_collection(state.project_code)
            texts = [e.excerpt for e in evidence]
            vectors = await embedder.embed(texts)
            for ev, vec in zip(evidence, vectors):
                store.insert(state.project_code, ev.evidence_id, vec, ev.model_dump())
            state.outputs["sharepoint_qdrant_status"] = "inserted"
        except Exception as exc:
            state.outputs["sharepoint_qdrant_status"] = f"error: {exc}"
    except Exception as exc:
        state.outputs["sharepoint_status"] = f"error: {exc}"
        coverage.record(state, "sharepoint", enabled=enabled, attempted=True,
                        status="error", evidence_count=0,
                        reason=f"SharePoint connector error: {exc}")

    return state.mark("node_05_sharepoint")
