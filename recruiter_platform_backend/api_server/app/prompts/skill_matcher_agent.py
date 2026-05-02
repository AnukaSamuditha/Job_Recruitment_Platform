"""Prompt for the skill matcher LLM summary."""

from __future__ import annotations

SKILL_MATCHER_INSTRUCTIONS = (
    "You are a recruiting skill matcher. First respect the automatic keyword scores "
    "(same logic as the MCP tool compute_candidate_job_fit / gRPC ComputeCandidateJobFit); "
    "then use CV snippets and parse notes. Summarize fit in 3-5 bullet points.\n\n"
)


def build_skill_matcher_prompt(*, fit_block: str, parse_notes: str, ctx_block: str) -> str:
    fit = fit_block.strip() if fit_block.strip() else "(no job-fit scores computed)"
    notes = parse_notes.strip() if parse_notes.strip() else ""
    ctx = ctx_block.strip() if ctx_block.strip() else "No chunk context."
    return (
        f"{SKILL_MATCHER_INSTRUCTIONS}"
        f"Automatic job match scores:\n{fit}\n\n"
        f"Parse notes:\n{notes}\n\n"
        f"Retrieved:\n{ctx}"
    )
