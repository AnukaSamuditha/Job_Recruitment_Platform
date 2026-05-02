"""CV Parser agent: MCP tool ``parse_candidate_cv_structured`` + recruiter brief LLM + DB updates."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.deps import ScreeningGraphDeps
from app.agents.runtime import log_agent_step
from app.agents.state import ScreeningState
from app.agents.tracing import make_trace
from app.core.config import get_settings
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.cv_profile import CvStructuredProfile
from app.schemas.cv_parser_agent import CV_PARSER_AGENT_DISCLAIMER, CvParserAgentRead
from app.services.cv_parser_agent_llm import run_cv_parser_recruiter_brief
from app.services.mcp_cv_tools_client import call_parse_candidate_cv_structured

logger = logging.getLogger(__name__)


def create_cv_parser_node(deps: ScreeningGraphDeps):
    async def cv_parser(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        settings = get_settings()
        mcp_cv_url = str(settings.mcp_cv_tools_url or "").strip()
        engine = "mcp_parse_candidate_cv_structured"
        await deps.broadcaster.publish(
            str(run_id), {"type": "parsing", "detail": f"CV Parser agent ({engine})"}
        )
        notes: list[str] = []
        queued_ids = list(state.get("candidate_ids") or [])
        job_id_str = (state.get("job_id") or "").strip()

        async with deps.session_factory() as session:
            await log_agent_step(
                session,
                run_id=run_id,
                agent_name="cv_parser",
                step_type="start",
                payload={
                    "candidate_ids": queued_ids,
                    "engine": engine,
                    "trace": make_trace(
                        inputs={
                            "job_id": job_id_str,
                            "candidate_ids": queued_ids,
                            "engine": engine,
                            "mcp_cv_tools_url": mcp_cv_url[:120],
                        },
                        tool_calls=[],
                        outputs={"phase": "cv_parser_start"},
                    ),
                },
            )
            await session.commit()

        async with deps.session_factory() as session:
            if not queued_ids:
                warn = (
                    "cv_parser: candidate_ids was empty — no per-candidate structured parse was performed. "
                    "Screening runs should include at least one candidate id."
                )
                notes.append(warn)
                logger.warning(warn)
                await log_agent_step(
                    session,
                    run_id=run_id,
                    agent_name="cv_parser",
                    step_type="skipped",
                    payload={
                        "detail": "empty_candidate_ids",
                        "trace": make_trace(
                            inputs={"job_id": job_id_str, "engine": engine},
                            tool_calls=[],
                            outputs={"reason": "empty_candidate_ids"},
                        ),
                    },
                )
                await session.commit()
            for cid in queued_ids:
                cand = await session.get(Candidate, uuid.UUID(cid))
                if cand is None:
                    continue
                data: dict[str, Any] | None = None
                if not job_id_str:
                    msg = f"{cand.display_name}: screening state missing job_id; cannot call MCP CV parse."
                    notes.append(msg)
                    logger.warning(msg)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={
                            "candidate_id": cid,
                            "detail": "missing_job_id_for_mcp",
                            "trace": make_trace(
                                inputs={"candidate_id": cid, "engine": engine},
                                tool_calls=[],
                                outputs={"ok": False, "detail": "missing_job_id_for_mcp"},
                            ),
                        },
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg},
                    )
                    continue
                try:
                    data = await call_parse_candidate_cv_structured(
                        mcp_cv_url,
                        job_id=job_id_str,
                        candidate_id=cid,
                    )
                except Exception as exc:
                    msg = f"{cand.display_name}: MCP parse_candidate_cv_structured failed ({exc})."
                    notes.append(msg)
                    logger.exception("MCP CV parse failed for %s", cid)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={
                            "candidate_id": cid,
                            "detail": str(exc),
                            "trace": make_trace(
                                inputs={"job_id": job_id_str, "candidate_id": cid, "engine": engine},
                                tool_calls=[
                                    {
                                        "name": "parse_candidate_cv_structured",
                                        "type": "mcp_tool",
                                        "input": {"job_id": job_id_str, "candidate_id": cid},
                                        "output": {"ok": False, "error": str(exc)[:800]},
                                    }
                                ],
                                outputs={"ok": False},
                            ),
                        },
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                err = data.get("error") if isinstance(data, dict) else None
                if err:
                    msg = f"{cand.display_name}: MCP CV parse error ({err})."
                    notes.append(msg)
                    logger.warning(msg)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={
                            "candidate_id": cid,
                            "detail": str(err)[:2000],
                            "trace": make_trace(
                                inputs={"job_id": job_id_str, "candidate_id": cid, "engine": engine},
                                tool_calls=[
                                    {
                                        "name": "parse_candidate_cv_structured",
                                        "type": "mcp_tool",
                                        "input": {"job_id": job_id_str, "candidate_id": cid},
                                        "output": {"ok": False, "error": str(err)[:800]},
                                    }
                                ],
                                outputs={"ok": False},
                            ),
                        },
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                structured = data.get("structured") if isinstance(data, dict) else None
                if isinstance(structured, str):
                    try:
                        structured = json.loads(structured)
                    except json.JSONDecodeError:
                        structured = None
                if not isinstance(structured, dict):
                    msg = f"{cand.display_name}: MCP response missing structured profile."
                    notes.append(msg)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={
                            "candidate_id": cid,
                            "detail": "missing_structured",
                            "trace": make_trace(
                                inputs={"job_id": job_id_str, "candidate_id": cid, "engine": engine},
                                tool_calls=[
                                    {
                                        "name": "parse_candidate_cv_structured",
                                        "type": "mcp_tool",
                                        "input": {"job_id": job_id_str, "candidate_id": cid},
                                        "output": {"ok": False, "error": "missing_structured"},
                                    }
                                ],
                                outputs={"ok": False},
                            ),
                        },
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                try:
                    profile = CvStructuredProfile.model_validate(structured)
                except Exception as exc:
                    msg = f"{cand.display_name}: could not validate MCP structured payload ({exc})."
                    notes.append(msg)
                    logger.exception("MCP structured validate failed for %s", cid)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={
                            "candidate_id": cid,
                            "detail": str(exc),
                            "trace": make_trace(
                                inputs={"job_id": job_id_str, "candidate_id": cid, "engine": engine},
                                tool_calls=[
                                    {
                                        "name": "parse_candidate_cv_structured",
                                        "type": "mcp_tool",
                                        "input": {"job_id": job_id_str, "candidate_id": cid},
                                        "output": {"ok": True},
                                    },
                                    {
                                        "name": "CvStructuredProfile.model_validate",
                                        "type": "schema",
                                        "input": {"structured_keys": list(structured.keys())[:24]},
                                        "output": {"ok": False, "error": str(exc)[:800]},
                                    },
                                ],
                                outputs={"ok": False},
                            ),
                        },
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                parse_tool_calls: list[dict[str, Any]] = [
                    {
                        "name": "parse_candidate_cv_structured",
                        "type": "mcp_tool",
                        "input": {"job_id": job_id_str, "candidate_id": cid},
                        "output": {
                            "ok": True,
                            "response_keys": list(data.keys())[:24] if isinstance(data, dict) else [],
                        },
                    }
                ]

                merged: dict[str, Any] = dict(cand.parse_result) if cand.parse_result else {}
                merged["llamaparse_structured"] = profile.model_dump()
                merged["structured_summary"] = profile.to_parse_notes()

                jid_key = (job_id_str or str(cand.job_id)).strip()
                job_row: Job | None = None
                if jid_key:
                    try:
                        job_row = await session.get(Job, uuid.UUID(jid_key))
                    except ValueError:
                        job_row = None

                try:
                    agent_read = await run_cv_parser_recruiter_brief(
                        deps.llm,
                        profile=profile,
                        job_title=job_row.title if job_row else "",
                        job_company=job_row.company if job_row else "",
                        job_description_plain=job_row.description_plain if job_row else "",
                    )
                    merged["cv_parser_agent"] = agent_read.model_dump()
                except Exception as exc:  # noqa: BLE001 — keep screening usable without Ollama
                    logger.exception("cv_parser recruiter LLM failed for candidate %s", cid)
                    merged["cv_parser_agent"] = CvParserAgentRead(
                        alignment_summary=[],
                        gaps_or_questions=[],
                        risk_flags=[],
                        disclaimer=CV_PARSER_AGENT_DISCLAIMER,
                        error=str(exc)[:2000],
                    ).model_dump()

                cand.parse_result = merged
                extracted_name = (profile.full_name or "").strip()
                if extracted_name:
                    cand.display_name = extracted_name[:512]
                await session.flush()

                summary = profile.to_parse_notes()
                notes.append(f"## {cand.display_name}\n{summary}")

                await log_agent_step(
                    session,
                    run_id=run_id,
                    agent_name="cv_parser",
                    step_type="llamaparse_structured",
                    payload={
                        "candidate_id": cid,
                        "full_name": profile.full_name,
                        "skills_count": len(profile.skills),
                        "roles_count": len(profile.work_experience),
                        "schema": CvStructuredProfile.__name__,
                        "via_mcp": True,
                        "trace": make_trace(
                            inputs={
                                "job_id": jid_key,
                                "candidate_id": cid,
                                "engine": engine,
                                "display_name": cand.display_name,
                            },
                            tool_calls=parse_tool_calls,
                            outputs={
                                "ok": True,
                                "skills_count": len(profile.skills),
                                "roles_count": len(profile.work_experience),
                                "structured_summary_chars": len(profile.to_parse_notes()),
                            },
                        ),
                    },
                )
                agent_err = (
                    merged.get("cv_parser_agent", {}).get("error")
                    if isinstance(merged.get("cv_parser_agent"), dict)
                    else None
                )
                await log_agent_step(
                    session,
                    run_id=run_id,
                    agent_name="cv_parser",
                    step_type="cv_parser_llm_brief",
                    payload={
                        "candidate_id": cid,
                        "alignment_count": len(merged.get("cv_parser_agent", {}).get("alignment_summary") or []),
                        "gaps_count": len(merged.get("cv_parser_agent", {}).get("gaps_or_questions") or []),
                        "risks_count": len(merged.get("cv_parser_agent", {}).get("risk_flags") or []),
                        "llm_error": bool(agent_err),
                        "trace": make_trace(
                            inputs={
                                "candidate_id": cid,
                                "job_title_present": bool(job_row and (job_row.title or "").strip()),
                                "job_description_chars": len(job_row.description_plain)
                                if job_row
                                else 0,
                            },
                            tool_calls=[
                                {
                                    "name": "ChatOllama.with_structured_output",
                                    "type": "llm",
                                    "task": "cv_parser_recruiter_brief",
                                    "input": {"schema": "CvParserAgentLlmCore"},
                                    "output": {"ok": not bool(agent_err)},
                                }
                            ],
                            outputs={
                                "alignment_count": len(
                                    merged.get("cv_parser_agent", {}).get("alignment_summary") or []
                                ),
                                "gaps_count": len(merged.get("cv_parser_agent", {}).get("gaps_or_questions") or []),
                                "risks_count": len(merged.get("cv_parser_agent", {}).get("risk_flags") or []),
                                "llm_error": bool(agent_err),
                            },
                        ),
                    },
                )

            await session.commit()

        text = "\n\n".join(notes) if notes else "No structured CV data extracted."
        return {
            "parse_notes": text,
            "messages": [AIMessage(content=f"[cv_parser] {text[:12000]}")],
        }

    return cv_parser
