"""On-demand digest generation and recording (spec Phase 3 stage 13 /
M13's /news command).

Deliberately distinct from pipeline/digest/dispatch.py's scheduled bulk
dispatch:
- single user, not batched — no need for the DB-serial/network-concurrent
  split that module's docstring explains.
- doesn't check NotificationSettings.morning_enabled/evening_enabled — a
  user explicitly asking "show me the news now" should get it regardless
  of their push preferences; those toggles only gate the *scheduled*
  pushes.
- doesn't send via Telegram itself. The backend has no Bot instance and
  isn't meant to (spec Phase 8.2: only the bot process talks to
  Telegram) — this returns rendered text, and bot/handlers/news.py sends
  it as a direct reply to the /news command.
- still records a digests/digest_items entry (digest_type=ON_DEMAND) so
  the repeat-story penalty in pipeline/scoring/relevance.py knows this
  event was already shown, the same as a scheduled digest would.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.digest.assembly import build_digest_for_user
from shared.enums import DigestStatus, DigestType
from shared.models import Digest, DigestItem, User


async def get_on_demand_digest(session: AsyncSession, user: User) -> str | None:
    """Returns rendered digest text, or None if there's nothing to show
    right now."""
    build = await build_digest_for_user(session, user)
    now = datetime.now(UTC)

    if not build.has_content:
        session.add(
            Digest(
                user_id=user.id,
                digest_type=DigestType.ON_DEMAND,
                sent_at=now,
                status=DigestStatus.SKIPPED_NO_CONTENT,
            )
        )
        await session.flush()
        return None

    digest = Digest(
        user_id=user.id, digest_type=DigestType.ON_DEMAND, sent_at=now, status=DigestStatus.SENT
    )
    session.add(digest)
    await session.flush()

    for position, ranked_event in enumerate(build.included, start=1):
        session.add(
            DigestItem(
                digest_id=digest.id,
                event_id=ranked_event.event.id,
                rank_position=position,
                final_score=ranked_event.final_score,
            )
        )
    await session.flush()

    return build.rendered_text
