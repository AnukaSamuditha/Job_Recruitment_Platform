"""gRPC servicer: DB facade for MCP tools (see PLAN.md)."""

from __future__ import annotations

import asyncio
import uuid

import grpc
from grpc import aio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.candidate import Candidate
from app.services.candidate_service import CandidateService
from app.services.job_candidate_fit import compute_job_candidate_fit
from app.services.job_service import JobService
from app.services.minio_storage import MinioStorageService

from recruitment.v1 import recruitment_pb2, recruitment_pb2_grpc

_MAX_CV_PDF_BYTES = 15 * 1024 * 1024


def build_recruitment_servicer(
    session_factory: async_sessionmaker,
    *,
    minio: MinioStorageService,
) -> recruitment_pb2_grpc.RecruitmentDataServicer:
    class Servicer(recruitment_pb2_grpc.RecruitmentDataServicer):
        async def GetJob(
            self,
            request: recruitment_pb2.GetJobRequest,
            context: aio.ServicerContext,
        ) -> recruitment_pb2.GetJobResponse:
            try:
                jid = uuid.UUID(request.job_id)
            except ValueError:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("invalid job_id")
                return recruitment_pb2.GetJobResponse()
            async with session_factory() as session:
                job = await JobService.get_by_id(session, jid)
                if job is None:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return recruitment_pb2.GetJobResponse()
                pb = recruitment_pb2.Job(
                    id=str(job.id),
                    title=job.title,
                    company=job.company,
                    description_plain=job.description_plain,
                    has_embedding=job.embedding is not None,
                )
                return recruitment_pb2.GetJobResponse(job=pb)

        async def ListCandidates(
            self,
            request: recruitment_pb2.ListCandidatesRequest,
            context: aio.ServicerContext,
        ) -> recruitment_pb2.ListCandidatesResponse:
            try:
                jid = uuid.UUID(request.job_id)
            except ValueError:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("invalid job_id")
                return recruitment_pb2.ListCandidatesResponse()
            async with session_factory() as session:
                rows = await CandidateService.list_for_job(session, jid)
                out = [
                    recruitment_pb2.CandidateSummary(
                        id=str(c.id),
                        display_name=c.display_name,
                        cv_storage_key=c.cv_storage_key,
                    )
                    for c in rows
                ]
                return recruitment_pb2.ListCandidatesResponse(candidates=out)

        async def ComputeCandidateJobFit(
            self,
            request: recruitment_pb2.ComputeCandidateJobFitRequest,
            context: aio.ServicerContext,
        ) -> recruitment_pb2.ComputeCandidateJobFitResponse:
            try:
                jid = uuid.UUID(request.job_id.strip())
                cid = uuid.UUID(request.candidate_id.strip())
            except ValueError:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("invalid job_id or candidate_id")
                return recruitment_pb2.ComputeCandidateJobFitResponse()
            async with session_factory() as session:
                fit = await compute_job_candidate_fit(session, job_id=jid, candidate_id=cid)
                return recruitment_pb2.ComputeCandidateJobFitResponse(
                    overall_score=int(fit.overall_score),
                    matched_skills=fit.matched_skills,
                    missing_skills=fit.missing_skills,
                    summary_line=fit.summary_line,
                )

        async def GetCandidateCvPdf(
            self,
            request: recruitment_pb2.GetCandidateCvPdfRequest,
            context: aio.ServicerContext,
        ) -> recruitment_pb2.GetCandidateCvPdfResponse:
            try:
                jid = uuid.UUID(request.job_id.strip())
                cid = uuid.UUID(request.candidate_id.strip())
            except ValueError:
                return recruitment_pb2.GetCandidateCvPdfResponse(error="invalid job_id or candidate_id")
            async with session_factory() as session:
                cand = await session.get(Candidate, cid)
                if cand is None or cand.job_id != jid:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return recruitment_pb2.GetCandidateCvPdfResponse(error="candidate not found for job")
                try:
                    pdf_bytes = await asyncio.to_thread(minio.get_object_bytes, cand.cv_storage_key)
                except Exception as exc:  # noqa: BLE001
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    return recruitment_pb2.GetCandidateCvPdfResponse(
                        error=f"could not read cv from storage: {exc}",
                    )
                if len(pdf_bytes) > _MAX_CV_PDF_BYTES:
                    context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                    return recruitment_pb2.GetCandidateCvPdfResponse(
                        error=f"pdf exceeds max size ({_MAX_CV_PDF_BYTES} bytes)",
                    )
                return recruitment_pb2.GetCandidateCvPdfResponse(
                    pdf=pdf_bytes,
                    display_name=cand.display_name or "",
                )

    return Servicer()
