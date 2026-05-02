"""Ranker agent: qualitative ordering from match summary."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from app.agents.deps import ScreeningGraphDeps
from app.agents.runtime import LLM_EMPTY_REPLY, coerce_llm_message_content, log_agent_step
from app.agents.state import ScreeningState


def create_ranker_node(deps: ScreeningGraphDeps):
    llm = deps.llm

    async def ranker(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await deps.broadcaster.publish(
            str(run_id), {"type": "ranking", "detail": "Ranking agent"}
        )
        prompt = (
            "Rank the candidates qualitatively based on the match summary. "
            "Return a short ordered list with one-line justifications.\n"
            f"{state.get('match_summary','')}"
        )
        msg = await llm.ainvoke([SystemMessage(content=prompt)])
        summary = coerce_llm_message_content(getattr(msg, "content", None)).strip() or LLM_EMPTY_REPLY
        async with deps.session_factory() as session:
            await log_agent_step(
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

    return ranker
