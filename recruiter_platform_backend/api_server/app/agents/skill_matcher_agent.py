"""Skill matcher agent: job–CV fit scores, retrieval, LLM summary."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from app.agents.deps import ScreeningGraphDeps
from app.agents.runtime import LLM_EMPTY_REPLY, coerce_llm_message_content, log_agent_step
from app.agents.state import ScreeningState
from app.models.candidate import Candidate
from app.agents.tracing import make_trace
from app.prompts.skill_matcher_agent import build_skill_matcher_prompt
from app.services.job_candidate_fit import compute_job_candidate_fit
from app.services.vector_query import top_k_chunks_for_job_candidate


def create_skill_matcher_node(deps: ScreeningGraphDeps):
    llm = deps.llm

    async def skill_matcher(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        job_id = uuid.UUID(state["job_id"])
        await deps.broadcaster.publish(
            str(run_id), {"type": "matching", "detail": "Skill Matcher (retrieve + LLM)"}
        )
        async with deps.session_factory() as session:
            cand_ids = [uuid.UUID(x) for x in state.get("candidate_ids", [])]
            fit_lines: list[str] = []
            fit_tool_calls: list[dict[str, Any]] = []
            for cid in cand_ids[:12]:
                cand = await session.get(Candidate, cid)
                if cand is None:
                    continue
                fit = await compute_job_candidate_fit(session, job_id=job_id, candidate_id=cid)
                fit_tool_calls.append(
                    {
                        "name": "compute_job_candidate_fit",
                        "type": "service",
                        "input": {"job_id": str(job_id), "candidate_id": str(cid)},
                        "output": {
                            "overall_score": int(fit.overall_score),
                            "matched_skills_count": len(fit.matched_skills),
                            "missing_skills_count": len(fit.missing_skills),
                        },
                    }
                )
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
            prompt = build_skill_matcher_prompt(
                fit_block=fit_block,
                parse_notes=str(state.get("parse_notes") or ""),
                ctx_block=ctx_block,
            )
            msg = await llm.ainvoke([SystemMessage(content=prompt)])
            summary = coerce_llm_message_content(getattr(msg, "content", None)).strip() or LLM_EMPTY_REPLY
            await log_agent_step(
                session,
                run_id=run_id,
                agent_name="skill_matcher",
                step_type="result",
                payload={
                    "summary": summary[:4000],
                    "trace": make_trace(
                        inputs={
                            "job_id": str(job_id),
                            "candidate_ids": [str(x) for x in cand_ids[:12]],
                            "parse_notes_chars": len(state.get("parse_notes") or ""),
                        },
                        tool_calls=fit_tool_calls[:24],
                        outputs={
                            "summary_chars": len(summary),
                            "llm_tool": "ChatOllama",
                            "task": "skill_matcher_summary",
                        },
                    ),
                },
            )
            await session.commit()
        return {
            "match_summary": summary,
            "messages": [AIMessage(content=f"[skill_matcher] {summary}")],
        }

    return skill_matcher
