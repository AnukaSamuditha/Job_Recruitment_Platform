"""MCP tool: list candidates for a job via API gRPC."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from recruitment.v1 import recruitment_pb2, recruitment_pb2_grpc

from grpc_util import get_grpc_channel


def register(app: FastMCP) -> None:
    @app.tool()
    async def db_list_candidates(job_id: str) -> str:
        """
        List candidates (and CV object keys) for a job from PostgreSQL via gRPC.
        """
        if not job_id or not job_id.strip():
            return "Error: job_id is required."
        stub = recruitment_pb2_grpc.RecruitmentDataStub(get_grpc_channel())
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
