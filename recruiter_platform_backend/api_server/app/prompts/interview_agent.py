"""Prompts for the interview-question generation step."""

from __future__ import annotations

INTERVIEW_AGENT_MAX_CONTEXT_CHARS = 6000

INTERVIEW_AGENT_SYSTEM = """You are an experienced hiring manager writing interview questions for this job's shortlist.
Rules:
- Output between 5 and 8 numbered questions (1. 2. 3. …), each on its own line or after a newline.
- Mix technical or role-specific questions with behavioral (STAR-style) questions grounded in the context.
- Use only information implied by the context; do not invent employers or credentials.
- Keep each question one or two sentences.
- Do not include a preamble or closing — only the numbered list."""


def build_interview_human(*, match_summary: str, ranking_summary: str, parse_notes: str) -> str:
    """Human message: capped excerpts from earlier screening steps."""
    match = (match_summary or "").strip()[:INTERVIEW_AGENT_MAX_CONTEXT_CHARS]
    ranking = (ranking_summary or "").strip()[:INTERVIEW_AGENT_MAX_CONTEXT_CHARS]
    parse_excerpt = (parse_notes or "").strip()[:INTERVIEW_AGENT_MAX_CONTEXT_CHARS]
    return (
        "Context from the screening pipeline (may mention several candidates):\n\n"
        f"--- Skill / fit summary ---\n{match or '(none)'}\n\n"
        f"--- Ranking ---\n{ranking or '(none)'}\n\n"
        f"--- CV parse notes (excerpts) ---\n{parse_excerpt or '(none)'}\n"
    )
