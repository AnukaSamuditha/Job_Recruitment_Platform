"""Dependencies injected into screening agent node factories."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_ollama import ChatOllama
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.minio_storage import MinioStorageService
from app.ws.broadcast import ScreeningBroadcaster


@dataclass(frozen=True)
class ScreeningGraphDeps:
    session_factory: async_sessionmaker
    broadcaster: ScreeningBroadcaster
    minio: MinioStorageService
    llm: ChatOllama
