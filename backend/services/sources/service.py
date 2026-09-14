"""Source management data-access functions (spec Phase 8.2)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.processing.reliability import recompute_events_for_source
from shared.models import NewsSource


async def list_sources(session: AsyncSession) -> list[NewsSource]:
    result = await session.execute(select(NewsSource).order_by(NewsSource.name))
    return list(result.scalars().all())


async def get_source(session: AsyncSession, source_id: int) -> NewsSource | None:
    return await session.get(NewsSource, source_id)


async def create_source(session: AsyncSession, **fields: object) -> NewsSource:
    source = NewsSource(**fields)
    session.add(source)
    await session.flush()
    await session.refresh(source)
    return source


async def update_source(
    session: AsyncSession, source: NewsSource, **fields: object
) -> tuple[NewsSource, int]:
    """Returns (updated_source, events_recomputed) — events_recomputed is
    0 unless reliability_score was actually part of this update, so
    callers/tests can tell whether the spec Phase 3 stage 8 recompute
    path actually ran.
    """
    reliability_changed = (
        "reliability_score" in fields
        and fields["reliability_score"] is not None
        and fields["reliability_score"] != source.reliability_score
    )

    for key, value in fields.items():
        if value is not None:
            setattr(source, key, value)
    await session.flush()

    events_recomputed = 0
    if reliability_changed:
        events_recomputed = await recompute_events_for_source(session, source.id)
        await session.flush()

    await session.refresh(source)
    return source, events_recomputed


async def deactivate_source(session: AsyncSession, source: NewsSource) -> NewsSource:
    """Soft delete only — a hard DELETE would cascade and destroy real
    collected articles/events that reference this source via FK. Setting
    is_active=False stops future collection without touching history;
    PATCH is_active=true to reverse it.
    """
    source.is_active = False
    await session.flush()
    await session.refresh(source)
    return source
