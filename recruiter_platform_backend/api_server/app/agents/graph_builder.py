"""Assemble the LangGraph screening workflow from per-agent nodes."""

from __future__ import annotations

from typing import Any, Literal

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.cv_parser_agent import create_cv_parser_node
from app.agents.deps import ScreeningGraphDeps
from app.agents.interview_agent import create_interview_agent_node
from app.agents.ranker_agent import create_ranker_node
from app.agents.skill_matcher_agent import create_skill_matcher_node
from app.agents.state import ScreeningState
from app.core.config import get_settings
from app.services.minio_storage import MinioStorageService
from app.ws.broadcast import ScreeningBroadcaster


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
    deps = ScreeningGraphDeps(
        session_factory=session_factory,
        broadcaster=broadcaster,
        minio=minio,
        llm=llm,
    )

    cv_parser = create_cv_parser_node(deps)
    skill_matcher = create_skill_matcher_node(deps)
    ranker = create_ranker_node(deps)
    interview_gen = create_interview_agent_node(deps)

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
