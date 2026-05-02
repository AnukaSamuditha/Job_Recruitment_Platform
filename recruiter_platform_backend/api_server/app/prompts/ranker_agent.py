"""Prompt for the ranker LLM step."""

from __future__ import annotations

RANKER_INSTRUCTIONS = (
    "Rank the candidates qualitatively based on the match summary. "
    "Return a short ordered list with one-line justifications.\n"
)


def build_ranker_prompt(*, match_summary: str) -> str:
    return f"{RANKER_INSTRUCTIONS}{match_summary or ''}"
