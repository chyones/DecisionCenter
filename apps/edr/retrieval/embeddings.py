"""Voyage-3-large embedding client. Phase 1D."""

from collections.abc import Sequence


class EmbeddingClient:
    """Async client for Voyage-3-large embeddings."""

    def __init__(self, api_key: str | None = None, _client=None) -> None:
        self.api_key = api_key
        self._client = _client

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return 1024-dimensional vectors for each text."""
        if self._client is not None:
            client = self._client
        else:
            import voyageai

            client = voyageai.AsyncClient(api_key=self.api_key)

        response = await client.embed(texts, model="voyage-3-large")
        return response.embeddings
