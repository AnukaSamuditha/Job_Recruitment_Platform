"""Ollama-backed recruiter brief for the CV parser agent (post–structured extraction)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.prompts.cv_parser_agent import CV_PARSER_RECRUITER_SYSTEM, build_cv_parser_recruiter_human
from app.schemas.cv_profile import CvStructuredProfile
from app.schemas.cv_parser_agent import (
    CV_PARSER_AGENT_DISCLAIMER,
    CvParserAgentLlmCore,
    CvParserAgentRead,
    finalize_cv_parser_agent,
)

logger = logging.getLogger(__name__)

_MAX_JOB_DESC_CHARS = 8000
_MAX_PROFILE_JSON_CHARS = 14000


def _compact_profile_json(profile: CvStructuredProfile) -> str:
    raw = json.dumps(profile.model_dump(), ensure_ascii=False)
    if len(raw) > _MAX_PROFILE_JSON_CHARS:
        return raw[:_MAX_PROFILE_JSON_CHARS] + "\n…(truncated)"
    return raw


async def run_cv_parser_recruiter_brief(
    llm: ChatOllama,
    *,
    profile: CvStructuredProfile,
    job_title: str,
    job_company: str,
    job_description_plain: str,
) -> CvParserAgentRead:
    """
    Call the local chat model with structured output, then normalize into ``CvParserAgentRead``.

    Raises on total failure (caller should catch and persist ``error`` only).
    """
    desc = (job_description_plain or "").strip()
    if len(desc) > _MAX_JOB_DESC_CHARS:
        desc = desc[:_MAX_JOB_DESC_CHARS] + "\n…(truncated)"

    human = build_cv_parser_recruiter_human(
        job_title=job_title,
        job_company=job_company,
        job_description_plain=desc or "",
        structured_cv_json=_compact_profile_json(profile),
    )

    structured_llm = llm.with_structured_output(CvParserAgentLlmCore)
    messages = [
        SystemMessage(content=CV_PARSER_RECRUITER_SYSTEM),
        HumanMessage(content=human),
    ]
    try:
        parsed: Any = await structured_llm.ainvoke(messages)
    except Exception:
        logger.exception("cv_parser recruiter LLM invoke failed")
        raise

    if isinstance(parsed, dict):
        core = CvParserAgentLlmCore.model_validate(parsed)
    elif isinstance(parsed, CvParserAgentLlmCore):
        core = parsed
    elif hasattr(parsed, "model_dump"):
        core = CvParserAgentLlmCore.model_validate(parsed.model_dump())
    else:
        raise TypeError(f"Unexpected structured LLM output type: {type(parsed).__name__}")

    out = finalize_cv_parser_agent(core)
    return out.model_copy(update={"disclaimer": CV_PARSER_AGENT_DISCLAIMER})
