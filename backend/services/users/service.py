"""User data-access functions.

Kept separate from backend/api/v1/users.py so the same logic is reusable
from Celery tasks later (spec Phase 8.2 — pipeline code talks to the DB
directly, not through the HTTP API) without importing FastAPI route code.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import Language
from shared.models import NotificationSettings, User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    language: Language,
) -> User:
    user = User(telegram_id=telegram_id, username=username, language=language)
    session.add(user)
    await session.flush()
    # Every user gets default notification settings (07:00/19:00, both
    # enabled) at creation time — spec Phase 1, item 16.
    session.add(NotificationSettings(user_id=user.id))
    await session.flush()
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, user: User, **fields: object) -> User:
    for key, value in fields.items():
        if value is not None:
            setattr(user, key, value)
    await session.flush()
    await session.refresh(user)
    return user
