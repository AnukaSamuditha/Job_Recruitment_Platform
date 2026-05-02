"""pgvector similarity helpers for Skill Matcher."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import CandidateDocumentChunk
from app.models.job import Job


async def top_k_chunks_for_job_candidate(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
    k: int = 8,
) -> list[CandidateDocumentChunk]:
    """Return CV chunks most similar to the job description embedding."""
    job = await session.get(Job, job_id)
    if job is None or job.embedding is None:
        return []
    # pgvector: cosine distance operator on column
    dist = CandidateDocumentChunk.embedding.cosine_distance(job.embedding)
    stmt = (
        select(CandidateDocumentChunk)
        .where(CandidateDocumentChunk.candidate_id == candidate_id)
        .order_by(dist)
        .limit(k)
    )
    res = await session.scalars(stmt)
    return list(res.all())
