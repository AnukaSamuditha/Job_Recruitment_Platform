from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from collections.abc import AsyncGenerator


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().db_url)


async_session_maker = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise