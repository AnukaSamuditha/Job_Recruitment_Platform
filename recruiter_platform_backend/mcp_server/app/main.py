"""MCP server: FastMCP transport; gRPC + LlamaCloud only inside tools (see ``tools/``)."""

from __future__ import annotations

import sys
from pathlib import Path

# Local modules (`tools`, `settings`, …) and generated protos (`recruitment.v1`).
_app_dir = Path(__file__).resolve().parent
_gen_root = _app_dir / "gen"
for _p in (_gen_root, _app_dir):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

from mcp.server.fastmcp import FastMCP

from tools import register_tools

app = FastMCP("Recruitment Platform MCP")
register_tools(app)
