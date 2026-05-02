from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_embedding_service
from app.api.schemas import JobCreate, JobRead, JobUpdate
from app.services.embedding_service import EmbeddingService
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(session: AsyncSession = Depends(get_db_session)) -> list[JobRead]:
    jobs = await JobService.list_jobs(session)
    return [
        JobRead(
            id=j.id,
            title=j.title,
            company=j.company,
            description_plain=j.description_plain,
            has_embedding=j.embedding is not None,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.post("", response_model=JobRead, status_code=201)
async def create_job(
    body: JobCreate,
    session: AsyncSession = Depends(get_db_session),
    embed: EmbeddingService = Depends(get_embedding_service),
) -> JobRead:
    job = await JobService.create(
        session,
        title=body.title,
        company=body.company,
        description_html=body.description_html,
        embedding_service=embed,
    )
    await session.commit()
    return JobRead(
        id=job.id,
        title=job.title,
        company=job.company,
        description_plain=job.description_plain,
        has_embedding=job.embedding is not None,
        created_at=job.created_at,
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> JobRead:
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobRead(
        id=job.id,
        title=job.title,
        company=job.company,
        description_plain=job.description_plain,
        has_embedding=job.embedding is not None,
        created_at=job.created_at,
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    await session.delete(job)
    await session.commit()


@router.patch("/{job_id}", response_model=JobRead)
async def patch_job(
    job_id: uuid.UUID,
    body: JobUpdate,
    session: AsyncSession = Depends(get_db_session),
    embed: EmbeddingService = Depends(get_embedding_service),
) -> JobRead:
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    await JobService.update(
        session,
        job,
        title=body.title,
        company=body.company,
        description_html=body.description_html,
        embedding_service=embed,
    )
    await session.commit()
    return JobRead(
        id=job.id,
        title=job.title,
        company=job.company,
        description_plain=job.description_plain,
        has_embedding=job.embedding is not None,
        created_at=job.created_at,
    )
