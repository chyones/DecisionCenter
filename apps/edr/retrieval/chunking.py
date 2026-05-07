"""Token-based text chunking. Phase 1D."""

from collections.abc import Iterable

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except ImportError:  # pragma: no cover
    _ENCODING = None


def chunk_text(
    text: str,
    target_tokens: int = 650,
    overlap_tokens: int = 125,
    hard_max_tokens: int = 1024,
) -> list[str]:
    """Split *text* into chunks of 500–800 tokens (target 650), with 100–150 token overlap.

    Falls back to character-based chunking if *tiktoken* is not installed.
    """
    if _ENCODING is None:
        return _char_fallback_chunk(text, target_tokens, overlap_tokens)

    tokens = _ENCODING.encode(text)
    if len(tokens) <= hard_max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_ENCODING.decode(chunk_tokens))
        if end == len(tokens):
            break
        start = max(0, end - overlap_tokens)

    return _normalize_chunks(chunks)


def _char_fallback_chunk(text: str, target_tokens: int, overlap_tokens: int) -> list[str]:
    # Rough heuristic: ~4 chars per token
    max_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap_chars
    return _normalize_chunks(chunks)


def _normalize_chunks(chunks: Iterable[str]) -> list[str]:
    return [" ".join(chunk.split()) for chunk in chunks if chunk.strip()]
