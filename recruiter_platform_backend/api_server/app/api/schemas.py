from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.cv_parser_agent import CvParserAgentRead


class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    company: str = Field(default="", max_length=512)
    description_html: str = ""


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    company: str | None = Field(default=None, max_length=512)
    description_html: str | None = None


class JobRead(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    description_plain: str
    has_embedding: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ScreeningRunCreate(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(default_factory=list)


class ScreeningRunRead(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateRead(BaseModel):
    id: uuid.UUID
    display_name: str
    cv_storage_key: str
    match_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Last computed job overlap score (0–100), if screening has run.",
    )
    missing_skills: list[str] = Field(
        default_factory=list,
        description="Up to eight keywords from the job post not seen on the CV (heuristic).",
    )

    model_config = {"from_attributes": True}


class CandidateContactRead(BaseModel):
    """Contact and headline fields extracted from the CV (LlamaParse structured profile)."""

    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    headline: str = ""
    summary: str = ""


class CandidateCvAnalysisRead(BaseModel):
    """Latest cv_parser agent step recorded for this candidate (per screening run)."""

    screening_run_id: uuid.UUID | None = None
    step_type: str | None = None
    recorded_at: datetime | None = None
    skills_count: int | None = None
    roles_count: int | None = None
    schema_name: str | None = None
    detail: str | None = Field(
        default=None,
        description="Error or diagnostic detail when step_type is error.",
    )


class CandidateJobFitRead(BaseModel):
    """Keyword overlap between this job posting and the CV (computed via shared service / MCP / gRPC)."""

    overall_score: int = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    summary_line: str = ""


class CandidateJobScreeningRead(BaseModel):
    """Latest screening run for the job; text fields may reference multiple candidates in the same run."""

    screening_run_id: uuid.UUID | None = None
    status: str | None = None
    created_at: datetime | None = None
    skill_match: str | None = None
    ranking: str | None = None
    interview: str | None = None


class CandidateDetailRead(BaseModel):
    """Single-candidate record plus CV-derived contact and screening-related metadata."""

    id: uuid.UUID
    job_id: uuid.UUID
    display_name: str
    cv_storage_key: str
    created_at: datetime
    contact: CandidateContactRead
    parse_summary: str | None = Field(
        default=None,
        description="Structured CV notes blob stored with the candidate (structured_summary).",
    )
    structured_profile: dict[str, Any] | None = Field(
        default=None,
        description="Full llamaparse_structured JSON when present.",
    )
    cv_analysis: CandidateCvAnalysisRead
    job_screening: CandidateJobScreeningRead
    job_fit: CandidateJobFitRead | None = Field(
        default=None,
        description="Latest persisted job–CV fit from screening (skill matcher step).",
    )
    cv_parser_agent: CvParserAgentRead | None = Field(
        default=None,
        description="Recruiter LLM brief (alignment, follow-ups, process checks) from cv_parser after parse.",
    )


class CandidateCvPreviewRead(BaseModel):
    """PNG previews plus structured CV and latest screening summaries for the detail UI."""

    pages: list[str] = Field(
        default_factory=list,
        description="Each entry is a data:image/png;base64,... URL.",
    )
    summary_text: str | None = Field(
        default=None,
        description="Structured CV notes when available (e.g. after screening).",
    )
    structured_profile: dict[str, Any] | None = Field(
        default=None,
        description="LlamaParse JSON profile (llamaparse_structured) when present.",
    )
    screening: dict[str, str] | None = Field(
        default=None,
        description="Latest job-level screening snippets: skill_match, ranking, interview.",
    )
