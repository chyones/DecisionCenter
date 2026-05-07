"""Cohere Rerank 3.5 client. Phase 1D."""

from apps.edr.retrieval.hybrid_search import SearchHit


class Reranker:
    """Async client for Cohere Rerank 3.5."""

    def __init__(self, api_key: str | None = None, _client=None) -> None:
        self.api_key = api_key
        self._client = _client

    async def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        """Rerank up to 50 hits; return top 10."""
        if not hits:
            return []

        if self._client is not None:
            client = self._client
        else:
            import cohere

            client = cohere.AsyncClient(api_key=self.api_key)

        inputs = hits[:50]
        documents = [
            hit.payload.get("excerpt", hit.payload.get("title", ""))
            for hit in inputs
        ]

        response = await client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=min(10, len(documents)),
        )

        ranked: list[SearchHit] = []
        for result in response.results:
            original = inputs[result.index]
            ranked.append(
                SearchHit(
                    evidence_id=original.evidence_id,
                    score=result.relevance_score,
                    payload=original.payload,
                )
            )
        return ranked
