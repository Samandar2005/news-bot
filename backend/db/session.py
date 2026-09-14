"""Async SQLAlchemy engine/session factory.

One engine per process (backend API, or a Celery worker's event loop),
created lazily so importing this module never opens a connection by itself.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session, closes it after the request."""
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside FastAPI (Celery tasks, scripts).

    Commits on success, rolls back on exception:

        async with session_scope() as session:
            session.add(obj)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
