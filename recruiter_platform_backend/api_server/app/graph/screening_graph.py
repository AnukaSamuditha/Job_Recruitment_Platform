"""LangGraph multi-agent screening pipeline (local Ollama)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated, Any, Literal, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.agent_step import AgentStep
from app.models.candidate import Candidate
from app.models.screening_run import ScreeningRun
from app.schemas.cv_profile import CvStructuredProfile
from app.services.job_candidate_fit import compute_job_candidate_fit
from app.services.llama_parse_cv import llamaparse_pdf_to_structured_profile
from app.services.minio_storage import MinioStorageService
from app.services.vector_query import top_k_chunks_for_job_candidate
from app.ws.broadcast import ScreeningBroadcaster

logger = logging.getLogger(__name__)

_NO_LLM_TEXT = (
    "(No text returned from the chat model. Check Ollama at OLLAMA_BASE_URL, pull OLLAMA_CHAT_MODEL, "
    "and confirm the service is running.)"
)


def _coerce_llm_text(content: Any) -> str:
    """Normalize LangChain / provider message payloads to a single string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        return bytes(content).decode("utf-8", errors="replace")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
                else:
                    inner = block.get("content")
                    if isinstance(inner, str):
                        parts.append(inner)
            elif hasattr(block, "text") and isinstance(getattr(block, "text", None), str):
                parts.append(str(block.text))
        return "\n".join(parts)
    return str(content)


class ScreeningState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    job_id: str
    screening_run_id: str
    candidate_ids: list[str]
    parse_notes: str
    match_summary: str
    ranking_summary: str
    interview_summary: str
    needs_reparse: bool


async def _log_step(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    agent_name: str,
    step_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        AgentStep(
            screening_run_id=run_id,
            agent_name=agent_name,
            step_type=step_type,
            payload=payload,
        )
    )
    await session.flush()


