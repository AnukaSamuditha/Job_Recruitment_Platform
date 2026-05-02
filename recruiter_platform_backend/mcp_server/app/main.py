"""MCP server: standard FastMCP transport; gRPC only inside DB-backed tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Generated protos import as `recruitment.v1`
_gen_root = Path(__file__).resolve().parent / "gen"
if str(_gen_root) not in sys.path:
    sys.path.insert(0, str(_gen_root))

from grpc import aio
from mcp.server.fastmcp import FastMCP
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from recruitment.v1 import recruitment_pb2, recruitment_pb2_grpc


class Settings(BaseSettings):
    """Configure gRPC target for the API database facade (see `.env`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_grpc_host: str = Field(default="127.0.0.1", description="API gRPC host.")
    api_grpc_port: int = Field(default=50051, description="API gRPC port (same as api_server GRPC_PORT).")
    api_grpc_target: str | None = Field(
        default=None,
        description="Optional full host:port; if unset, built from api_grpc_host:api_grpc_port.",
    )

    @model_validator(mode="after")
    def compose_api_grpc_target(self) -> Settings:
        raw = (self.api_grpc_target or "").strip()
        if raw:
            self.api_grpc_target = raw
        else:
            self.api_grpc_target = f"{self.api_grpc_host}:{self.api_grpc_port}"
        return self


settings = Settings()
app = FastMCP("Recruitment Platform MCP")

_channel: aio.Channel | None = None


def _channel_singleton() -> aio.Channel:
    global _channel
    if _channel is None:
        _channel = aio.insecure_channel(settings.api_grpc_target)
    return _channel


@app.tool()
async def db_get_job(job_id: str) -> str:
    """
    Load a job from PostgreSQL via the API gRPC facade.

    Use when the agent needs authoritative job title, company, and description text.
    """
    if not job_id or not job_id.strip():
        return "Error: job_id is required."
    stub = recruitment_pb2_grpc.RecruitmentDataStub(_channel_singleton())
    try:
        resp = await stub.GetJob(
            recruitment_pb2.GetJobRequest(job_id=job_id.strip()),
            timeout=15.0,
        )
    except Exception as exc:  # noqa: BLE001 — surface to MCP client
        return f"gRPC error: {exc!s}"
    if not resp.job.id:
        return "Job not found."
    j = resp.job
    return (
        f"id={j.id}\n"
        f"title={j.title}\ncompany={j.company}\n"
        f"has_embedding={j.has_embedding}\n\n"
        f"{j.description_plain}"
    )


@app.tool()
async def db_list_candidates(job_id: str) -> str:
    """
    List candidates (and CV object keys) for a job from PostgreSQL via gRPC.
    """
    if not job_id or not job_id.strip():
        return "Error: job_id is required."
    stub = recruitment_pb2_grpc.RecruitmentDataStub(_channel_singleton())
    try:
        resp = await stub.ListCandidates(
            recruitment_pb2.ListCandidatesRequest(job_id=job_id.strip()),
            timeout=15.0,
        )
    except Exception as exc:  # noqa: BLE001
        return f"gRPC error: {exc!s}"
    if not resp.candidates:
        return "(no candidates for this job)"
    lines = [
        f"- {c.id} | {c.display_name} | key={c.cv_storage_key}"
        for c in resp.candidates
    ]
    return "\n".join(lines)


@app.tool()
async def compute_candidate_job_fit(job_id: str, candidate_id: str) -> str:
    """
    Compute a 0–100 keyword overlap score between the job posting and this candidate's CV,
    plus matched tokens and likely gaps. Same logic as the API screening skill matcher
    (gRPC ComputeCandidateJobFit).
    """
    jid = (job_id or "").strip()
    cid = (candidate_id or "").strip()
    if not jid or not cid:
        return json.dumps({"error": "job_id and candidate_id are required."})
    stub = recruitment_pb2_grpc.RecruitmentDataStub(_channel_singleton())
    try:
        resp = await stub.ComputeCandidateJobFit(
            recruitment_pb2.ComputeCandidateJobFitRequest(job_id=jid, candidate_id=cid),
            timeout=30.0,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})
    return json.dumps(
        {
            "overall_score": int(resp.overall_score),
            "matched_skills": list(resp.matched_skills),
            "missing_skills": list(resp.missing_skills),
            "summary_line": resp.summary_line,
        },
        indent=2,
    )
