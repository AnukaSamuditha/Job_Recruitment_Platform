"""Agent execution tracing: structured inputs, tool calls, and outputs (DB + JSON logs).

Assignment-style audit trail: each ``log_agent_step`` payload may include a ``trace`` object
``{version, inputs, tool_calls, outputs}`` persisted in ``agent_steps.payload`` (JSONB) and
mirrored to the ``app.agents.trace`` logger at INFO for log aggregation. When
``configure_trace_file_logging`` runs from ``app.main``, each line is one JSON object under
``logs/agent_traces.log`` (rotating).
"""

from __future__ import annotations

import json
import logging
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

TRACE_VERSION = 1
TRACE_LOGGER_NAME = "app.agents.trace"
_MAX_TRACE_STRING = 12_000
_MAX_JSON_LOG = 48_000

trace_logger = logging.getLogger(TRACE_LOGGER_NAME)

_TRACE_FILE_HANDLER_ATTR = "_recruiter_trace_json_file"


def configure_trace_file_logging(
    *,
    log_dir: Path,
    enabled: bool = True,
    filename: str = "agent_traces.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> Path | None:
    """Append one JSON object per line to ``log_dir / filename`` (message only, no log prefix).

    Idempotent: safe to call multiple times (e.g. Uvicorn reload).
    """
    if not enabled:
        return None
    if any(getattr(h, _TRACE_FILE_HANDLER_ATTR, False) for h in trace_logger.handlers):
        return log_dir / filename

    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / filename
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=False,
    )
    setattr(handler, _TRACE_FILE_HANDLER_ATTR, True)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.INFO)
    trace_logger.setLevel(logging.INFO)
    trace_logger.addHandler(handler)
    return path


def clip_text(value: Any, max_chars: int = _MAX_TRACE_STRING) -> Any:
    """Shorten long strings for traces and logs; pass through scalars and small structures."""
    if value is None:
        return None
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + f"\n…({len(value) - max_chars} more chars)"
    if isinstance(value, dict):
        return {str(k): clip_text(v, max_chars=max(256, max_chars // max(len(value), 1))) for k, v in value.items()}
    if isinstance(value, list):
        cap = 40
        clipped = [clip_text(x, max_chars=2048) for x in value[:cap]]
        if len(value) > cap:
            clipped.append(f"…({len(value) - cap} more items)")
        return clipped
    return value


def make_trace(
    *,
    inputs: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    outputs: dict[str, Any],
) -> dict[str, Any]:
    """Build a versioned trace dict suitable for ``AgentStep.payload['trace']``."""
    return {
        "version": TRACE_VERSION,
        "inputs": clip_text(inputs),
        "tool_calls": clip_text(tool_calls),
        "outputs": clip_text(outputs),
    }


def emit_screening_trace(
    *,
    screening_run_id: uuid.UUID,
    agent_name: str,
    step_type: str,
    payload: dict[str, Any],
) -> None:
    """Write one JSON line to the trace logger when payload includes a ``trace`` key."""
    trace = payload.get("trace")
    if not isinstance(trace, dict):
        return
    record = {
        "kind": "agent_step_trace",
        "screening_run_id": str(screening_run_id),
        "agent_name": agent_name,
        "step_type": step_type,
        "trace": trace,
        "payload_excerpt": {
            k: clip_text(v, max_chars=400)
            for k, v in payload.items()
            if k != "trace" and k != "summary"
        },
    }
    if isinstance(payload.get("summary"), str):
        record["summary_excerpt"] = clip_text(payload["summary"], max_chars=1500)
    line = json.dumps(record, default=str)
    if len(line) > _MAX_JSON_LOG:
        line = line[:_MAX_JSON_LOG] + "…(truncated)"
    trace_logger.info("%s", line)


def emit_screening_run_event(
    *,
    event: str,
    screening_run_id: uuid.UUID,
    job_id: uuid.UUID,
    candidate_ids: list[str],
    detail: str | None = None,
) -> None:
    """Graph-level correlation (start / failure) for log pipelines."""
    trace_logger.info(
        "%s",
        json.dumps(
            {
                "kind": "screening_run",
                "event": event,
                "screening_run_id": str(screening_run_id),
                "job_id": str(job_id),
                "candidate_count": len(candidate_ids),
                "candidate_ids": candidate_ids[:24],
                "detail": detail,
            },
            default=str,
        ),
    )
