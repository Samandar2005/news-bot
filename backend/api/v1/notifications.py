"""GET/PATCH /api/v1/users/{telegram_id}/notifications (spec Phase 8.2).

Bot-facing (internal token), same as users/interests — every user gets a
NotificationSettings row at creation time (backend/services/users/service.py),
so a missing row here indicates a real bug, not a normal 404 case.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.common import get_user_or_404
from backend.core.security import require_internal_token
from backend.db.session import get_session
from backend.schemas.notification import NotificationSettingsRead, NotificationSettingsUpdate
from backend.services.notifications import service as notifications_service

router = APIRouter(tags=["notifications"], dependencies=[Depends(require_internal_token)])


@router.get("/users/{telegram_id}/notifications", response_model=NotificationSettingsRead)
async def get_notification_settings(
    telegram_id: int, session: AsyncSession = Depends(get_session)
) -> NotificationSettingsRead:
    user = await get_user_or_404(session, telegram_id)
    settings = await notifications_service.get_settings(session, user.id)
    if settings is None:
        # Should never happen — every user gets one at creation time.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no notification_settings row",
        )
    return NotificationSettingsRead.model_validate(settings)


@router.patch("/users/{telegram_id}/notifications", response_model=NotificationSettingsRead)
async def update_notification_settings(
    telegram_id: int,
    payload: NotificationSettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> NotificationSettingsRead:
    user = await get_user_or_404(session, telegram_id)
    settings = await notifications_service.get_settings(session, user.id)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no notification_settings row",
        )
    updated = await notifications_service.update_settings(
        session, settings, **payload.model_dump()
    )
    await session.commit()
    return NotificationSettingsRead.model_validate(updated)
