"""GET /api/v1/interests/categories and
GET/PUT /api/v1/users/{telegram_id}/interests — see spec Phase 8.2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.common import get_user_or_404
from backend.core.security import require_internal_token
from backend.db.session import get_session
from backend.schemas.interest import CategoryRead, UserInterestsRead, UserInterestsSet
from backend.services.interests import service as interests_service
from backend.services.interests.service import InvalidCategoryIds

router = APIRouter(tags=["interests"], dependencies=[Depends(require_internal_token)])


@router.get("/interests/categories", response_model=list[CategoryRead])
async def get_categories(session: AsyncSession = Depends(get_session)) -> list[CategoryRead]:
    categories = await interests_service.list_categories(session)
    return [CategoryRead.model_validate(c) for c in categories]


@router.get("/users/{telegram_id}/interests", response_model=UserInterestsRead)
async def get_user_interests(
    telegram_id: int, session: AsyncSession = Depends(get_session)
) -> UserInterestsRead:
    user = await get_user_or_404(session, telegram_id)
    categories = await interests_service.get_user_categories(session, user.id)
    return UserInterestsRead(categories=[CategoryRead.model_validate(c) for c in categories])


@router.put("/users/{telegram_id}/interests", response_model=UserInterestsRead)
async def set_user_interests(
    telegram_id: int, payload: UserInterestsSet, session: AsyncSession = Depends(get_session)
) -> UserInterestsRead:
    user = await get_user_or_404(session, telegram_id)
    try:
        categories = await interests_service.set_user_categories(
            session, user.id, payload.category_ids
        )
    except InvalidCategoryIds as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await session.commit()
    return UserInterestsRead(categories=[CategoryRead.model_validate(c) for c in categories])
