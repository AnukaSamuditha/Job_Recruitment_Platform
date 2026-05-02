from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_broadcaster,
    get_db_session,
    get_screening_graph,
)
from app.api.schemas import ScreeningRunCreate, ScreeningRunRead
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.services.screening_runner import schedule_screening_run
from app.ws.broadcast import ScreeningBroadcaster

router = APIRouter(tags=["screening"])


@router.post("/jobs/{job_id}/screening-runs", response_model=ScreeningRunRead, status_code=201)
async def create_screening_run(
    job_id: uuid.UUID,
    body: ScreeningRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    broadcaster: ScreeningBroadcaster = Depends(get_broadcaster),
    graph: object = Depends(get_screening_graph),
) -> ScreeningRunRead:
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    candidate_ids = list(body.candidate_ids)
    if not candidate_ids:
        rows = await CandidateService.list_for_job(session, job_id)
        candidate_ids = [c.id for c in rows]
    if not candidate_ids:
        raise HTTPException(
            status_code=400,
            detail="No candidates to screen. Upload at least one CV for this job, or pass candidate_ids.",
        )
    run = await schedule_screening_run(
        background_tasks=background_tasks,
        session=session,
        job_id=job_id,
        candidate_ids=candidate_ids,
        graph=graph,
        broadcaster=broadcaster,
    )
    return ScreeningRunRead(
        id=run.id, job_id=run.job_id, status=run.status, created_at=run.created_at
    )
