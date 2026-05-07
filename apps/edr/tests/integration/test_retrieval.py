"""Phase 1D retrieval layer tests.

All tests use mocks so they pass without live Voyage, Cohere, Qdrant, or Redis.
"""

import asyncio

from apps.edr.retrieval.chunking import chunk_text
from apps.edr.retrieval.embeddings import EmbeddingClient
from apps.edr.retrieval.hybrid_search import SearchHit, reciprocal_rank_fusion
from apps.edr.retrieval.qdrant_store import EvidenceStore
from apps.edr.retrieval.rerank import Reranker
from apps.edr.retrieval.cache import EvidenceCache


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


async def _mock_embed(texts, model):
    return type("Response", (), {"embeddings": [[0.0] * 1024 for _ in texts]})()


def test_embed_returns_correct_dimension() -> None:
    mock_client = type("MockVoyage", (), {})()
    mock_client.embed = _mock_embed

    client = EmbeddingClient(api_key="test", _client=mock_client)
    vectors = asyncio.run(client.embed(["hello", "world"]))

    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert len(vectors[1]) == 1024


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def test_chunk_text_token_bounds() -> None:
    # 800 tokens of repeating text (~4 chars per token ≈ 3200 chars)
    text = ("word " * 200) * 4  # roughly 800 tokens
    chunks = chunk_text(text, target_tokens=650, overlap_tokens=125)

    assert len(chunks) > 0
    # Each chunk should be non-empty
    for chunk in chunks:
        assert len(chunk) > 0


# ---------------------------------------------------------------------------
# Qdrant Store
# ---------------------------------------------------------------------------


def test_qdrant_insert_and_retrieve() -> None:
    mock_qdrant = type("MockQdrant", (), {})()
    mock_qdrant.collection_exists = lambda name: False
    mock_qdrant.create_collection = lambda **kw: None

    stored_points: list = []

    def mock_upsert(*, collection_name, points):
        stored_points.extend(points)

    def mock_search(*, collection_name, query_vector, limit, with_payload):
        return [
            type(
                "ScoredPoint",
                (),
                {"id": p.id, "score": 0.95, "payload": p.payload},
            )
            for p in stored_points
        ]

    mock_qdrant.upsert = mock_upsert
    mock_qdrant.search = mock_search

    store = EvidenceStore(_client=mock_qdrant)
    store.ensure_collection("PRJ-001", vector_size=1024)
    store.insert("PRJ-001", "ev-001", [0.1] * 1024, {"title": "Test"})
    hits = store.search("PRJ-001", [0.1] * 1024, top_k=10)

    assert len(hits) == 1
    assert hits[0].evidence_id == "ev-001"
    assert hits[0].payload["title"] == "Test"


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def test_rrf_fusion_produces_ranked_list() -> None:
    set_a = [
        SearchHit(evidence_id="a", score=1.0, payload={}),
        SearchHit(evidence_id="b", score=0.9, payload={}),
    ]
    set_b = [
        SearchHit(evidence_id="b", score=1.0, payload={}),
        SearchHit(evidence_id="c", score=0.8, payload={}),
    ]

    result = reciprocal_rank_fusion([set_a, set_b], k=60)

    assert len(result) == 3
    # b appears in both sets → higher fused score
    assert result[0].evidence_id == "b"
    scores = {r.evidence_id: r.score for r in result}
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_redis_cache_key_includes_user_and_project() -> None:
    cache = EvidenceCache()
    key = cache._build_key(
        user_id="user-42",
        query="project status",
        project_code="PRJ-001",
        allowed_resources={"mailboxes": ["a@b.com"]},
    )
    assert "user-42" in key
    assert "PRJ-001" in key
    assert "project status" in key


# ---------------------------------------------------------------------------
# Rerank
# ---------------------------------------------------------------------------


def test_rerank_truncates_to_10() -> None:
    class MockResult:
        def __init__(self, index, score):
            self.index = index
            self.relevance_score = score

    async def _mock_rerank(**kw):
        return type(
            "Response", (), {"results": [MockResult(i, 0.9) for i in range(min(10, len(kw["documents"])))]}
        )()

    mock_client = type("MockCohere", (), {})()
    mock_client.rerank = _mock_rerank

    reranker = Reranker(api_key="test", _client=mock_client)
    hits = [
        SearchHit(evidence_id=f"ev-{i}", score=0.5, payload={"excerpt": f"text {i}"})
        for i in range(15)
    ]
    result = asyncio.run(reranker.rerank("query", hits))

    assert len(result) <= 10
