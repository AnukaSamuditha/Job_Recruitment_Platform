"""MCP tool: load job by id via API gRPC."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from recruitment.v1 import recruitment_pb2, recruitment_pb2_grpc

from grpc_util import get_grpc_channel


def register(app: FastMCP) -> None:
    @app.tool()
    async def db_get_job(job_id: str) -> str:
        """
        Load a job from PostgreSQL via the API gRPC facade.

        Use when the agent needs authoritative job title, company, and description text.
        """
        if not job_id or not job_id.strip():
            return "Error: job_id is required."
        stub = recruitment_pb2_grpc.RecruitmentDataStub(get_grpc_channel())
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
