"""Node 9 - Normalize and Deduplicate. Spec: Sections 12 and 16."""

from collections import Counter

from apps.edr.graph.state import DecisionState

_SOURCE_PRIORITY = {
    "odoo": 3,
    "sharepoint": 2,
    "owncloud": 2,
    "email": 1,
    "cad": 0,
}


async def run(state: DecisionState) -> DecisionState:
    evidence = state.evidence
    seen: dict[tuple[str, str], dict] = {}

    for item in evidence:
        key = (item.get("source_uri", ""), item.get("hash_sha256", ""))
        existing = seen.get(key)
        if existing is None:
            seen[key] = item
            continue
        # Higher source-type priority wins; never downgrade.
        existing_priority = _SOURCE_PRIORITY.get(existing.get("source_type", ""), 0)
        new_priority = _SOURCE_PRIORITY.get(item.get("source_type", ""), 0)
        if new_priority > existing_priority:
            seen[key] = item

    deduped = list(seen.values())
    removed = len(evidence) - len(deduped)
    distribution = Counter(str(e.get("confidence", "unknown")) for e in deduped)

    state.evidence = deduped
    state.outputs["evidence_count"] = len(deduped)
    state.outputs["dedup_removed"] = removed
    state.outputs["confidence_distribution"] = dict(distribution)

    return state.mark("node_09_normalize")
