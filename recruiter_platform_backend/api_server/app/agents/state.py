"""Shared LangGraph state for the screening pipeline."""

from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


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
