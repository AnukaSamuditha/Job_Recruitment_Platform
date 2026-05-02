"""Property-based and golden tests for CV parser agent structured output (no Ollama)."""

from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.cv_parser_agent import (
    CV_PARSER_AGENT_DISCLAIMER,
    CvParserAgentLlmCore,
    CvParserAgentRead,
    cv_parser_agent_read_from_stored,
    finalize_cv_parser_agent,
)


def test_finalize_golden_minimal() -> None:
    core = CvParserAgentLlmCore(
        alignment_summary=["A", "B"],
        gaps_or_questions=["Q1"],
        risk_flags=[],
    )
    out = finalize_cv_parser_agent(core)
    assert 3 <= len(out.alignment_summary) <= 6
    assert 2 <= len(out.gaps_or_questions) <= 4
    assert out.risk_flags == []
    assert out.disclaimer == CV_PARSER_AGENT_DISCLAIMER
    assert out.error is None


def test_finalize_respects_max_lengths() -> None:
    long_s = "x" * 2000
    core = CvParserAgentLlmCore(
        alignment_summary=[long_s] * 10,
        gaps_or_questions=[long_s] * 10,
        risk_flags=[long_s] * 20,
    )
    out = finalize_cv_parser_agent(core)
    assert len(out.alignment_summary) == 6
    assert len(out.gaps_or_questions) == 4
    assert len(out.risk_flags) == 8
    for lst in (out.alignment_summary, out.gaps_or_questions, out.risk_flags):
        for line in lst:
            assert len(line) <= 500


@settings(max_examples=80)
@given(
    align=st.lists(
        st.text(
            alphabet=string.ascii_letters + string.digits + " .,-",
            min_size=1,
            max_size=120,
        ),
        max_size=8,
    ),
    gaps=st.lists(
        st.text(alphabet=string.ascii_letters + string.digits + " ", min_size=1, max_size=80),
        max_size=4,
    ),
    risks=st.lists(
        st.text(alphabet=string.ascii_letters + string.digits + " ", min_size=0, max_size=60),
        max_size=8,
    ),
)
def test_finalize_property_bounds(align: list[str], gaps: list[str], risks: list[str]) -> None:
    core = CvParserAgentLlmCore(alignment_summary=align, gaps_or_questions=gaps, risk_flags=risks)
    out = finalize_cv_parser_agent(core)
    assert 3 <= len(out.alignment_summary) <= 6
    assert 2 <= len(out.gaps_or_questions) <= 4
    assert len(out.risk_flags) <= 8
    assert out.disclaimer == CV_PARSER_AGENT_DISCLAIMER
    for line in out.alignment_summary + out.gaps_or_questions + out.risk_flags:
        assert "\x00" not in line
        assert len(line) <= 500


def test_read_from_stored_roundtrip() -> None:
    original = CvParserAgentRead(
        alignment_summary=["a", "b", "c"],
        gaps_or_questions=["x", "y"],
        risk_flags=["gap"],
        disclaimer=CV_PARSER_AGENT_DISCLAIMER,
        error=None,
    )
    blob = original.model_dump()
    parsed = cv_parser_agent_read_from_stored(blob)
    assert parsed is not None
    assert parsed.model_dump() == blob


def test_read_from_stored_invalid_returns_none() -> None:
    assert cv_parser_agent_read_from_stored("not-a-dict") is None
    assert cv_parser_agent_read_from_stored({"alignment_summary": "wrong"}) is None


def test_no_null_bytes_after_finalize() -> None:
    core = CvParserAgentLlmCore(
        alignment_summary=["ok\x00bad", "b", "c"],
        gaps_or_questions=["q1", "q2"],
        risk_flags=[],
    )
    out = finalize_cv_parser_agent(core)
    joined = "\n".join(out.alignment_summary + out.gaps_or_questions + out.risk_flags)
    assert "\x00" not in joined
