"""Ranker agent: qualitative ordering from match summary."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.deps import ScreeningGraphDeps
from app.agents.runtime import LLM_EMPTY_REPLY, coerce_llm_message_content, log_agent_step
from app.agents.state import ScreeningState
from app.agents.tracing import make_trace
from app.prompts.ranker_agent import build_ranker_prompt


def create_ranker_node(deps: ScreeningGraphDeps):
    llm = deps.llm

    async def ranker(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await deps.broadcaster.publish(
            str(run_id), {"type": "ranking", "detail": "Ranking agent"}
        )
        prompt = build_ranker_prompt(match_summary=str(state.get("match_summary") or ""))
        msg = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = coerce_llm_message_content(getattr(msg, "content", None)).strip() or LLM_EMPTY_REPLY
        async with deps.session_factory() as session:
            await log_agent_step(
                session,
                run_id=run_id,
                agent_name="ranker",
                step_type="result",
                payload={
                    "summary": summary[:4000],
                    "trace": make_trace(
                        inputs={
                            "match_summary_chars": len(state.get("match_summary") or ""),
                            "match_summary_head": (state.get("match_summary") or "")[:600],
                        },
                        tool_calls=[
                            {
                                "name": "ChatOllama",
                                "type": "llm",
                                "task": "ranker",
                                "input": {"prompt_built_by": "build_ranker_prompt"},
                                "output": {"chars": len(summary)},
                            }
                        ],
                        outputs={"summary_chars": len(summary), "ok": True},
                    ),
                },
            )
            await session.commit()
        return {
            "ranking_summary": summary,
            "messages": [AIMessage(content=f"[ranker] {summary}")],
        }

    return ranker
