"""Interview question agent + marks screening run completed."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from app.agents.deps import ScreeningGraphDeps
from app.agents.runtime import LLM_EMPTY_REPLY, coerce_llm_message_content, log_agent_step
from app.agents.state import ScreeningState
from app.models.screening_run import ScreeningRun


def create_interview_agent_node(deps: ScreeningGraphDeps):
    llm = deps.llm

    async def interview_gen(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await deps.broadcaster.publish(
            str(run_id), {"type": "interview_gen", "detail": "Interview question agent"}
        )
        prompt = (
            "Propose 5 interview questions (mix technical and behavioral) informed by this ranking.\n"
            f"{state.get('ranking_summary','')}"
        )
        msg = await llm.ainvoke([SystemMessage(content=prompt)])
        summary = coerce_llm_message_content(getattr(msg, "content", None)).strip() or LLM_EMPTY_REPLY
        async with deps.session_factory() as session:
            await log_agent_step(
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
        await deps.broadcaster.publish(
            str(run_id), {"type": "done", "detail": "Screening graph completed"}
        )
        return {
            "interview_summary": summary,
            "messages": [AIMessage(content=f"[interview] {summary}")],
        }

    return interview_gen
