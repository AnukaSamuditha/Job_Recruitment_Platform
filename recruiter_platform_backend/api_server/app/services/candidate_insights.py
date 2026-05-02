"""Aggregate screening agent outputs for recruiter UI (latest run per job)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_step import AgentStep
from app.models.screening_run import ScreeningRun


async def latest_screening_run_for_job(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
) -> ScreeningRun | None:
    return (
        await session.scalars(
            select(ScreeningRun)
            .where(ScreeningRun.job_id == job_id)
            .order_by(desc(ScreeningRun.created_at))
            .limit(1)
        )
    ).first()


async def agent_snippets_for_run(session: AsyncSession, *, run_id: uuid.UUID) -> dict[str, str]:
    steps = (
        await session.scalars(
            select(AgentStep)
            .where(AgentStep.screening_run_id == run_id)
            .order_by(AgentStep.created_at)
        )
    ).all()

    out: dict[str, str] = {}
    for step in steps:
        payload: dict[str, Any] = step.payload if isinstance(step.payload, dict) else {}
        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            continue
        text = summary.strip()
        if step.agent_name == "skill_matcher" and step.step_type == "result":
            out["skill_match"] = text
        elif step.agent_name == "ranker" and step.step_type == "result":
            out["ranking"] = text
        elif step.agent_name == "interview" and step.step_type == "result":
            out["interview"] = text
    return out


async def latest_screening_snippets(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
) -> dict[str, str]:
    """Return text blobs from the most recent screening run for this job."""
    run = await latest_screening_run_for_job(session, job_id=job_id)
    if run is None:
        return {}
    return await agent_snippets_for_run(session, run_id=run.id)


async def latest_cv_parser_step_for_candidate(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> tuple[AgentStep | None, ScreeningRun | None]:
    """Most recent cv_parser outcome (success or error) logged for this candidate within this job."""
    cid = str(candidate_id)
    rows = (
        await session.execute(
            select(AgentStep, ScreeningRun)
            .join(ScreeningRun, AgentStep.screening_run_id == ScreeningRun.id)
            .where(ScreeningRun.job_id == job_id)
            .where(AgentStep.agent_name == "cv_parser")
            .where(AgentStep.step_type.in_(("llamaparse_structured", "error")))
            .order_by(desc(AgentStep.created_at))
        )
    ).all()
    for step, run in rows:
        payload: dict[str, Any] = step.payload if isinstance(step.payload, dict) else {}
        if payload.get("candidate_id") == cid:
            return step, run
    return None, None


async def cv_parser_gap_hint(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict[str, Any] | None:
    """When no structured/error cv_parser step exists for this candidate, infer why from other steps."""
    cid = str(candidate_id)
    start_rows = (
        await session.execute(
            select(AgentStep, ScreeningRun)
            .join(ScreeningRun, AgentStep.screening_run_id == ScreeningRun.id)
            .where(ScreeningRun.job_id == job_id)
            .where(AgentStep.agent_name == "cv_parser")
            .where(AgentStep.step_type == "start")
            .order_by(desc(AgentStep.created_at))
        )
    ).all()
    for step, run in start_rows:
        pl: dict[str, Any] = step.payload if isinstance(step.payload, dict) else {}
        raw_ids = pl.get("candidate_ids") or []
        id_strs = {str(x) for x in raw_ids}
        if cid in id_strs:
            return {
                "screening_run_id": run.id,
                "step_type": "pipeline_started_without_outcome",
                "recorded_at": step.created_at,
                "detail": (
                    "This screening run listed the candidate at cv_parser start but logged no "
                    "structured or error step afterward. Common causes: an older run used an empty "
                    "candidate_ids list (fixed in API: empty now defaults to all job candidates), or "
                    "the parser session failed before per-candidate logging."
                ),
            }

    any_cv = (
        await session.scalars(
            select(AgentStep.id)
            .join(ScreeningRun, AgentStep.screening_run_id == ScreeningRun.id)
            .where(ScreeningRun.job_id == job_id)
            .where(AgentStep.agent_name == "cv_parser")
            .limit(1)
        )
    ).first()
    if any_cv is None:
        return {
            "screening_run_id": None,
            "step_type": "no_cv_parser_activity",
            "recorded_at": None,
            "detail": (
                "No cv_parser agent steps exist for this job yet. Upload a CV (triggers screening) or "
                "POST /api/v1/jobs/{job_id}/screening-runs with candidate_ids."
            ),
        }

    return {
        "screening_run_id": None,
        "step_type": "parser_not_attributed",
        "recorded_at": None,
        "detail": (
            "Screening ran for this job but no cv_parser outcome is recorded for this candidate id. "
            "Try starting a new screening run including this candidate."
        ),
    }


def gap_hint_to_cv_analysis_payload(hint: dict[str, Any]) -> dict[str, Any]:
    """Shape gap hint dict for CandidateCvAnalysisRead construction."""
    rid = hint.get("screening_run_id")
    recorded = hint.get("recorded_at")
    return {
        "screening_run_id": rid if isinstance(rid, uuid.UUID) else None,
        "step_type": hint.get("step_type") if isinstance(hint.get("step_type"), str) else None,
        "recorded_at": recorded if isinstance(recorded, datetime) else None,
        "skills_count": None,
        "roles_count": None,
        "schema_name": None,
        "detail": hint.get("detail") if isinstance(hint.get("detail"), str) else None,
    }
