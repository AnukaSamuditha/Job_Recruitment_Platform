"""Deterministic character-window chunking for CV embedding."""

from __future__ import annotations


def chunk_text(
    text: str,
    *,
    max_chars: int = 900,
    overlap: int = 120,
) -> list[str]:
    """Split plain text into overlapping windows."""
    t = text.strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]
    chunks: list[str] = []
    start = 0
    step = max(1, max_chars - overlap)
    while start < len(t):
        end = min(start + max_chars, len(t))
        chunks.append(t[start:end].strip())
        if end >= len(t):
            break
        start += step
    return [c for c in chunks if c]
