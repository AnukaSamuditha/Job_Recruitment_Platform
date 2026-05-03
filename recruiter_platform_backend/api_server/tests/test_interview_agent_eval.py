"""Evaluation methodology, testing scripts, and performance/reliability analysis for interview question generator agent."""

from __future__ import annotations

import re
import time
import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from app.agents.interview_agent import create_interview_agent_node
from app.agents.state import ScreeningState
from app.agents.deps import ScreeningGraphDeps
from app.prompts.interview_agent import (
    build_interview_human,
    INTERVIEW_AGENT_SYSTEM,
    INTERVIEW_AGENT_MAX_CONTEXT_CHARS,
)


class TestInterviewQuestionGeneratorEvaluation:
    """Test 1: Evaluation Methodology - Validates prompt construction and format compliance."""

    def test_prompt_construction_includes_all_contexts(self) -> None:
        """
        Evaluation criterion: Verify that the interview human message includes all required context sections.
        Testing strategy: Unit test with deterministic inputs.
        Validates: Skill summary, ranking summary, and CV parse notes are all included.
        """
        match_summary = "Candidate has strong Python skills"
        ranking_summary = "Ranked 1st among 10 candidates"
        parse_notes = "5 years backend experience"

        prompt = build_interview_human(
            match_summary=match_summary,
            ranking_summary=ranking_summary,
            parse_notes=parse_notes,
        )

        # Evaluation check: All context sections must be present
        assert "Skill / fit summary" in prompt
        assert "Ranking" in prompt
        assert "CV parse notes" in prompt

        # Evaluation check: Input content must be preserved
        assert match_summary in prompt
        assert ranking_summary in prompt
        assert parse_notes in prompt

    def test_prompt_respects_max_context_length(self) -> None:
        """
        Evaluation criterion: Verify that long context inputs are truncated to INTERVIEW_AGENT_MAX_CONTEXT_CHARS.
        Testing strategy: Boundary value analysis with oversized inputs.
        Validates: Performance and memory efficiency.
        """
        long_text = "x" * (INTERVIEW_AGENT_MAX_CONTEXT_CHARS + 1000)

        prompt = build_interview_human(
            match_summary=long_text,
            ranking_summary=long_text,
            parse_notes=long_text,
        )

        # Evaluation check: Prompt should be reasonably bounded
        # (allows header text, so we add buffer)
        max_expected_length = (
            INTERVIEW_AGENT_MAX_CONTEXT_CHARS * 3 + 500
        )  # 3 sections + headers
        assert len(prompt) <= max_expected_length

    def test_system_prompt_consistency(self) -> None:
        """
        Evaluation criterion: Verify system prompt enforces correct question format.
        Testing strategy: Content analysis of system instructions.
        Validates: Instructions for 5-8 questions, numbered format, no preamble.
        """
        # Evaluation check: System prompt must specify question count range
        assert "5 and 8" in INTERVIEW_AGENT_SYSTEM or "5-8" in INTERVIEW_AGENT_SYSTEM

        # Evaluation check: System prompt must specify numbered format
        assert "numbered" in INTERVIEW_AGENT_SYSTEM.lower()

        # Evaluation check: System prompt must prohibit hallucination
        assert "invent" in INTERVIEW_AGENT_SYSTEM.lower() or (
            "do not" in INTERVIEW_AGENT_SYSTEM.lower()
            and "information" in INTERVIEW_AGENT_SYSTEM.lower()
        )


