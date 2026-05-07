"""Qdrant vector store for evidence embeddings. Phase 1D."""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from apps.edr.retrieval.hybrid_search import SearchHit


class EvidenceStore:
    """Manage Qdrant collections and evidence vector operations."""

    def __init__(self, qdrant_url: str | None = None, _client: QdrantClient | None = None) -> None:
        if _client is not None:
            self._client = _client
        else:
            from apps.edr.config import settings

            self._client = QdrantClient(url=qdrant_url or settings.qdrant_url)

    @staticmethod
    def _collection_name(project_code: str) -> str:
        return f"edr_{project_code.lower().replace('-', '_')}"

    def ensure_collection(self, project_code: str, vector_size: int = 1024) -> None:
        """Idempotently create a Qdrant collection for the project."""
        name = self._collection_name(project_code)
        if not self._client.collection_exists(name):
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def insert(
        self,
        project_code: str,
        evidence_id: str,
        vector: list[float],
        payload: dict[str, object],
    ) -> None:
        """Upsert a single evidence vector into the project collection."""
        name = self._collection_name(project_code)
        self._client.upsert(
            collection_name=name,
            points=[
                PointStruct(
                    id=evidence_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    def search(
        self,
        project_code: str,
        query_vector: list[float],
        top_k: int = 50,
    ) -> list[SearchHit]:
        """Search the project collection and return scored hits."""
        name = self._collection_name(project_code)
        results = self._client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            SearchHit(
                evidence_id=point.id,
                score=point.score,
                payload=dict(point.payload or {}),
            )
            for point in results
        ]
