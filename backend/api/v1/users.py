"""POST/GET/PATCH /api/v1/users — see spec Phase 8.2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import require_internal_token
from backend.db.session import get_session
from backend.schemas.user import UserCreate, UserRead, UserUpdate
from backend.services.users import service as users_service

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(require_internal_token)]
)


@router.post("", response_model=UserRead)
async def upsert_user(
    payload: UserCreate, session: AsyncSession = Depends(get_session)
) -> UserRead:
    """Create the user if they don't exist yet, otherwise return them as-is.

    Called on every `/start` — idempotent by design so the bot doesn't need
    to know in advance whether this is a returning user.
    """
    existing = await users_service.get_by_telegram_id(session, payload.telegram_id)
    if existing is not None:
        return UserRead.model_validate(existing)

    user = await users_service.create_user(
        session, payload.telegram_id, payload.username, payload.language
    )
    await session.commit()
    return UserRead.model_validate(user)


@router.get("/{telegram_id}", response_model=UserRead)
async def get_user(telegram_id: int, session: AsyncSession = Depends(get_session)) -> UserRead:
    user = await users_service.get_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserRead.model_validate(user)


@router.patch("/{telegram_id}", response_model=UserRead)
async def update_user(
    telegram_id: int, payload: UserUpdate, session: AsyncSession = Depends(get_session)
) -> UserRead:
    user = await users_service.get_by_telegram_id(session, telegram_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user = await users_service.update_user(session, user, **payload.model_dump())
    await session.commit()
    return UserRead.model_validate(user)
