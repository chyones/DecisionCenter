from collections.abc import Iterable


def chunk_text(text: str, max_chars: int = 1600, overlap: int = 160) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be non-negative and smaller than max_chars")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def normalize_chunks(chunks: Iterable[str]) -> list[str]:
    return [" ".join(chunk.split()) for chunk in chunks if chunk.strip()]
