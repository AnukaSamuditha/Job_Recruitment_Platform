"""Job-scoped candidate REST routes (detail, CV preview, list, upload)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_broadcaster,
    get_db_session,
    get_embedding_service,
    get_minio,
    get_screening_graph,
)
from app.api.schemas import (
    CandidateCvPreviewRead,
    CandidateDetailRead,
    CandidateRead,
    CandidateContactRead,
    CandidateCvAnalysisRead,
    CandidateJobFitRead,
    CandidateJobScreeningRead,
)
from app.schemas.cv_parser_agent import cv_parser_agent_read_from_stored
from app.core.config import get_settings
from app.models.agent_step import AgentStep
from app.models.candidate import Candidate
from app.models.screening_run import ScreeningRun
from app.schemas.cv_profile import CvStructuredProfile
from app.services.candidate_insights import (
    agent_snippets_for_run,
    cv_parser_gap_hint,
    gap_hint_to_cv_analysis_payload,
    latest_cv_parser_step_for_candidate,
    latest_screening_run_for_job,
    latest_screening_snippets,
)
from app.services.candidate_service import CandidateService
from app.services.cv_pdf_preview import pdf_bytes_to_png_data_urls
from app.services.embedding_service import EmbeddingService
from app.services.job_candidate_fit import parse_job_fit_from_candidate_row
from app.services.job_service import JobService
from app.services.minio_storage import MinioStorageService
from app.services.screening_runner import schedule_screening_run
from app.ws.broadcast import ScreeningBroadcaster

router = APIRouter(prefix="/jobs", tags=["candidates"])


def _contact_from_parse(
    parse_result: dict[str, Any] | None,
    *,
    display_name: str,
) -> CandidateContactRead:
    if not isinstance(parse_result, dict):
        return CandidateContactRead(full_name=display_name.strip() or "")
    raw = parse_result.get("llamaparse_structured")
    if not isinstance(raw, dict):
        return CandidateContactRead(full_name=(display_name or "").strip())
    try:
        p = CvStructuredProfile.model_validate(raw)
        fn = (p.full_name or "").strip() or (display_name or "").strip()
        return CandidateContactRead(
            full_name=fn,
            email=(p.email or "").strip(),
            phone=(p.phone or "").strip(),
            location=(p.location or "").strip(),
            headline=(p.headline or "").strip(),
            summary=(p.summary or "").strip(),
        )
    except Exception:
        return CandidateContactRead(full_name=(display_name or "").strip())


def _cv_analysis_from_step(
    step: AgentStep | None,
    run: ScreeningRun | None,
) -> CandidateCvAnalysisRead:
    if step is None:
        return CandidateCvAnalysisRead()
    payload: dict[str, Any] = step.payload if isinstance(step.payload, dict) else {}
    rid = run.id if run is not None else None
    if step.step_type == "llamaparse_structured":
        return CandidateCvAnalysisRead(
            screening_run_id=rid,
            step_type=step.step_type,
            recorded_at=step.created_at,
            skills_count=payload.get("skills_count")
            if isinstance(payload.get("skills_count"), int)
            else None,
            roles_count=payload.get("roles_count")
            if isinstance(payload.get("roles_count"), int)
            else None,
            schema_name=payload.get("schema") if isinstance(payload.get("schema"), str) else None,
            detail=None,
        )
    if step.step_type == "error":
        detail = payload.get("detail")
        if not isinstance(detail, str):
            detail = str(detail) if detail is not None else "cv_parser error"
        return CandidateCvAnalysisRead(
            screening_run_id=rid,
            step_type=step.step_type,
            recorded_at=step.created_at,
            detail=detail[:2000],
        )
    return CandidateCvAnalysisRead(
        screening_run_id=rid,
        step_type=step.step_type,
        recorded_at=step.created_at,
    )


def _job_fit_read(parse_result: dict[str, Any] | None) -> CandidateJobFitRead | None:
    raw = parse_job_fit_from_candidate_row(parse_result)
    if not raw:
        return None
    return CandidateJobFitRead(
        overall_score=int(raw["overall_score"]),
        matched_skills=list(raw.get("matched_skills") or []),
        missing_skills=list(raw.get("missing_skills") or []),
        summary_line=str(raw.get("summary_line") or ""),
    )


@router.get("/{job_id}/candidates/{candidate_id}", response_model=CandidateDetailRead)
async def get_candidate_detail(
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateDetailRead:
    """Return one candidate's stored fields, CV-derived contact info, parse status, and latest job screening text."""
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    cand = await session.get(Candidate, candidate_id)
    if cand is None or cand.job_id != job_id:
        raise HTTPException(status_code=404, detail="Candidate not found")

    parse_result = cand.parse_result if isinstance(cand.parse_result, dict) else None
    parse_summary: str | None = None
    structured_profile: dict[str, Any] | None = None
    if parse_result:
        raw_sum = parse_result.get("structured_summary")
        if isinstance(raw_sum, str) and raw_sum.strip():
            parse_summary = raw_sum.strip()
        raw_profile = parse_result.get("llamaparse_structured")
        if isinstance(raw_profile, dict) and raw_profile:
            structured_profile = raw_profile

    step, run = await latest_cv_parser_step_for_candidate(
        session, job_id=job_id, candidate_id=candidate_id
    )
    cv_analysis = _cv_analysis_from_step(step, run)
    if (
        cv_analysis.step_type is None
        and cv_analysis.detail is None
        and cv_analysis.screening_run_id is None
    ):
        hint = await cv_parser_gap_hint(session, job_id=job_id, candidate_id=candidate_id)
        if hint:
            cv_analysis = CandidateCvAnalysisRead(**gap_hint_to_cv_analysis_payload(hint))

    latest_run = await latest_screening_run_for_job(session, job_id=job_id)
    snippets: dict[str, str] = {}
    if latest_run is not None:
        snippets = await agent_snippets_for_run(session, run_id=latest_run.id)
    job_screening = CandidateJobScreeningRead(
        screening_run_id=latest_run.id if latest_run else None,
        status=latest_run.status if latest_run else None,
        created_at=latest_run.created_at if latest_run else None,
        skill_match=snippets.get("skill_match"),
        ranking=snippets.get("ranking"),
        interview=snippets.get("interview"),
    )

    return CandidateDetailRead(
        id=cand.id,
        job_id=cand.job_id,
        display_name=cand.display_name,
        cv_storage_key=cand.cv_storage_key,
        created_at=cand.created_at,
        contact=_contact_from_parse(parse_result, display_name=cand.display_name),
        parse_summary=parse_summary,
        structured_profile=structured_profile,
        cv_analysis=cv_analysis,
        job_screening=job_screening,
        job_fit=_job_fit_read(parse_result),
        cv_parser_agent=cv_parser_agent_read_from_stored(
            parse_result.get("cv_parser_agent") if parse_result else None
        ),
    )


