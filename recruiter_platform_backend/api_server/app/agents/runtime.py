"""Shared helpers for screening agents (DB steps, LLM text coercion)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_step import AgentStep

LLM_EMPTY_REPLY = (
    "(No text returned from the chat model. Check Ollama at OLLAMA_BASE_URL, pull OLLAMA_CHAT_MODEL, "
    "and confirm the service is running.)"
)


def coerce_llm_message_content(content: Any) -> str:
    """Normalize LangChain / provider message payloads to a single string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        return bytes(content).decode("utf-8", errors="replace")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
                else:
                    inner = block.get("content")
                    if isinstance(inner, str):
                        parts.append(inner)
            elif hasattr(block, "text") and isinstance(getattr(block, "text", None), str):
                parts.append(str(block.text))
        return "\n".join(parts)
    return str(content)


async def log_agent_step(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    agent_name: str,
    step_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        AgentStep(
            screening_run_id=run_id,
            agent_name=agent_name,
            step_type=step_type,
            payload=payload,
        )
    )
    await session.flush()
