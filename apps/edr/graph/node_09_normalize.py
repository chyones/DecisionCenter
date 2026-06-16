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


def _title_key(item: dict) -> str | None:
    """Return a normalized title key for secondary dedup, or None to skip."""
    title = (item.get("title") or "").strip()
    if not title:
        return None
    # Strip common revision suffixes so "Doc Rev1" and "Doc Rev2" count as different
    # but "Project Report.pdf" appearing twice counts as the same.
    return title.lower()


async def run(state: DecisionState) -> DecisionState:
    evidence = state.evidence

    # Primary pass: deduplicate by (source_uri, hash_sha256). Higher source-type
    # priority wins; never downgrade.
    seen: dict[tuple[str, str], dict] = {}
    for item in evidence:
        key = (item.get("source_uri", ""), item.get("hash_sha256", ""))
        existing = seen.get(key)
        if existing is None:
            seen[key] = item
            continue
        existing_priority = _SOURCE_PRIORITY.get(existing.get("source_type", ""), 0)
        new_priority = _SOURCE_PRIORITY.get(item.get("source_type", ""), 0)
        if new_priority > existing_priority:
            seen[key] = item

    after_hash_dedup = list(seen.values())

    # Secondary pass: deduplicate by (source_type, normalised_title).
    # SharePoint often returns the same document at multiple URLs or with
    # minor metadata differences. Keep only the first occurrence of each
    # title within a given source type. Items with no title are kept as-is.
    title_seen: dict[tuple[str, str], bool] = {}
    deduped: list[dict] = []
    for item in after_hash_dedup:
        stype = item.get("source_type", "")
        tkey = _title_key(item)
        if tkey is None:
            deduped.append(item)
            continue
        composite = (stype, tkey)
        if composite not in title_seen:
            title_seen[composite] = True
            deduped.append(item)
        # else: duplicate title within same source type — drop silently

    removed = len(evidence) - len(deduped)
    distribution = Counter(str(e.get("confidence", "unknown")) for e in deduped)

    state.evidence = deduped
    state.outputs["evidence_count"] = len(deduped)
    state.outputs["dedup_removed"] = removed
    state.outputs["confidence_distribution"] = dict(distribution)

    return state.mark("node_09_normalize")
