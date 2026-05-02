"""Job persistence and mandatory job-description embeddings."""

from __future__ import annotations

import hashlib
import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.job import Job
from app.services.embedding_service import EmbeddingService
from app.services.html_plain import html_to_plain


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class JobService:
    @staticmethod
    async def get_by_id(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
        return await session.get(Job, job_id)

    @staticmethod
    async def list_jobs(session: AsyncSession) -> Sequence[Job]:
        res = await session.scalars(select(Job).order_by(Job.created_at.desc()))
        return res.all()

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        title: str,
        company: str,
        description_html: str,
        embedding_service: EmbeddingService,
    ) -> Job:
        plain = html_to_plain(description_html)
        job = Job(
            title=title,
            company=company,
            description_plain=plain,
        )
        session.add(job)
        await session.flush()
        await JobService._refresh_job_embedding(session, job, embedding_service)
        return job

    @staticmethod
    async def update(
        session: AsyncSession,
        job: Job,
        *,
        title: str | None = None,
        company: str | None = None,
        description_html: str | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> Job:
        if title is not None:
            job.title = title
        if company is not None:
            job.company = company
        if description_html is not None:
            job.description_plain = html_to_plain(description_html)
        await session.flush()
        if embedding_service is not None:
            await JobService._refresh_job_embedding(session, job, embedding_service)
        return job

    @staticmethod
    async def _refresh_job_embedding(
        session: AsyncSession,
        job: Job,
        embedding_service: EmbeddingService,
    ) -> None:
        plain = job.description_plain or ""
        h = _content_hash(plain)
        settings = get_settings()
        if job.description_hash == h and job.embedding is not None:
            return
        if not plain.strip():
            job.description_hash = h
            job.embedding = None
            job.embedding_model = None
            return
        vec = await embedding_service.embed_one(plain)
        job.description_hash = h
        job.embedding = vec
        job.embedding_model = settings.ollama_embed_model
        await session.flush()
