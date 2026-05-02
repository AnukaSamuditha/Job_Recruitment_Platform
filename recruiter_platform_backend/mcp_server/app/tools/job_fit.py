"""MCP tool: keyword overlap job–CV fit via API gRPC."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from recruitment.v1 import recruitment_pb2, recruitment_pb2_grpc

from grpc_util import get_grpc_channel


def register(app: FastMCP) -> None:
    @app.tool()
    async def compute_candidate_job_fit(job_id: str, candidate_id: str) -> str:
        """
        Compute a 0-100 keyword overlap score between the job posting and this candidate's CV,
        plus matched tokens and likely gaps. Same logic as the API screening skill matcher
        (gRPC ComputeCandidateJobFit).
        """
        jid = (job_id or "").strip()
        cid = (candidate_id or "").strip()
        if not jid or not cid:
            return json.dumps({"error": "job_id and candidate_id are required."})
        stub = recruitment_pb2_grpc.RecruitmentDataStub(get_grpc_channel())
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
