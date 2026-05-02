from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


def get_broadcaster(request: Request):
    return request.app.state.broadcaster


def get_embedding_service(request: Request):
    return request.app.state.embedding_service


def get_minio(request: Request):
    return request.app.state.minio


def get_screening_graph(request: Request):
    return request.app.state.screening_graph
