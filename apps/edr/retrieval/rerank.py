from apps.edr.retrieval.hybrid_search import SearchHit


class Reranker:
    """Placeholder for Cohere Rerank 3.5."""

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        raise NotImplementedError("Wire Cohere reranking in Phase 1D.")
