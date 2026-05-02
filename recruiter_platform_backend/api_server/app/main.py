from __future__ import annotations

import logging
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap_gen_path import install_gen_path

install_gen_path()

from app.api.routes import candidates as candidates_routes
from app.api.routes import jobs as jobs_routes
from app.api.routes import screening as screening_routes
from app.api.routes import ws as ws_routes
from app.core.config import get_settings
from app.core.database import async_session_maker
from app.graph.screening_graph import build_screening_graph
from app.rpc.serve import start_grpc_server, stop_grpc_server
from app.services.embedding_service import EmbeddingService
from app.services.minio_storage import MinioStorageService
from app.ws.broadcast import ScreeningBroadcaster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    storage = MinioStorageService(settings)
    try:
        storage.ensure_bucket()
    except Exception:
        logger.warning("MinIO bucket check failed — uploads may fail until MinIO is up.")

    broadcaster = ScreeningBroadcaster()
    embed = EmbeddingService(settings)
    graph = build_screening_graph(async_session_maker, broadcaster, storage)

    app.state.minio = storage
    app.state.broadcaster = broadcaster
    app.state.embedding_service = embed
    app.state.screening_graph = graph

    grpc_server = await start_grpc_server(
        session_factory=async_session_maker,
        host=settings.grpc_bind_host,
        port=settings.grpc_port,
    )
    app.state.grpc_server = grpc_server
    logger.info("REST on port %s, gRPC on %s", settings.port, settings.grpc_port)
    yield
    await stop_grpc_server(grpc_server)


app = FastAPI(title="Recruitment Platform API", lifespan=lifespan)

_cors = get_settings()
_cors_kw: dict[str, Any] = {
    "allow_origins": _cors.cors_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if _cors.cors_allow_origin_regex:
    _cors_kw["allow_origin_regex"] = _cors.cors_allow_origin_regex

app.add_middleware(CORSMiddleware, **_cors_kw)

app.include_router(jobs_routes.router, prefix="/api/v1")
app.include_router(candidates_routes.router, prefix="/api/v1")
app.include_router(screening_routes.router, prefix="/api/v1")
app.include_router(ws_routes.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Recruitment API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