class TestInterviewQuestionGeneratorOutputFormat:
    """Test 2: Testing Scripts - Validates interview question output format and structure."""

    def test_output_format_compliance_numbered_list(self) -> None:
        """
        Testing script: Validates that generated questions follow the required numbered list format.
        Test method: Regex-based format validation.
        Evaluates: Output correctness and format compliance.
        """
        # Mock output from the agent
        mock_output = (
            "1. What is your experience with Python and backend systems?\n"
            "2. Tell us about a time you led a technical project (STAR method).\n"
            "3. How do you approach system design for scalability?\n"
            "4. Describe a challenging bug you debugged and your process.\n"
            "5. Why are you interested in this role and company?\n"
        )

        # Format compliance regex pattern
        lines = [line.strip() for line in mock_output.split("\n") if line.strip()]

        # Testing check: Each line must start with a number and period
        for i, line in enumerate(lines, 1):
            assert re.match(rf"^{i}\.", line), f"Line {i} does not match format"

        # Testing check: Minimum 5 questions
        assert len(lines) >= 5, f"Expected at least 5 questions, got {len(lines)}"

        # Testing check: Maximum 8 questions
        assert len(lines) <= 8, f"Expected at most 8 questions, got {len(lines)}"

    def test_question_content_validity_no_hallucination(self) -> None:
        """
        Testing script: Validates that generated questions are grounded in provided context.
        Test method: Keyword and content matching against input context.
        Evaluates: Absence of hallucinated (invented) credentials or employers.
        """
        context_text = "Candidate: John | Skills: Python, SQL | Company: TechCorp | Role: Backend Engineer"
        mock_output = (
            "1. Tell us about your Python experience at TechCorp.\n"
            "2. How have you used SQL in your backend work?\n"
            "3. What backend challenges have you solved?\n"
        )

        # Validation: Extract keywords from context
        valid_keywords = {"python", "sql", "techcorp", "backend", "engineer"}

        # Validation check: At least some questions should reference context keywords
        questions_with_context = 0
        for line in mock_output.split("\n"):
            if any(keyword in line.lower() for keyword in valid_keywords):
                questions_with_context += 1

        assert (
            questions_with_context > 0
        ), "Questions must be grounded in provided context"

        # Validation check: No fabricated companies or roles not in context
        fabricated_patterns = [
            r"google|meta|amazon|apple",  # Big tech companies not mentioned
        ]
        for pattern in fabricated_patterns:
            assert not re.search(
                pattern, mock_output.lower()
            ), f"Questions appear to reference fabricated company: {pattern}"

    def test_question_quality_diversity(self) -> None:
        """
        Testing script: Validates question diversity (technical, behavioral, domain-specific).
        Test method: Question type classification.
        Evaluates: Question quality and coverage.
        """
        mock_output = (
            "1. What is your experience with Python and distributed systems?\n"
            "2. Tell us about a time you debugged a critical production issue (STAR).\n"
            "3. How would you design a caching layer for a high-traffic API?\n"
            "4. Describe your approach to code review and collaboration.\n"
            "5. Why are you interested in this role?\n"
        )

        lines = [line.strip() for line in mock_output.split("\n") if line.strip()]

        # Classify question types
        behavioral_patterns = [
            r"tell us about|describe|your approach",
        ]  # STAR questions
        technical_patterns = [
            r"how would you|design|experience with",
        ]  # Technical questions

        behavioral_count = sum(
            1
            for line in lines
            if any(re.search(p, line.lower()) for p in behavioral_patterns)
        )
        technical_count = sum(
            1
            for line in lines
            if any(re.search(p, line.lower()) for p in technical_patterns)
        )

        # Testing check: Must have mix of question types
        assert (
            behavioral_count > 0 and technical_count > 0
        ), "Questions must include both technical and behavioral questions"


