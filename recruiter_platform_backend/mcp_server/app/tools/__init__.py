"""Register all MCP tools on a ``FastMCP`` app instance."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .db_candidates import register as _register_db_candidates
from .db_job import register as _register_db_job
from .job_fit import register as _register_job_fit
from .parse_cv import register as _register_parse_cv


def register_tools(app: FastMCP) -> None:
    _register_db_job(app)
    _register_db_candidates(app)
    _register_job_fit(app)
    _register_parse_cv(app)
