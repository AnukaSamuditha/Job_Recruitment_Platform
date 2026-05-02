"""CV Parser agent: LlamaParse structured profile + DB updates."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.deps import ScreeningGraphDeps
from app.agents.runtime import log_agent_step
from app.agents.state import ScreeningState
from app.core.config import get_settings
from app.models.candidate import Candidate
from app.schemas.cv_profile import CvStructuredProfile
from app.services.llama_parse_cv import llamaparse_pdf_to_structured_profile

logger = logging.getLogger(__name__)


def create_cv_parser_node(deps: ScreeningGraphDeps):
    async def cv_parser(state: ScreeningState) -> dict[str, Any]:
        run_id = uuid.UUID(state["screening_run_id"])
        await deps.broadcaster.publish(
            str(run_id), {"type": "parsing", "detail": "CV Parser agent (LlamaParse + schema)"}
        )
        api_key = (get_settings().llama_cloud_api_key or "").strip()
        notes: list[str] = []
        queued_ids = list(state.get("candidate_ids") or [])

        async with deps.session_factory() as session:
            await log_agent_step(
                session,
                run_id=run_id,
                agent_name="cv_parser",
                step_type="start",
                payload={"candidate_ids": queued_ids, "engine": "llamaparse"},
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
                    payload={"detail": "empty_candidate_ids"},
                )
                await session.commit()
            for cid in queued_ids:
                cand = await session.get(Candidate, uuid.UUID(cid))
                if cand is None:
                    continue
                if not api_key:
                    msg = f"{cand.display_name}: LLAMA_CLOUD_API_KEY missing; skipped structured LlamaParse."
                    notes.append(msg)
                    logger.warning(msg)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={"candidate_id": cid, "detail": "missing_llama_cloud_api_key"},
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg},
                    )
                    continue

                try:
                    pdf_bytes = await asyncio.to_thread(
                        deps.minio.get_object_bytes, cand.cv_storage_key
                    )
                except Exception as exc:
                    msg = f"{cand.display_name}: could not load CV from object storage ({exc})."
                    notes.append(msg)
                    logger.exception("MinIO read failed for candidate %s", cid)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={"candidate_id": cid, "detail": str(exc)},
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                file_name = f"{(cand.display_name or 'cv').strip() or 'cv'}.pdf"
                try:
                    profile = await llamaparse_pdf_to_structured_profile(
                        api_key=api_key,
                        pdf_bytes=pdf_bytes,
                        file_name=file_name,
                    )
                except Exception as exc:
                    msg = f"{cand.display_name}: LlamaParse structured extraction failed ({exc})."
                    notes.append(msg)
                    logger.exception("LlamaParse structured failed for %s", cid)
                    await log_agent_step(
                        session,
                        run_id=run_id,
                        agent_name="cv_parser",
                        step_type="error",
                        payload={"candidate_id": cid, "detail": str(exc)},
                    )
                    await deps.broadcaster.publish(
                        str(run_id),
                        {"type": "parse_issue", "detail": msg[:500]},
                    )
                    continue

                merged: dict[str, Any] = dict(cand.parse_result) if cand.parse_result else {}
                merged["llamaparse_structured"] = profile.model_dump()
                merged["structured_summary"] = profile.to_parse_notes()
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
                    },
                )

            await session.commit()

        text = "\n\n".join(notes) if notes else "No structured CV data extracted."
        return {
            "parse_notes": text,
            "messages": [AIMessage(content=f"[cv_parser] {text[:12000]}")],
        }

    return cv_parser
