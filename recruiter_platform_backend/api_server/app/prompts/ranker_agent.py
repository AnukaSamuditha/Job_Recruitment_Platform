"""Prompt for the ranker LLM step."""

from __future__ import annotations

RANKER_INSTRUCTIONS = (
    "You are an executive talent sourcer. Rank the candidates qualitatively from BEST to WORST "
    "based on their fit for the job as described in the match summary. "
    "Perform a definitive 'force-ranking'—no ties. "
    "Return a clear, numbered list. For each candidate, provide a one-line executive justification "
    "explaining why they are in that specific position relative to others.\n"
)


def build_ranker_prompt(*, match_summary: str) -> str:
    return f"{RANKER_INSTRUCTIONS}{match_summary or ''}"
