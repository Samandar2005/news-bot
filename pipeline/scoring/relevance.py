"""User relevance scoring and final per-user ranking (spec Phase 3 stages
10 & 12 / Phase 6's FinalScore formula):

    FinalScore(user, event) = Importance(event) * (1 + w6*U) + w7*G - w8*D

U = user interest match, G = geo/locale relevance bonus, D = repeat-story
penalty. Weights live in shared/config.py, same pattern as importance.py.

**The "must-know story override" edge case (spec Phase 3 stage 10) isn't
special-cased anywhere — it falls out of the formula's own shape.** An
event with zero interest match (U=0) still scores at its full
importance_score, not zero, since Importance*(1+0) == Importance. A
sufficiently important event can still outrank a matched-but-low-
importance one purely on that basis, with no separate override logic
needed. compute_final_score's docstring below spells this out; it's the
reason the formula is written the way it is.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.enums import EventStatus
from shared.models import (
    CustomInterest,
    Digest,
    DigestItem,
    NewsArticle,
    NewsEvent,
    User,
    UserInterest,
)

# Geo relevance keywords (spec Phase 6.1: "e.g. Uzbek users get boost for
# Central Asia news"). Approximated via user.language == "uz" rather than
# real per-user location data, which this schema doesn't collect —
# Uzbek-language is this product's strongest available signal of being
# Uzbekistan-based (spec Phase 1.2's core persona). A light heuristic,
# not a claim of genuine geo-detection.
_GEO_KEYWORDS = [
    "uzbekistan",
    "tashkent",
    "central asia",
    "узбекистан",
    "ташкент",
    "центральная азия",
    "o'zbekiston",
    "toshkent",
    "markaziy osiyo",
]

# A confirmed predefined-category match is closer to "the user explicitly
# opted into this" than a keyword hit against a free-text phrase, which
# is just a guess at intent — weighted lower accordingly.
_CUSTOM_INTEREST_MATCH_SCORE = 0.75


@dataclass(frozen=True, slots=True)
class RankedEvent:
    event: NewsEvent
    final_score: float
    interest_match: float
    geo_relevance: float
    repeat_penalty: float


def compute_final_score(
    *,
    importance_score: float,
    interest_match: float,
    geo_relevance: float,
    repeat_penalty: float,
) -> float:
    """Pure function — the Phase 6 FinalScore formula, unit-testable
    against constructed cases without a database. See module docstring
    for why a zero interest_match doesn't zero out the whole score.
    """
    return (
        importance_score * (1 + settings.weight_interest_boost * interest_match)
        + settings.weight_geo_bonus * geo_relevance
        - settings.weight_repeat_penalty * repeat_penalty
    )


async def _event_text(session: AsyncSession, event_id: int) -> str:
    result = await session.execute(
        select(NewsArticle.title, NewsArticle.content).where(NewsArticle.event_id == event_id)
    )
    return " ".join(f"{title} {content}" for title, content in result.all()).lower()


async def compute_interest_match(session: AsyncSession, user_id: int, event: NewsEvent) -> float:
    """1.0 for a confirmed predefined-category match; a partial score for
    a custom-interest keyword hit (spec Phase 3 stage 10: "keyword or
    embedding similarity" — keyword here, consistent with this pipeline's
    placeholder-embedding-aware design elsewhere); 0.0 otherwise.
    """
    if event.category_id is not None:
        result = await session.execute(
            select(UserInterest.id).where(
                UserInterest.user_id == user_id, UserInterest.category_id == event.category_id
            )
        )
        if result.scalar_one_or_none() is not None:
            return 1.0

    custom_result = await session.execute(
        select(CustomInterest.phrase)
        .join(UserInterest, UserInterest.custom_interest_id == CustomInterest.id)
        .where(UserInterest.user_id == user_id)
    )
    phrases = [p.lower() for (p,) in custom_result.all()]
    if not phrases:
        return 0.0

    text = await _event_text(session, event.id)
    return _CUSTOM_INTEREST_MATCH_SCORE if any(phrase in text for phrase in phrases) else 0.0


async def compute_geo_relevance(session: AsyncSession, user: User, event: NewsEvent) -> float:
    if user.language != "uz":
        return 0.0
    text = await _event_text(session, event.id)
    return 1.0 if any(keyword in text for keyword in _GEO_KEYWORDS) else 0.0


async def compute_repeat_penalty(session: AsyncSession, user_id: int, event: NewsEvent) -> float:
    """1.0 if this user has ever received this exact event in a past
    digest, else 0.0 — spec Phase 3 stage 12's "avoid re-surfacing same
    story every digest" edge case. A full-history check rather than a
    time-windowed one, for MVP simplicity; events naturally age out of
    relevance anyway via importance.py's continuous freshness decay, so
    an old repeat is already unlikely to rank high enough to matter.
    """
    result = await session.execute(
        select(DigestItem.id)
        .join(Digest, Digest.id == DigestItem.digest_id)
        .where(Digest.user_id == user_id, DigestItem.event_id == event.id)
        .limit(1)
    )
    return 1.0 if result.scalar_one_or_none() is not None else 0.0


async def get_candidate_events(session: AsyncSession, batch_limit: int = 500) -> list[NewsEvent]:
    """All active events, most important first — deliberately unfiltered
    by category or importance floor (unlike summarization's cost-driven
    threshold in pipeline/ai/summarizer.py): ranking is free to compute,
    so there's no reason to gate it the way an LLM call needs to be."""
    result = await session.execute(
        select(NewsEvent)
        .where(NewsEvent.status == EventStatus.ACTIVE)
        .order_by(NewsEvent.importance_score.desc())
        .limit(batch_limit)
    )
    return list(result.scalars().all())


async def rank_events_for_user(
    session: AsyncSession,
    user: User,
    candidate_events: list[NewsEvent] | None = None,
    limit: int | None = None,
) -> list[RankedEvent]:
    """Scores and sorts candidate_events (or all active events, if not
    given) for one user. Returns at most `limit` (default
    settings.digest_max_items) results, highest FinalScore first.

    Note this doesn't filter by summary availability in the user's
    language — that's a digest-assembly concern (M12), not a ranking
    one; this module's job is producing a correctly-ordered list of
    events by relevance, independent of what's ready to display yet.
    """
    events = (
        candidate_events if candidate_events is not None else await get_candidate_events(session)
    )
    result_limit = limit if limit is not None else settings.digest_max_items

    ranked: list[RankedEvent] = []
    for event in events:
        interest_match = await compute_interest_match(session, user.id, event)
        geo_relevance = await compute_geo_relevance(session, user, event)
        repeat_penalty = await compute_repeat_penalty(session, user.id, event)
        final_score = compute_final_score(
            importance_score=event.importance_score,
            interest_match=interest_match,
            geo_relevance=geo_relevance,
            repeat_penalty=repeat_penalty,
        )
        ranked.append(
            RankedEvent(
                event=event,
                final_score=final_score,
                interest_match=interest_match,
                geo_relevance=geo_relevance,
                repeat_penalty=repeat_penalty,
            )
        )

    ranked.sort(key=lambda r: r.final_score, reverse=True)
    return ranked[:result_limit]
