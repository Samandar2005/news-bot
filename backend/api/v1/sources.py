"""Admin-only source management: GET/POST /api/v1/sources,
GET/PATCH/DELETE /api/v1/sources/{id} (spec Phase 8.1 / 8.2).

Separate from the internal-token-protected routers (users, interests) —
this is admin functionality, not something the bot itself calls, so it
gets its own auth dependency per spec Phase 8.1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import require_admin_token
from backend.db.session import get_session
from backend.schemas.source import SourceCreate, SourceRead, SourceUpdate
from backend.services.sources import service as sources_service

router = APIRouter(
    prefix="/sources", tags=["sources"], dependencies=[Depends(require_admin_token)]
)


@router.get("", response_model=list[SourceRead])
async def list_sources(session: AsyncSession = Depends(get_session)) -> list[SourceRead]:
    sources = await sources_service.list_sources(session)
    return [SourceRead.model_validate(s) for s in sources]


@router.post("", response_model=SourceRead)
async def create_source(
    payload: SourceCreate, session: AsyncSession = Depends(get_session)
) -> SourceRead:
    source = await sources_service.create_source(session, **payload.model_dump())
    await session.commit()
    return SourceRead.model_validate(source)


async def _get_source_or_404(session: AsyncSession, source_id: int):
    source = await sources_service.get_source(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(source_id: int, session: AsyncSession = Depends(get_session)) -> SourceRead:
    source = await _get_source_or_404(session, source_id)
    return SourceRead.model_validate(source)


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int, payload: SourceUpdate, session: AsyncSession = Depends(get_session)
) -> SourceRead:
    source = await _get_source_or_404(session, source_id)
    updated, _events_recomputed = await sources_service.update_source(
        session, source, **payload.model_dump()
    )
    await session.commit()
    return SourceRead.model_validate(updated)


@router.delete("/{source_id}", response_model=SourceRead)
async def deactivate_source(
    source_id: int, session: AsyncSession = Depends(get_session)
) -> SourceRead:
    """Soft delete — see backend/services/sources/service.py for why this
    doesn't remove the row."""
    source = await _get_source_or_404(session, source_id)
    deactivated = await sources_service.deactivate_source(session, source)
    await session.commit()
    return SourceRead.model_validate(deactivated)