@router.get("/{job_id}/candidates", response_model=list[CandidateRead])
async def list_job_candidates(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[CandidateRead]:
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    rows = await CandidateService.list_for_job(session, job_id)
    out: list[CandidateRead] = []
    for c in rows:
        pr = c.parse_result if isinstance(c.parse_result, dict) else None
        fit = parse_job_fit_from_candidate_row(pr)
        out.append(
            CandidateRead(
                id=c.id,
                display_name=c.display_name,
                cv_storage_key=c.cv_storage_key,
                match_score=int(fit["overall_score"]) if fit else None,
                missing_skills=(fit.get("missing_skills") or [])[:8] if fit else [],
            )
        )
    return out


@router.get("/{job_id}/candidates/{candidate_id}/cv-preview", response_model=CandidateCvPreviewRead)
async def get_candidate_cv_preview(
    job_id: uuid.UUID,
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    storage: MinioStorageService = Depends(get_minio),
) -> CandidateCvPreviewRead:
    """Rasterize the stored CV PDF to PNG data URLs for the recruiter UI."""
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    cand = await session.get(Candidate, candidate_id)
    if cand is None or cand.job_id != job_id:
        raise HTTPException(status_code=404, detail="Candidate not found")

    settings = get_settings()
    try:
        pdf_bytes = await asyncio.to_thread(storage.get_object_bytes, cand.cv_storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not load CV from storage: {exc}",
        ) from exc

    def _render() -> list[str]:
        return pdf_bytes_to_png_data_urls(
            pdf_bytes,
            max_pages=settings.cv_preview_max_pages,
            max_width_px=settings.cv_preview_max_width_px,
        )

    pages = await asyncio.to_thread(_render)

    summary: str | None = None
    structured_profile: dict | None = None
    if isinstance(cand.parse_result, dict):
        raw_summary = cand.parse_result.get("structured_summary")
        if isinstance(raw_summary, str) and raw_summary.strip():
            summary = raw_summary.strip()
        raw_profile = cand.parse_result.get("llamaparse_structured")
        if isinstance(raw_profile, dict) and raw_profile:
            structured_profile = raw_profile

    screening = await latest_screening_snippets(session, job_id=job_id)
    screening_out = screening if screening else None

    return CandidateCvPreviewRead(
        pages=pages,
        summary_text=summary,
        structured_profile=structured_profile,
        screening=screening_out,
    )


@router.post("/{job_id}/candidates", status_code=201)
async def upload_candidate_cv(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    storage: MinioStorageService = Depends(get_minio),
    embed: EmbeddingService = Depends(get_embedding_service),
    broadcaster: ScreeningBroadcaster = Depends(get_broadcaster),
    graph: object = Depends(get_screening_graph),
    display_name: str = Form("Candidate"),
    file: UploadFile = File(...),
) -> dict[str, str]:
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        cand = await CandidateService.create_with_cv_pdf(
            session,
            job_id=job_id,
            display_name=display_name,
            file_bytes=data,
            filename=file.filename or "cv.pdf",
            storage=storage,
            embedding_service=embed,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    run = await schedule_screening_run(
        background_tasks=background_tasks,
        session=session,
        job_id=job_id,
        candidate_ids=[cand.id],
        graph=graph,
        broadcaster=broadcaster,
    )
    return {
        "candidate_id": str(cand.id),
        "cv_storage_key": cand.cv_storage_key,
        "screening_run_id": str(run.id),
    }


@router.post("/{job_id}/rank-all", status_code=201)
async def trigger_job_ranking(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    broadcaster: ScreeningBroadcaster = Depends(get_broadcaster),
    graph: object = Depends(get_screening_graph),
) -> dict[str, str]:
    """Fetch all candidates for this job and start a new joint screening run (ranking comparison)."""
    job = await JobService.get_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    candidates = await CandidateService.list_for_job(session, job_id)
    if not candidates:
        raise HTTPException(status_code=400, detail="No candidates to rank")

    cids = [c.id for c in candidates]

    run = await schedule_screening_run(
        background_tasks=background_tasks,
        session=session,
        job_id=job_id,
        candidate_ids=cids,
        graph=graph,
        broadcaster=broadcaster,
    )
    return {
        "screening_run_id": str(run.id),
    }


@router.get("/{job_id}/screening", response_model=CandidateJobScreeningRead)
async def get_job_screening(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateJobScreeningRead:
    """Return text blobs from the most recent screening run for this job (e.g. joint ranking)."""
    run = await latest_screening_run_for_job(session, job_id=job_id)
    snippets: dict[str, str] = {}
    if run is not None:
        snippets = await agent_snippets_for_run(session, run_id=run.id)

    return CandidateJobScreeningRead(
        screening_run_id=run.id if run else None,
        status=run.status if run else None,
        created_at=run.created_at if run else None,
        skill_match=snippets.get("skill_match"),
        ranking=snippets.get("ranking"),
        interview=snippets.get("interview"),
    )
