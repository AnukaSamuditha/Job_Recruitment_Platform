"""Background LangGraph screening runs (shared by upload and manual API)."""

from __future__ import annotations

import logging
import uuid

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models.screening_run import ScreeningRun
from app.ws.broadcast import ScreeningBroadcaster

logger = logging.getLogger(__name__)


async def run_screening_task(
    *,
    run_id: uuid.UUID,
    job_id: uuid.UUID,
    candidate_ids: list[str],
    graph: object,
    broadcaster: ScreeningBroadcaster,
) -> None:
    await broadcaster.publish(
        str(run_id), {"type": "screening_started", "job_id": str(job_id)}
    )
    try:
        await graph.ainvoke(
            {
                "job_id": str(job_id),
                "screening_run_id": str(run_id),
                "candidate_ids": candidate_ids,
                "needs_reparse": False,
                "messages": [],
            }
        )
    except Exception:
        logger.exception("Screening graph failed run_id=%s", run_id)
        await broadcaster.publish(
            str(run_id),
            {"type": "error", "detail": "screening_failed"},
        )
        async with async_session_maker() as session:
            run = await session.get(ScreeningRun, run_id)
            if run:
                run.status = "failed"
                await session.commit()


async def schedule_screening_run(
    *,
    background_tasks: BackgroundTasks,
    session: AsyncSession,
    job_id: uuid.UUID,
    candidate_ids: list[uuid.UUID],
    graph: object,
    broadcaster: ScreeningBroadcaster,
) -> ScreeningRun:
    run = ScreeningRun(job_id=job_id, status="running")
    session.add(run)
    await session.flush()
    cids = [str(c) for c in candidate_ids]
    await session.commit()
    background_tasks.add_task(
        run_screening_task,
        run_id=run.id,
        job_id=job_id,
        candidate_ids=cids,
        graph=graph,
        broadcaster=broadcaster,
    )
    return run
