"""Candidates, CV ingestion, chunk embeddings."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.candidate import Candidate
from app.models.chunk import CandidateDocumentChunk
from app.services.embedding_service import EmbeddingService
from app.services.llama_parse_cv import llamaparse_pdf_to_markdown
from app.services.minio_storage import MinioStorageService
from app.services.text_chunker import chunk_text


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CandidateService:
    @staticmethod
    async def list_for_job(session: AsyncSession, job_id: uuid.UUID) -> list[Candidate]:
        res = await session.scalars(
            select(Candidate).where(Candidate.job_id == job_id).order_by(Candidate.created_at)
        )
        return list(res.all())

    @staticmethod
    async def create_with_cv_pdf(
        session: AsyncSession,
        *,
        job_id: uuid.UUID,
        display_name: str,
        file_bytes: bytes,
        filename: str,
        storage: MinioStorageService,
        embedding_service: EmbeddingService,
    ) -> Candidate:
        key = storage.put_cv(job_id, filename, file_bytes, content_type="application/pdf")
        cand = Candidate(
            job_id=job_id,
            display_name=display_name,
            cv_storage_key=key,
        )
        session.add(cand)
        await session.flush()
        await CandidateService.refresh_chunks_from_cv(
            session,
            cand,
            file_bytes,
            embedding_service,
        )
        return cand

    @staticmethod
    async def refresh_chunks_from_cv(
        session: AsyncSession,
        candidate: Candidate,
        pdf_bytes: bytes,
        embedding_service: EmbeddingService,
    ) -> None:
        settings = get_settings()
        key = (settings.llama_cloud_api_key or "").strip()
        if not key:
            raise ValueError(
                "LLAMA_CLOUD_API_KEY is not set. LlamaParse is required to read CV PDFs."
            )
        file_label = f"{(candidate.display_name or 'candidate').strip() or 'cv'}.pdf"
        text = await llamaparse_pdf_to_markdown(
            api_key=key,
            pdf_bytes=pdf_bytes,
            file_name=file_label,
        )
        th = _text_hash(text)
        candidate.cv_text_hash = th
        candidate.parse_result = {
            "source": "llamaparse",
            "ingest_stage": "markdown",
            "extracted_char_len": len(text),
        }
        await session.execute(
            delete(CandidateDocumentChunk).where(
                CandidateDocumentChunk.candidate_id == candidate.id
            )
        )
        chunks = chunk_text(text)
        if not chunks:
            await session.flush()
            return
        batch_size = 16
        idx = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            vectors = await embedding_service.embed_texts(batch)
            for j, (content, vec) in enumerate(zip(batch, vectors, strict=True)):
                session.add(
                    CandidateDocumentChunk(
                        candidate_id=candidate.id,
                        chunk_index=idx + j,
                        content=content,
                        embedding=vec,
                        embedding_model=settings.ollama_embed_model,
                    )
                )
            idx += len(batch)
        await session.flush()

    @staticmethod
    async def get_with_chunks(
        session: AsyncSession, candidate_id: uuid.UUID
    ) -> Candidate | None:
        res = await session.scalars(
            select(Candidate)
            .options(selectinload(Candidate.chunks))
            .where(Candidate.id == candidate_id)
        )
        return res.first()