def build_screening_graph(
    session_factory: async_sessionmaker,
    broadcaster: ScreeningBroadcaster,
    minio: MinioStorageService,
) -> Any:
    settings = get_settings()
    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_chat_model,
        temperature=0.2,
    )

    async def cv_parser(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await broadcaster.publish(
            str(run_id), {"type": "parsing", "detail": "CV Parser agent (LlamaParse + schema)"}
        )
        api_key = (get_settings().llama_cloud_api_key or "").strip()
        notes: list[str] = []
        queued_ids = list(state.get("candidate_ids") or [])

        async with session_factory() as session:
            await _log_step(
                session,
                run_id=run_id,
                agent_name="cv_parser",
                step_type="start",
                payload={"candidate_ids": queued_ids, "engine": "llamaparse"},
            )
            await session.commit()

        async with session_factory() as session:
            if not queued_ids:
                warn = (
                    "cv_parser: candidate_ids was empty — no per-candidate structured parse was performed. "
                    "Screening runs should include at least one candidate id."
                )
                notes.append(warn)
                logger.warning(warn)
                await _log_step(
                    session,
                    run_id=run_id,
                    agent_name="cv_parser",
                    step_type="skipped",
                    payload={"detail": "empty_candidate_ids"},
                )
                await session.commit()
            for cid in queued_ids:
                cand = await session.get(Candidate, uuid.UUID(cid))
                if cand is None:
                    continue
                if not api_key:
                    msg = f"{cand.display_name}: LLAMA_CLOUD_API_KEY missing; skipped structured LlamaParse."
                    notes.append(msg)
                    logger.warning(msg)
                    await _log_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={"candidate_id": cid, "detail": "missing_llama_cloud_api_key"},
                    )
                    await broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg},
                    )
                    continue

                try:
                    pdf_bytes = await asyncio.to_thread(
                        minio.get_object_bytes, cand.cv_storage_key
                    )
                except Exception as exc:
                    msg = f"{cand.display_name}: could not load CV from object storage ({exc})."
                    notes.append(msg)
                    logger.exception("MinIO read failed for candidate %s", cid)
                    await _log_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={"candidate_id": cid, "detail": str(exc)},
                    )
                    await broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                file_name = f"{(cand.display_name or 'cv').strip() or 'cv'}.pdf"
                try:
                    profile = await llamaparse_pdf_to_structured_profile(
                        api_key=api_key,
                        pdf_bytes=pdf_bytes,
                        file_name=file_name,
                    )
                except Exception as exc:
                    msg = f"{cand.display_name}: LlamaParse structured extraction failed ({exc})."
                    notes.append(msg)
                    logger.exception("LlamaParse structured failed for %s", cid)
                    await _log_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={"candidate_id": cid, "detail": str(exc)},
                    )
                    await broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                merged: dict[str, Any] = dict(cand.parse_result) if cand.parse_result else {}
                merged["llamaparse_structured"] = profile.model_dump()
                merged["structured_summary"] = profile.to_parse_notes()
                cand.parse_result = merged
                extracted_name = (profile.full_name or "").strip()
                if extracted_name:
                    cand.display_name = extracted_name[:512]
                await session.flush()

                summary = profile.to_parse_notes()
                notes.append(f"## {cand.display_name}\n{summary}")

                await _log_step(
                    session,
                    run_id=run_id,
                    agent_name="cv_parser",
                    step_type="llamaparse_structured",
                    payload={
                        "candidate_id": cid,
                        "full_name": profile.full_name,
                        "skills_count": len(profile.skills),
                        "roles_count": len(profile.work_experience),
                        "schema": CvStructuredProfile.__name__,
                    },
                )

            await session.commit()

        text = "\n\n".join(notes) if notes else "No structured CV data extracted."
        return {
            "parse_notes": text,
            "messages": [AIMessage(content=f"[cv_parser] {text[:12000]}")],
        }

    async def skill_matcher(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        job_id = uuid.UUID(state["job_id"])
        await broadcaster.publish(
            str(run_id), {"type": "matching", "detail": "Skill Matcher (retrieve + LLM)"}
        )
        async with session_factory() as session:
            cand_ids = [uuid.UUID(x) for x in state.get("candidate_ids", [])]
            fit_lines: list[str] = []
            for cid in cand_ids[:12]:
                cand = await session.get(Candidate, cid)
                if cand is None:
                    continue
                fit = await compute_job_candidate_fit(session, job_id=job_id, candidate_id=cid)
                merged: dict[str, Any] = dict(cand.parse_result) if isinstance(cand.parse_result, dict) else {}
                merged["job_fit"] = fit.as_parse_blob(job_id=job_id)
                cand.parse_result = merged
                fit_lines.append(
                    f"- {cand.display_name} ({cid}): auto job match {fit.overall_score}/100; "
                    f"aligned tokens: {', '.join(fit.matched_skills[:8]) or '—'}; "
                    f"gaps vs posting: {', '.join(fit.missing_skills[:8]) or '—'}"
                )
            await session.flush()

            contexts: list[str] = []
            for cid in cand_ids[:5]:
                chunks = await top_k_chunks_for_job_candidate(
                    session, job_id=job_id, candidate_id=cid, k=6
                )
                if not chunks:
                    contexts.append(f"Candidate {cid}: (no embeddings yet)")
                    continue
                snippets = "\n---\n".join(c.content[:500] for c in chunks)
                contexts.append(f"Candidate {cid} top chunks:\n{snippets}")
            ctx_block = "\n\n".join(contexts) or "No chunk context."
            fit_block = "\n".join(fit_lines) if fit_lines else "(no job-fit scores computed)"
            prompt = (
                "You are a recruiting skill matcher. First respect the automatic keyword scores "
                "(same logic as the MCP tool compute_candidate_job_fit / gRPC ComputeCandidateJobFit); "
                "then use CV snippets and parse notes. Summarize fit in 3-5 bullet points.\n\n"
                f"Automatic job match scores:\n{fit_block}\n\n"
                f"Parse notes:\n{state.get('parse_notes','')}\n\nRetrieved:\n{ctx_block}"
            )
            msg = await llm.ainvoke([SystemMessage(content=prompt)])
            summary = _coerce_llm_text(getattr(msg, "content", None)).strip() or _NO_LLM_TEXT
            await _log_step(
                session,
                run_id=run_id,
                agent_name="skill_matcher",
                step_type="result",
                payload={"summary": summary[:4000]},
            )
            await session.commit()
        return {
            "match_summary": summary,
            "messages": [AIMessage(content=f"[skill_matcher] {summary}")],
        }

    async def ranker(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await broadcaster.publish(
            str(run_id), {"type": "ranking", "detail": "Ranking agent"}
        )
        prompt = (
            "Rank the candidates qualitatively based on the match summary. "
            "Return a short ordered list with one-line justifications.\n"
            f"{state.get('match_summary','')}"
        )
        msg = await llm.ainvoke([SystemMessage(content=prompt)])
        summary = _coerce_llm_text(getattr(msg, "content", None)).strip() or _NO_LLM_TEXT
        async with session_factory() as session:
            await _log_step(
                session,
                run_id=run_id,
                agent_name="ranker",
                step_type="result",
                payload={"summary": summary[:4000]},
            )
            await session.commit()
        return {
            "ranking_summary": summary,
            "messages": [AIMessage(content=f"[ranker] {summary}")],
        }

    async def interview_gen(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await broadcaster.publish(
            str(run_id), {"type": "interview_gen", "detail": "Interview question agent"}
        )
        prompt = (
            "Propose 5 interview questions (mix technical and behavioral) informed by this ranking.\n"
            f"{state.get('ranking_summary','')}"
        )
        msg = await llm.ainvoke([SystemMessage(content=prompt)])
        summary = _coerce_llm_text(getattr(msg, "content", None)).strip() or _NO_LLM_TEXT
        async with session_factory() as session:
            await _log_step(
                session,
                run_id=run_id,
                agent_name="interview",
                step_type="result",
                payload={"summary": summary[:4000]},
            )
            run = await session.get(ScreeningRun, run_id)
            if run:
                run.status = "completed"
            await session.commit()
        await broadcaster.publish(
            str(run_id), {"type": "done", "detail": "Screening graph completed"}
        )
        return {
            "interview_summary": summary,
            "messages": [AIMessage(content=f"[interview] {summary}")],
        }

    def route_after_matcher(state: ScreeningState) -> Literal["ranker", "cv_parser"]:
        if state.get("needs_reparse"):
            return "cv_parser"
        return "ranker"

    g = StateGraph(ScreeningState)
    g.add_node("cv_parser", cv_parser)
    g.add_node("skill_matcher", skill_matcher)
    g.add_node("ranker", ranker)
    g.add_node("interview", interview_gen)
    g.add_edge(START, "cv_parser")
    g.add_edge("cv_parser", "skill_matcher")
    g.add_conditional_edges("skill_matcher", route_after_matcher)
    g.add_edge("ranker", "interview")
    g.add_edge("interview", END)
    return g.compile()
