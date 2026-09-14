"""Small helpers shared across backend/api/v1/*.py route modules —
kept separate from backend/services/users/service.py since raising an
HTTPException is an API-layer (not service-layer) concern.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.users import service as users_service
from shared.models import User


async def get_user_or_404(session: AsyncSession, telegram_id: int) -> User:
    user = await users_service.get_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
