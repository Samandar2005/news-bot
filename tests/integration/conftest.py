"""httpx AsyncClient fixture for API integration tests.

Uses ASGITransport to call the FastAPI app in-process (no real network,
no running uvicorn needed) but exercises the real app, real routing, real
dependency injection, and the real (isolated) test database — this is an
actual integration test, not a mocked one.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.db.session import get_session
from backend.main import app
from shared.config import settings
from shared.models import InterestCategory


@pytest_asyncio.fixture
async def client(session) -> AsyncGenerator[AsyncClient, None]:
    # Override the app's DB dependency to use the same rolled-back-per-test
    # session as everything else in the suite, instead of opening a second,
    # uncontrolled connection to the dev database.
    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "X-Internal-Token": settings.internal_api_token,
            "X-Admin-Token": settings.admin_api_token,
        },
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_categories(session) -> list[InterestCategory]:
    """A handful of categories owned entirely by the test transaction.

    Deliberately *not* the real 14 seeded categories — permanently seeding
    those into the test database would reintroduce exactly the key-collision
    problem the dev/test database split was meant to fix (see
    shared/models tests and tests/conftest.py). Business-content assertions
    ("there are 14 categories", "python is one of them") belong on the seed
    script itself, not on the interests endpoint's behavior.
    """
    cats = [
        InterestCategory(key="test_tech", name_en="Tech", name_ru="Техно", name_uz="Texno"),
        InterestCategory(key="test_ai", name_en="AI", name_ru="ИИ", name_uz="SI"),
        InterestCategory(
            key="test_science", name_en="Science", name_ru="Наука", name_uz="Fan"
        ),
        InterestCategory(key="test_space", name_en="Space", name_ru="Космос", name_uz="Kosmos"),
    ]
    session.add_all(cats)
    await session.flush()
    for c in cats:
        await session.refresh(c)
    return cats
