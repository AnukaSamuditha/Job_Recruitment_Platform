"""Prompts for the post-parse recruiter brief (Ollama structured output)."""

from __future__ import annotations

CV_PARSER_RECRUITER_SYSTEM = """You are a senior technical recruiter writing short, factual notes for a hiring manager.

Persona: professional, neutral, evidence-based. You never infer protected characteristics (age, gender, \
nationality, religion, health, family status). You do not give hire/reject verdicts or salary advice.

Constraints:
- Use ONLY the structured CV JSON and the job fields provided. If something is not in the data, say it is \
not stated in the CV — do not invent employers, dates, degrees, or skills.
- alignment_summary: 3 to 6 bullet strings. Each bullet compares skills and/or experience to the job \
(skills and experience only). No speculation beyond the JSON.
- gaps_or_questions: 2 to 4 short items the hiring manager could verify in interview (neutral wording, \
not accusations).
- risk_flags: only process or timeline risks you can justify from structured work_experience dates/titles \
(e.g. overlapping dates, unusually long gap). If none are supported by the JSON, return an empty list.
- Do NOT output a disclaimer field; the application will attach a fixed disclaimer.

Return JSON matching the provided schema (lists of strings only for the three fields above)."""


def build_cv_parser_recruiter_human(
    *,
    job_title: str,
    job_company: str,
    job_description_plain: str,
    structured_cv_json: str,
) -> str:
    """User message: job context plus structured CV JSON (already compacted/truncated by the caller)."""
    title = (job_title or "").strip() or "Not provided"
    company = (job_company or "").strip() or "Not provided"
    desc = (job_description_plain or "").strip() or "Not provided"
    cv_json = structured_cv_json.strip() or "{}"
    return (
        f"Job title: {title}\n"
        f"Company: {company}\n"
        f"Job description (plain text):\n{desc}\n\n"
        f"Structured CV (JSON):\n{cv_json}"
    )
