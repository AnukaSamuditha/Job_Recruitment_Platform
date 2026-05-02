"""Tests for MCP CV tool result normalization."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.mcp_cv_tools_client import _tool_call_result_to_parse_payload

_MIN_PROFILE = {
    "full_name": "Ada",
    "email": "",
    "phone": "",
    "location": "",
    "headline": "",
    "summary": "",
    "skills": ["Python"],
    "work_experience": [],
    "education": [],
    "certifications": [],
    "languages": [],
}


def test_prefers_text_json_when_structuredcontent_is_wrong_envelope() -> None:
    payload = {
        "structured": _MIN_PROFILE,
        "structured_summary": "notes",
        "display_name": "Ada",
    }
    result = SimpleNamespace(
        structuredContent={"_meta": "not-the-tool-payload"},
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )
    out = _tool_call_result_to_parse_payload(result)
    assert out["structured"]["full_name"] == "Ada"
    assert out.get("error") is None


def test_structured_content_contract_shape() -> None:
    payload = {"structured": _MIN_PROFILE, "structured_summary": "s", "display_name": "Ada"}
    result = SimpleNamespace(structuredContent=payload, content=[])
    out = _tool_call_result_to_parse_payload(result)
    assert out == payload


def test_unwrapped_profile_in_structured_content() -> None:
    envelope = {**_MIN_PROFILE, "structured_summary": "sum", "display_name": "Ada"}
    result = SimpleNamespace(structuredContent=envelope, content=[])
    out = _tool_call_result_to_parse_payload(result)
    assert isinstance(out.get("structured"), dict)
    assert out["structured"]["full_name"] == "Ada"
    assert out["structured_summary"] == "sum"
