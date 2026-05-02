"""Call MCP streamable-HTTP tools (parse_candidate_cv_structured) from the API process."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)


def _parse_json_dict(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    if not raw.startswith("{"):
        return None
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        return None


def _tool_call_result_to_parse_payload(result: Any) -> dict[str, Any]:
    """Turn MCP ``call_tool`` result into the dict shape ``cv_parser`` expects (``structured`` / ``error``).

    FastMCP may populate ``structuredContent`` with a wrapper that is *not* the tool JSON, or put the
    tool's JSON string only in ``content`` text blocks. We only trust ``structuredContent`` when it
    already looks like the tool contract; otherwise we parse JSON from text.
    """
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        if isinstance(sc.get("structured"), dict):
            return dict(sc)
        if sc.get("error") is not None:
            return dict(sc)
        # Single-value envelope whose value is the full JSON string from ``return json.dumps(...)``.
        if len(sc) == 1:
            v = next(iter(sc.values()))
            if isinstance(v, str):
                parsed = _parse_json_dict(v)
                if parsed and (isinstance(parsed.get("structured"), dict) or parsed.get("error") is not None):
                    return parsed

    texts: list[str] = []
    for block in getattr(result, "content", []) or []:
        if hasattr(block, "text") and block.text:
            texts.append(str(block.text))
    raw = "\n".join(texts).strip()
    parsed = _parse_json_dict(raw) if raw else None
    if parsed and (isinstance(parsed.get("structured"), dict) or parsed.get("error") is not None):
        return parsed

    # Unwrapped CvStructuredProfile-shaped object at top level (no ``structured`` key).
    if isinstance(sc, dict) and not sc.get("error"):
        if isinstance(sc.get("skills"), list) and isinstance(sc.get("work_experience"), list):
            summary = sc.get("structured_summary", "")
            display = sc.get("display_name", sc.get("full_name", ""))
            structured_body = {k: v for k, v in sc.items() if k not in ("structured_summary", "display_name")}
            return {
                "structured": structured_body,
                "structured_summary": summary if isinstance(summary, str) else "",
                "display_name": display if isinstance(display, str) else "",
            }

    if isinstance(parsed, dict) and not parsed.get("error"):
        if isinstance(parsed.get("skills"), list) and isinstance(parsed.get("work_experience"), list):
            summary = parsed.get("structured_summary", "")
            display = parsed.get("display_name", parsed.get("full_name", ""))
            structured_body = {k: v for k, v in parsed.items() if k not in ("structured_summary", "display_name")}
            return {
                "structured": structured_body,
                "structured_summary": summary if isinstance(summary, str) else "",
                "display_name": display if isinstance(display, str) else "",
            }

    if isinstance(sc, dict):
        logger.warning(
            "MCP parse_candidate_cv_structured: structuredContent present but unrecognized shape; keys=%s",
            list(sc.keys())[:24],
        )
        return dict(sc)
    if parsed:
        return parsed
    return {"error": "empty_tool_response"}


def _mcp_connect_failure_hint(base: str, exc: BaseException) -> str | None:
    """If *exc* is (or wraps) httpx.ConnectError, return a short operator hint; else None."""

    def _walk(e: BaseException) -> bool:
        if isinstance(e, httpx.ConnectError):
            return True
        if isinstance(e, BaseExceptionGroup):
            return any(_walk(x) for x in e.exceptions)
        return False

    if not _walk(exc):
        return None
    return (
        f"Cannot reach MCP CV server at {base} (connection refused or host unreachable). "
        "Ensure MCP_CV_AUTO_START is true (default) and ``uv`` is on PATH, or start manually from "
        "recruiter_platform_backend/mcp_server: "
        "uv run fastmcp run app/main.py --transport streamable-http --host 127.0.0.1 --port 8765 "
        "(API must stay up on gRPC; mcp_server/.env needs LLAMA_CLOUD_API_KEY.)"
    )


async def call_parse_candidate_cv_structured(
    mcp_base_url: str,
    *,
    job_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    """
    Invoke MCP tool ``parse_candidate_cv_structured`` and return parsed JSON dict.

    ``mcp_base_url`` must be the streamable-HTTP MCP URL (same as ``fastmcp run --transport streamable-http``),
    e.g. ``http://127.0.0.1:8765/mcp`` (no trailing slash — FastMCP responds with **307** from ``/mcp/`` to ``/mcp``,
    which ``httpx`` + MCP treat as an error unless we normalize).
    """
    base = mcp_base_url.strip().rstrip("/")

    # LlamaCloud polling can exceed default HTTP read timeouts.
    http_timeout = httpx.Timeout(60.0, read=960.0)
    try:
        async with httpx.AsyncClient(timeout=http_timeout) as http_client:
            async with streamable_http_client(base, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "parse_candidate_cv_structured",
                        {"job_id": job_id.strip(), "candidate_id": candidate_id.strip()},
                    )
    except BaseException as exc:
        hint = _mcp_connect_failure_hint(base, exc)
        if hint:
            raise RuntimeError(hint) from exc
        raise

    return _tool_call_result_to_parse_payload(result)
