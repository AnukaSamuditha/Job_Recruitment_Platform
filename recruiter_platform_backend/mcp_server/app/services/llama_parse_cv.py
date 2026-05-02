"""LlamaCloud parsing HTTP client (same contract as api_server ``llama_parse_cv``)."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import time
from typing import Any

import httpx

from schemas.cv_profile import CvStructuredProfile
from settings import settings

logger = logging.getLogger(__name__)

_JOB_UPLOAD = "/api/parsing/upload"
_JOB_STATUS = "/api/parsing/job/{job_id}"
_JOB_RESULT = "/api/parsing/job/{job_id}/result/{result_type}"


def _form_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return v if isinstance(v, str) else str(v)


def _build_upload_path(organization_id: str | None, project_id: str | None) -> str:
    q: list[str] = []
    if organization_id:
        q.append(f"organization_id={organization_id}")
    if project_id:
        q.append(f"project_id={project_id}")
    if q:
        return f"{_JOB_UPLOAD}?" + "&".join(q)
    return _JOB_UPLOAD


def _structured_payload_from_json_layout(layout: dict[str, Any]) -> dict[str, Any] | None:
    pages = layout.get("pages")
    if not isinstance(pages, list):
        return None
    merged: dict[str, Any] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        sd = page.get("structuredData")
        if not isinstance(sd, dict) or not sd:
            continue
        for k, v in sd.items():
            if isinstance(v, list) and isinstance(merged.get(k), list):
                merged[k] = [*merged[k], *v]
            elif isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            elif k not in merged or merged[k] in (None, "", [], {}):
                merged[k] = v
            else:
                merged[k] = v
    return merged if merged else None


def _text_from_result_payload(result: dict[str, Any], result_key: str) -> str:
    raw = result.get(result_key)
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if x is not None and str(x).strip()]
        return "\n\n".join(parts)
    return str(raw).strip()


async def _poll_until_success(
    client: httpx.AsyncClient,
    job_id: str,
    *,
    check_interval: float,
    max_check_interval: float,
    max_timeout: float,
) -> None:
    start = time.monotonic()
    interval = float(check_interval)
    while True:
        await asyncio.sleep(interval)
        if time.monotonic() - start > max_timeout:
            raise TimeoutError(f"LlamaCloud parse job {job_id} exceeded {max_timeout}s")
        r = await client.get(_JOB_STATUS.format(job_id=job_id))
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        if status == "SUCCESS":
            return
        if status == "PENDING":
            interval = min(interval + 1.0, max_check_interval)
            continue
        err = body.get("error_message") or body.get("error") or body.get("error_code") or status
        raise RuntimeError(f"LlamaCloud parse job {job_id} failed: {err}")


async def _fetch_result_json(
    client: httpx.AsyncClient,
    job_id: str,
    result_type: str,
) -> dict[str, Any]:
    r = await client.get(_JOB_RESULT.format(job_id=job_id, result_type=result_type))
    r.raise_for_status()
    return r.json()


async def _parse_pdf_http(
    *,
    api_key: str,
    pdf_bytes: bytes,
    file_name: str,
    form_fields: dict[str, Any],
    fetch_result_type: str,
    return_json_layout: bool = False,
) -> str | dict[str, Any]:
    base = (settings.llama_cloud_base_url or "").rstrip("/")
    org = (settings.llama_cloud_organization_id or "").strip() or None
    proj = (settings.llama_cloud_project_id or "").strip() or None

    mime = mimetypes.guess_type(file_name)[0] or "application/pdf"
    upload_path = _build_upload_path(org, proj)
    data = {k: _form_value(v) for k, v in form_fields.items()}
    timeout = httpx.Timeout(settings.llama_cloud_parse_timeout_seconds)

    async with httpx.AsyncClient(
        base_url=base,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    ) as client:
        resp = await client.post(
            upload_path,
            files={"file": (file_name, pdf_bytes, mime)},
            data=data,
        )
        resp.raise_for_status()
        job_id = resp.json().get("id")
        if not job_id:
            raise RuntimeError("LlamaCloud upload response missing job id")

        await _poll_until_success(
            client,
            str(job_id),
            check_interval=float(settings.llama_cloud_parse_poll_interval),
            max_check_interval=float(settings.llama_cloud_parse_max_poll_interval),
            max_timeout=float(settings.llama_cloud_parse_timeout_seconds),
        )
        result_json = await _fetch_result_json(client, str(job_id), fetch_result_type)
        if return_json_layout:
            return result_json

        return _text_from_result_payload(result_json, fetch_result_type)


async def llamaparse_pdf_to_structured_profile(
    *,
    api_key: str,
    pdf_bytes: bytes,
    file_name: str,
) -> CvStructuredProfile:
    schema_str = json.dumps(CvStructuredProfile.model_json_schema())
    form: dict[str, Any] = {
        "from_python_package": True,
        "save_images": True,
        "structured_output": True,
        "structured_output_json_schema": schema_str,
        "system_prompt": (
            "You extract recruiting-relevant information from a candidate CV or résumé PDF. "
            "Output must strictly match the provided JSON schema. Use empty strings and empty "
            "arrays when a field is not present. Prefer facts stated in the document over guesses."
        ),
    }
    layout = await _parse_pdf_http(
        api_key=api_key,
        pdf_bytes=pdf_bytes,
        file_name=file_name,
        form_fields=form,
        fetch_result_type="json",
        return_json_layout=True,
    )
    if not isinstance(layout, dict):
        logger.error("LlamaParse expected JSON layout dict, got %s", type(layout).__name__)
        return CvStructuredProfile()
    payload = _structured_payload_from_json_layout(layout)
    if not payload:
        logger.warning("LlamaParse JSON layout had no structuredData for %s", file_name)
        return CvStructuredProfile()

    try:
        return CvStructuredProfile.model_validate(payload)
    except Exception:
        logger.exception("Could not validate LlamaParse structuredData into CvStructuredProfile")
        return CvStructuredProfile()
