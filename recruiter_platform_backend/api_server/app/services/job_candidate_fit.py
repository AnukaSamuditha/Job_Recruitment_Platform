"""Job–candidate skill overlap (keyword-based).

Exposed as gRPC ``ComputeCandidateJobFit`` and MCP tool ``compute_candidate_job_fit``.
The screening ``skill_matcher`` node calls :func:`compute_job_candidate_fit` directly (same logic).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.chunk import CandidateDocumentChunk
from app.models.job import Job
from app.services.vector_query import top_k_chunks_for_job_candidate

_WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]*", re.I)

_STOP = frozenset(
    "a an the and or for to of in on at by as is are was were be been being it we you they this that "
    "with from will can may not no yes all any our your their more most less least other into out up "
    "about over under between per using use used work working experience years year month team strong "
    "good great excellent looking seeking opportunity role position company skills requirements required "
    "preferred ideal candidate ability knowledge understanding familiar proficiency level senior junior "
    "mid lead principal staff engineer developer software full part time remote hybrid onsite uk us"
    .split()
)


@dataclass(frozen=True)
class JobCandidateFitResult:
    overall_score: int
    matched_skills: list[str]
    missing_skills: list[str]
    summary_line: str

    def as_parse_blob(self, *, job_id: uuid.UUID) -> dict[str, Any]:
        d = asdict(self)
        d["job_id"] = str(job_id)
        return d


def _norm_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for m in _WORD.finditer(text or ""):
        t = m.group(0).lower()
        if len(t) < 2 or t in _STOP:
            continue
        out.add(t)
    return out


def _skills_from_structured(parse_result: dict[str, Any] | None) -> set[str]:
    if not isinstance(parse_result, dict):
        return set()
    raw = parse_result.get("llamaparse_structured")
    if not isinstance(raw, dict):
        return set()
    skills = raw.get("skills")
    if not isinstance(skills, list):
        return set()
    out: set[str] = set()
    for s in skills:
        if not isinstance(s, str):
            continue
        s = s.strip().lower()
        if len(s) < 2:
            continue
        out.add(s)
        for part in re.split(r"[,;/]|\s+", s):
            p = part.strip().lower()
            if len(p) > 1:
                out.add(p)
    return out


def _token_matches_job_requirement(req: str, candidate_pool: set[str]) -> bool:
    if req in candidate_pool:
        return True
    if len(req) < 4:
        return False
    for c in candidate_pool:
        if len(c) < 2:
            continue
        if req in c or c in req:
            return True
    return False


def compute_fit_from_texts(
    *,
    job_title: str,
    job_description: str,
    candidate_skills: set[str],
    cv_sample: str,
) -> JobCandidateFitResult:
    """Heuristic overlap score and missing-skill hints from plain text."""
    job_blob = f"{job_title}\n{job_description}".lower()
    job_tokens = _norm_tokens(job_blob)
    cv_tokens = _norm_tokens(cv_sample) | candidate_skills

    matched: set[str] = set()
    for t in job_tokens:
        if _token_matches_job_requirement(t, cv_tokens):
            matched.add(t)

    missing_candidates = sorted(
        (t for t in job_tokens if t not in matched and len(t) >= 3),
        key=lambda x: (-len(x), x),
    )[:14]

    n_job = len(job_tokens)
    if n_job == 0:
        score = 50
        line = "Not enough keywords in the job description to score overlap."
        return JobCandidateFitResult(
            overall_score=score,
            matched_skills=sorted(matched)[:20],
            missing_skills=[],
            summary_line=line,
        )

    ratio = len(matched) / max(n_job, 1)
    score = int(round(min(100, max(5, 15 + 85 * ratio))))

    matched_display = sorted({t for t in matched if len(t) > 2})[:24]
    missing_display = [t.replace("-", " ") for t in missing_candidates[:12]]

    line = (
        f"Roughly {score}% overlap between important words in the job post and what we see on the CV. "
        "This is an automatic keyword match, not a human verdict."
    )
    return JobCandidateFitResult(
        overall_score=score,
        matched_skills=matched_display,
        missing_skills=missing_display,
        summary_line=line,
    )


async def compute_job_candidate_fit(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> JobCandidateFitResult:
    job = await session.get(Job, job_id)
    cand = await session.get(Candidate, candidate_id)
    if job is None or cand is None or cand.job_id != job_id:
        return JobCandidateFitResult(
            overall_score=0,
            matched_skills=[],
            missing_skills=[],
            summary_line="Job or candidate not found.",
        )

    chunks = await top_k_chunks_for_job_candidate(session, job_id=job_id, candidate_id=candidate_id, k=10)
    if not chunks:
        stmt = (
            select(CandidateDocumentChunk)
            .where(CandidateDocumentChunk.candidate_id == candidate_id)
            .order_by(CandidateDocumentChunk.chunk_index)
            .limit(12)
        )
        rows = await session.scalars(stmt)
        chunks = list(rows.all())

    cv_sample = "\n".join(c.content for c in chunks[:12] if c.content)[:12000]
    parse_result = cand.parse_result if isinstance(cand.parse_result, dict) else None
    skill_set = _skills_from_structured(parse_result)
    skill_set |= _norm_tokens(cv_sample)

    return compute_fit_from_texts(
        job_title=job.title,
        job_description=job.description_plain,
        candidate_skills=skill_set,
        cv_sample=cv_sample,
    )


def parse_job_fit_from_candidate_row(parse_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(parse_result, dict):
        return None
    raw = parse_result.get("job_fit")
    if not isinstance(raw, dict):
        return None
    try:
        score = int(raw.get("overall_score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    ms = raw.get("matched_skills")
    miss = raw.get("missing_skills")
    line = raw.get("summary_line")
    return {
        "overall_score": score,
        "matched_skills": [str(x) for x in ms] if isinstance(ms, list) else [],
        "missing_skills": [str(x) for x in miss] if isinstance(miss, list) else [],
        "summary_line": line if isinstance(line, str) else "",
    }
