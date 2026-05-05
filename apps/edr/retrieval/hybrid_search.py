from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    evidence_id: str
    score: float
    payload: dict[str, object]


def reciprocal_rank_fusion(result_sets: list[list[SearchHit]], k: int = 60) -> list[SearchHit]:
    scores: dict[str, float] = {}
    payloads: dict[str, dict[str, object]] = {}

    for result_set in result_sets:
        for rank, hit in enumerate(result_set, start=1):
            scores[hit.evidence_id] = scores.get(hit.evidence_id, 0.0) + 1.0 / (k + rank)
            payloads.setdefault(hit.evidence_id, hit.payload)

    return [
        SearchHit(evidence_id=evidence_id, score=score, payload=payloads[evidence_id])
        for evidence_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]
