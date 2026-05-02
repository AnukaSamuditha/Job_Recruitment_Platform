"""Start/stop async gRPC server for RecruitmentData."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import grpc
from grpc import aio

from app.bootstrap_gen_path import install_gen_path

install_gen_path()

from recruitment.v1 import recruitment_pb2_grpc  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.minio_storage import MinioStorageService

logger = logging.getLogger(__name__)


async def start_grpc_server(
    *,
    session_factory: "async_sessionmaker",
    minio: "MinioStorageService",
    host: str,
    port: int,
) -> aio.Server:
    from app.rpc.recruitment_servicer import build_recruitment_servicer

    server = aio.server()
    recruitment_pb2_grpc.add_RecruitmentDataServicer_to_server(
        build_recruitment_servicer(session_factory, minio=minio), server
    )
    listen = f"{host}:{port}"
    server.add_insecure_port(listen)
    await server.start()
    logger.info("gRPC server listening on %s", listen)
    return server


async def stop_grpc_server(server: aio.Server, grace: float = 5.0) -> None:
    await server.stop(grace)
