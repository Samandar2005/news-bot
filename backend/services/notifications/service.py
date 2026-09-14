"""Notification settings data-access functions (spec Phase 8.2)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import NotificationSettings


async def get_settings(session: AsyncSession, user_id: int) -> NotificationSettings | None:
    result = await session.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_settings(
    session: AsyncSession, settings: NotificationSettings, **fields: object
) -> NotificationSettings:
    for key, value in fields.items():
        if value is not None:
            setattr(settings, key, value)
    await session.flush()
    await session.refresh(settings)
    return settings
