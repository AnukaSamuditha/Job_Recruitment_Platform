"""Start the MCP CV server alongside the API when configured (loopback MCP URL + auto-start on)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings

logger = logging.getLogger(__name__)


def _repo_mcp_server_dir() -> Path:
    # app/services/mcp_cv_autostart.py -> api_server = parents[2], recruiter_platform_backend = parents[3]
    return Path(__file__).resolve().parents[3] / "mcp_server"


def _loopback_host_port(settings: Settings) -> tuple[str, int] | None:
    raw = str(settings.mcp_cv_tools_url or "").strip()
    if not raw:
        return None
    u = raw if "://" in raw else f"http://{raw}"
    p = urlparse(u)
    host = (p.hostname or "").lower()
    if host in ("localhost", ""):
        host = "127.0.0.1"
    if host not in ("127.0.0.1", "::1"):
        return None
    port = p.port or (443 if p.scheme == "https" else 80)
    if host == "::1":
        return "::1", port
    return "127.0.0.1", port


async def _probe_tcp(host: str, port: int) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.0)
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _wait_tcp(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await _probe_tcp(host, port):
            return True
        await asyncio.sleep(0.25)
    return False


async def ensure_mcp_cv_subprocess(settings: Settings) -> subprocess.Popen | None:
    """If enabled and URL is loopback and port is closed, spawn ``fastmcp`` in ``mcp_server/``."""
    if not settings.mcp_cv_auto_start:
        return None
    loc = _loopback_host_port(settings)
    if loc is None:
        logger.info("MCP auto-start skipped (MCP_CV_TOOLS_URL is not loopback).")
        return None
    host, port = loc
    if await _probe_tcp(host, port):
        logger.info("MCP CV already listening on %s:%s (auto-start skipped).", host, port)
        return None
    uv = shutil.which("uv")
    if not uv:
        logger.warning("`uv` not on PATH; cannot auto-start MCP CV. Start mcp_server manually.")
        return None
    mcp_dir = _repo_mcp_server_dir()
    if not (mcp_dir / "app" / "main.py").exists():
        logger.warning("mcp_server not found at %s; cannot auto-start.", mcp_dir)
        return None
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    cmd = [
        uv,
        "run",
        "fastmcp",
        "run",
        "app/main.py",
        "--transport",
        "streamable-http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(mcp_dir),
        env=os.environ.copy(),
        creationflags=creationflags if os.name == "nt" else 0,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("Started MCP CV subprocess (pid=%s) for 127.0.0.1:%s", proc.pid, port)
    if not await _wait_tcp("127.0.0.1", port, timeout=45.0):
        logger.error("MCP CV subprocess did not open port %s in time (pid=%s).", port, proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        return None
    logger.info("MCP CV streamable HTTP ready (matches MCP_CV_TOOLS_URL port %s).", port)
    return proc


def terminate_mcp_cv_subprocess(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
