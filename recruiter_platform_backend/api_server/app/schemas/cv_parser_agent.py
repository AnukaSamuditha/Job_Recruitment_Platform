"""Structured output for the CV parser recruiter LLM step (persisted under ``parse_result["cv_parser_agent"]``)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

CV_PARSER_AGENT_DISCLAIMER = (
    "This assistive summary is not a hiring decision. Verify all facts against the CV and job requirements."
)

_MAX_ITEM_LEN = 500
_MIN_ALIGNMENT = 3
_MAX_ALIGNMENT = 6
_MIN_GAPS = 2
_MAX_GAPS = 4
_MAX_RISKS = 8

_ALIGNMENT_PAD: tuple[str, ...] = (
    "Skill and experience alignment with the role should be confirmed in interview using concrete examples.",
    "Compare the candidate's stated tools and domains with the job description where wording differs.",
    "Review the structured timeline against the role's seniority expectations if not fully inferable from the CV.",
)

_GAPS_PAD: tuple[str, ...] = (
    "Ask the candidate to clarify responsibilities and outcomes for their most relevant role.",
    "Confirm dates and employment sequence as written on the original CV.",
)


def _trim_list(items: list[str], *, max_items: int, max_len: int) -> list[str]:
    out: list[str] = []
    for x in items:
        if not isinstance(x, str):
            continue
        s = x.strip().replace("\x00", "")
        if not s:
            continue
        out.append(s[:max_len])
        if len(out) >= max_items:
            break
    return out


class CvParserAgentLlmCore(BaseModel):
    """Shape returned by the LLM (uncapped lists; ``finalize_cv_parser_agent`` enforces UI bounds)."""

    alignment_summary: list[str] = Field(default_factory=list)
    gaps_or_questions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

    @field_validator("alignment_summary", "gaps_or_questions", "risk_flags", mode="before")
    @classmethod
    def _coerce_str_lists(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        return [str(x) for x in v]


class CvParserAgentRead(BaseModel):
    """API + persistence shape for ``cv_parser_agent`` (includes fixed disclaimer and optional error)."""

    alignment_summary: list[str] = Field(default_factory=list)
    gaps_or_questions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    disclaimer: str = Field(default=CV_PARSER_AGENT_DISCLAIMER, max_length=1024)
    error: str | None = Field(default=None, max_length=2000)

    model_config = {"extra": "ignore"}


def finalize_cv_parser_agent(core: CvParserAgentLlmCore) -> CvParserAgentRead:
    """Clamp list sizes and string lengths; pad to minimum counts with neutral lines."""
    align = _trim_list(list(core.alignment_summary), max_items=_MAX_ALIGNMENT, max_len=_MAX_ITEM_LEN)
    gaps = _trim_list(list(core.gaps_or_questions), max_items=_MAX_GAPS, max_len=_MAX_ITEM_LEN)
    risks = _trim_list(list(core.risk_flags), max_items=_MAX_RISKS, max_len=_MAX_ITEM_LEN)

    while len(align) < _MIN_ALIGNMENT:
        align.append(_ALIGNMENT_PAD[len(align) % len(_ALIGNMENT_PAD)])
    align = align[:_MAX_ALIGNMENT]

    while len(gaps) < _MIN_GAPS:
        gaps.append(_GAPS_PAD[len(gaps) % len(_GAPS_PAD)])
    gaps = gaps[:_MAX_GAPS]

    return CvParserAgentRead(
        alignment_summary=align,
        gaps_or_questions=gaps,
        risk_flags=risks,
        disclaimer=CV_PARSER_AGENT_DISCLAIMER,
        error=None,
    )


def cv_parser_agent_read_from_stored(raw: object) -> CvParserAgentRead | None:
    """Best-effort parse of JSONB blob for API responses."""
    if not isinstance(raw, dict):
        return None
    try:
        return CvParserAgentRead.model_validate(raw)
    except Exception:
        return None
