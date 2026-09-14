"""GET /api/v1/users/{telegram_id}/digest/preview (spec Phase 8.2) — the
/news on-demand command's backing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.common import get_user_or_404
from backend.core.security import require_internal_token
from backend.db.session import get_session
from backend.schemas.digest import DigestPreviewRead
from backend.services.digest import service as digest_service

router = APIRouter(tags=["digest"], dependencies=[Depends(require_internal_token)])


@router.get("/users/{telegram_id}/digest/preview", response_model=DigestPreviewRead)
async def get_digest_preview(
    telegram_id: int, session: AsyncSession = Depends(get_session)
) -> DigestPreviewRead:
    user = await get_user_or_404(session, telegram_id)
    text = await digest_service.get_on_demand_digest(session, user)
    await session.commit()
    return DigestPreviewRead(has_content=text is not None, text=text)
