"""Digest assembly for one user (spec Phase 3 stage 13): ranks candidate
events, filters to only those with a cached summary in the user's
language (ranking itself deliberately doesn't do this filtering — see
pipeline/scoring/relevance.py's docstring — this is where that concern
actually gets resolved), and renders the final message text.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.digest.rendering import render_digest_message
from pipeline.scoring.relevance import RankedEvent, rank_events_for_user
from shared.models import EventSummary, User


@dataclass(frozen=True, slots=True)
class DigestBuild:
    has_content: bool
    rendered_text: str | None
    included: list[RankedEvent]


async def build_digest_for_user(session: AsyncSession, user: User) -> DigestBuild:
    ranked = await rank_events_for_user(session, user)
    if not ranked:
        return DigestBuild(has_content=False, rendered_text=None, included=[])

    event_ids = [r.event.id for r in ranked]
    summaries_result = await session.execute(
        select(EventSummary.event_id, EventSummary.summary_text).where(
            EventSummary.event_id.in_(event_ids), EventSummary.language == user.language
        )
    )
    summary_by_event_id = dict(summaries_result.all())

    # Preserves ranked's order — summary_by_event_id is just a lookup,
    # not something to re-sort by.
    items = [
        (ranked_event, summary_by_event_id[ranked_event.event.id])
        for ranked_event in ranked
        if ranked_event.event.id in summary_by_event_id
    ]
    if not items:
        return DigestBuild(has_content=False, rendered_text=None, included=[])

    rendered_text = render_digest_message(items, user.language)
    included = [ranked_event for ranked_event, _summary in items]
    return DigestBuild(has_content=True, rendered_text=rendered_text, included=included)
