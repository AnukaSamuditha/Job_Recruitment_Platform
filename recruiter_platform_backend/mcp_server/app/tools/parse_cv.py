"""MCP tool: fetch CV PDF over gRPC and run LlamaCloud structured parse (LlamaIndex Cloud API)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from recruitment.v1 import recruitment_pb2, recruitment_pb2_grpc

from grpc_util import get_grpc_channel
from services.llama_parse_cv import llamaparse_pdf_to_structured_profile
from settings import settings


def register(app: FastMCP) -> None:
    @app.tool()
    async def parse_candidate_cv_structured(job_id: str, candidate_id: str) -> str:
        """
        Download the candidate's stored CV PDF via the API (gRPC GetCandidateCvPdf) and return
        a JSON object with ``structured`` (CvStructuredProfile fields), ``structured_summary``,
        and ``display_name``. Requires ``LLAMA_CLOUD_API_KEY`` in the MCP server's environment.
        """
        jid = (job_id or "").strip()
        cid = (candidate_id or "").strip()
        if not jid or not cid:
            return json.dumps({"error": "job_id and candidate_id are required."})
        api_key = (settings.llama_cloud_api_key or "").strip()
        if not api_key:
            return json.dumps(
                {"error": "LLAMA_CLOUD_API_KEY is not set on the MCP server (required for parsing)."}
            )

        stub = recruitment_pb2_grpc.RecruitmentDataStub(get_grpc_channel())
        try:
            resp = await stub.GetCandidateCvPdf(
                recruitment_pb2.GetCandidateCvPdfRequest(job_id=jid, candidate_id=cid),
                timeout=90.0,
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": f"gRPC GetCandidateCvPdf failed: {exc!s}"})

        err = (resp.error or "").strip()
        if err:
            return json.dumps({"error": err})

        pdf = bytes(resp.pdf) if resp.pdf else b""
        if not pdf:
            return json.dumps({"error": "empty PDF in response"})

        display = (resp.display_name or "").strip()
        file_name = f"{display or 'cv'}.pdf"
        if not file_name.lower().endswith(".pdf"):
            file_name = f"{file_name}.pdf"

        try:
            profile = await llamaparse_pdf_to_structured_profile(
                api_key=api_key,
                pdf_bytes=pdf,
                file_name=file_name,
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": f"LlamaCloud structured parse failed: {exc!s}"})

        out_display = display or (profile.full_name or "").strip()
        return json.dumps(
            {
                "structured": profile.model_dump(),
                "structured_summary": profile.to_parse_notes(),
                "display_name": out_display,
            },
            default=str,
        )