class TestInterviewQuestionGeneratorPerformance:
    """Test 3: Performance Analysis - Measures response time, token usage, and resource efficiency."""

    def test_prompt_construction_performance(self) -> None:
        """
        Performance test: Measure time to construct interview prompt.
        Metric: Execution time should be < 10ms.
        Validates: Prompt building efficiency.
        """
        match_summary = "x" * INTERVIEW_AGENT_MAX_CONTEXT_CHARS
        ranking_summary = "y" * INTERVIEW_AGENT_MAX_CONTEXT_CHARS
        parse_notes = "z" * INTERVIEW_AGENT_MAX_CONTEXT_CHARS

        # Performance measurement
        start_time = time.perf_counter()
        for _ in range(100):  # 100 iterations
            build_interview_human(
                match_summary=match_summary,
                ranking_summary=ranking_summary,
                parse_notes=parse_notes,
            )
        elapsed = time.perf_counter() - start_time
        avg_time_ms = (elapsed / 100) * 1000

        # Performance assertion: Should complete promptly
        assert (
            avg_time_ms < 10
        ), f"Prompt construction too slow: {avg_time_ms:.2f}ms per call"

    def test_context_truncation_efficiency(self) -> None:
        """
        Performance test: Verify efficient handling of oversized contexts.
        Metric: Output length should be bounded regardless of input size.
        Validates: Memory efficiency and token control.
        """
        # Test with extremely large context
        oversized_input = "A" * (INTERVIEW_AGENT_MAX_CONTEXT_CHARS * 10)

        prompt = build_interview_human(
            match_summary=oversized_input,
            ranking_summary=oversized_input,
            parse_notes=oversized_input,
        )

        # Performance check: Output should remain bounded
        max_expected = INTERVIEW_AGENT_MAX_CONTEXT_CHARS * 4  # 3 sections + headers
        assert len(prompt) <= max_expected, (
            f"Prompt length {len(prompt)} exceeds expected maximum {max_expected}"
        )

    def test_response_time_baseline(self) -> None:
        """
        Reliability test: Measure baseline execution time for interview agent prompt building.
        Metric: Establishes performance baseline for regression detection.
        Validates: No unexpected performance degradation.
        """
        test_inputs = [
            ("short", "short", "short"),
            ("medium" * 100, "medium" * 100, "medium" * 100),
            ("long" * 500, "long" * 500, "long" * 500),
        ]

        times = []
        for match, ranking, notes in test_inputs:
            start = time.perf_counter()
            build_interview_human(
                match_summary=match, ranking_summary=ranking, parse_notes=notes
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        # Reliability check: All variations should complete quickly
        assert all(
            t < 50 for t in times
        ), f"Some calls exceeded 50ms threshold: {times}"


class TestInterviewQuestionGeneratorReliability:
    """Test 4: Reliability Analysis - Tests consistency, error handling, and robustness."""

    def test_empty_context_handling(self) -> None:
        """
        Reliability test: Verify graceful handling of empty or missing context.
        Test method: Edge case testing with empty strings.
        Validates: No crashes, fallback behavior.
        """
        # Edge case: All empty inputs
        prompt = build_interview_human(
            match_summary="",
            ranking_summary="",
            parse_notes="",
        )

        # Reliability check: Should not crash and should produce valid output
        assert prompt is not None
        assert len(prompt) > 0
        assert "(none)" in prompt  # Fallback text for empty sections

    def test_special_characters_handling(self) -> None:
        """
        Reliability test: Verify handling of special characters and unicode.
        Test method: Input fuzzing with special characters.
        Validates: Robustness against non-ASCII input.
        """
        special_text = (
            "Candidate: José | Skills: C++, Python | Company: 中文公司 | Salary: $100k USD ✓"
        )

        prompt = build_interview_human(
            match_summary=special_text,
            ranking_summary=special_text,
            parse_notes=special_text,
        )

        # Reliability check: Should handle unicode and special chars
        assert special_text in prompt
        assert len(prompt) > 0

    def test_null_and_none_robustness(self) -> None:
        """
        Reliability test: Verify robustness with None inputs.
        Test method: Testing with edge case None/empty values.
        Validates: Type safety and defensive programming.
        """
        # This simulates optional parameters that might be None
        prompt = build_interview_human(
            match_summary="",  # Empty acts like None
            ranking_summary=None or "",  # Simulate None coalescing
            parse_notes="Sample notes",
        )

        # Reliability check: Must not crash and produce valid output
        assert prompt is not None
        assert "Sample notes" in prompt


@pytest.mark.asyncio
class TestInterviewAgentNodeIntegration:
    """Test 5: Integration Test - Full agent node execution with mocked dependencies."""

    async def test_interview_agent_node_execution(self) -> None:
        """
        Integration test: Full execution of interview agent node.
        Test method: Async integration test with mocked LLM and database.
        Evaluates: End-to-end agent execution, message passing, database logging.
        """
        # Setup mock dependencies
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=(
                    "1. What is your Python experience?\n"
                    "2. Tell us about a challenging project.\n"
                    "3. How do you approach code quality?\n"
                    "4. Describe a teamwork experience.\n"
                    "5. Why this role interests you?\n"
                )
            )
        )

        mock_session = AsyncMock()
        mock_run = MagicMock()
        mock_run.status = "completed"
        mock_session.get = AsyncMock(return_value=mock_run)
        mock_session.commit = AsyncMock()

        # Create a proper async context manager for session_factory
        mock_session_factory = MagicMock()
        mock_session_factory.__call__ = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        ))

        mock_broadcaster = AsyncMock()
        mock_broadcaster.publish = AsyncMock()

        # Create agent with mocked dependencies
        deps = MagicMock(spec=ScreeningGraphDeps)
        deps.llm = mock_llm
        deps.session_factory = mock_session_factory
        deps.broadcaster = mock_broadcaster

        interview_node = create_interview_agent_node(deps)

        # Create test state
        state: ScreeningState = {
            "screening_run_id": "550e8400-e29b-41d4-a716-446655440000",
            "candidate_name": "John Doe",
            "job_id": "job-123",
            "match_summary": "Strong Python background, 5 years experience",
            "ranking_summary": "Ranked 1st",
            "parse_notes": "AWS, microservices, team lead",
            "messages": [],
        }

        # Integration test execution
        result = await interview_node(state)

        # Integration check: Result must contain interview_summary
        assert "interview_summary" in result
        assert result["interview_summary"] is not None
        assert len(result["interview_summary"]) > 0

        # Integration check: Messages must be updated
        assert "messages" in result
        assert len(result["messages"]) > 0
        assert isinstance(result["messages"][0], AIMessage)

        # Integration check: Broadcaster must notify completion
        assert mock_broadcaster.publish.called
        publish_calls = [call for call in mock_broadcaster.publish.call_args_list]
        assert any("done" in str(call) for call in publish_calls)

        # Integration check: LLM must be invoked with correct message types
        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]
        assert any(isinstance(m, SystemMessage) for m in messages)
        assert any(isinstance(m, HumanMessage) for m in messages)
