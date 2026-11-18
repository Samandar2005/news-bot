"""Shared pytest fixtures.

Tests run against a real Postgres+pgvector database (not sqlite / mocks) —
several of our constraints (CHECK, unique, vector columns) don't behave the
same on a fake backend, so this catches real schema bugs. Deliberately a
*separate* database from the dev one (`newsbot_test`, not `newsbot`) so
tests never collide with real seed data (e.g. predefined category keys).
Each test runs inside a transaction that's rolled back afterward, so tests
never leak state into each other either.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/newsbot_test",
)


@pytest_asyncio.fixture
async def engine():
    # Function-scoped (not session-scoped) on purpose: pytest-asyncio gives
    # each test its own event loop, and an asyncpg engine created against
    # one loop breaks on the next — see
    # https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops
    eng = create_async_engine(TEST_DATABASE_URL)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    async_session = session_factory()

    try:
        yield async_session
    finally:
        await async_session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
