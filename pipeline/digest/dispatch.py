"""Digest generation + delivery batch orchestration (spec Phase 3 stages
13-14): iterates eligible users, builds each one's digest, sends it, and
records the outcome to digest_history (`digests` / `digest_items`).

**Why this is three sequential passes, not one loop with concurrent
sends:** SQLAlchemy's AsyncSession is not safe for concurrent use from
multiple coroutines — interleaving `await session.execute(...)` calls
from a batch run via `asyncio.gather` on the *same* session corrupts its
state. But the whole point of batching sends is concurrency, to stay
under Telegram's throughput limits without the run taking forever
serially. Splitting into build (DB, serial) → send (network, concurrent)
→ record (DB, serial) gets genuine send concurrency without ever
touching the session from more than one coroutine at a time.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.digest.assembly import DigestBuild, build_digest_for_user
from pipeline.digest.delivery import send_digest_message
from shared.enums import DigestStatus, DigestType
from shared.models import Digest, DigestItem, NotificationSettings, User

# Telegram's documented bulk-send limit is ~30 messages/second globally
# (spec Phase 3 stage 14); staying comfortably under it rather than
# tuning right up to the edge.
_BATCH_SIZE = 20
_BATCH_DELAY_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class DispatchStats:
    users_considered: int
    sent: int
    skipped_no_content: int
    failed: int


async def _get_eligible_users(session: AsyncSession, digest_type: DigestType) -> list[User]:
    enabled_column = (
        NotificationSettings.morning_enabled
        if digest_type == DigestType.MORNING
        else NotificationSettings.evening_enabled
    )
    result = await session.execute(
        select(User)
        .join(NotificationSettings, NotificationSettings.user_id == User.id)
        .where(User.is_active.is_(True), enabled_column.is_(True))
    )
    return list(result.scalars().all())


async def dispatch_digests(
    session: AsyncSession, bot: Bot, digest_type: DigestType
) -> DispatchStats:
    users = await _get_eligible_users(session, digest_type)

    # Pass 1 — build (DB-bound, serial on the one session).
    builds: dict[int, DigestBuild] = {}
    for user in users:
        builds[user.id] = await build_digest_for_user(session, user)

    # Pass 2 — send (network-bound, concurrent within rate-limited batches).
    users_with_content = [u for u in users if builds[u.id].has_content]
    delivered_by_user_id: dict[int, bool] = {}
    for i in range(0, len(users_with_content), _BATCH_SIZE):
        batch = users_with_content[i : i + _BATCH_SIZE]
        outcomes = await asyncio.gather(
            *(send_digest_message(bot, u.telegram_id, builds[u.id].rendered_text) for u in batch)
        )
        for user, delivered in zip(batch, outcomes, strict=True):
            delivered_by_user_id[user.id] = delivered
        if i + _BATCH_SIZE < len(users_with_content):
            await asyncio.sleep(_BATCH_DELAY_SECONDS)

    # Pass 3 — record (DB-bound, serial again).
    sent = skipped_no_content = failed = 0
    now = datetime.now(UTC)
    for user in users:
        build = builds[user.id]

        if not build.has_content:
            session.add(
                Digest(
                    user_id=user.id,
                    digest_type=digest_type,
                    sent_at=now,
                    status=DigestStatus.SKIPPED_NO_CONTENT,
                )
            )
            skipped_no_content += 1
            continue

        if not delivered_by_user_id[user.id]:
            # spec Phase 3 stage 14's named edge case: a confirmed
            # delivery failure (most commonly, a blocked bot) means
            # future cycles shouldn't keep trying this user.
            user.is_active = False
            session.add(
                Digest(
                    user_id=user.id,
                    digest_type=digest_type,
                    sent_at=now,
                    status=DigestStatus.FAILED,
                )
            )
            failed += 1
            continue

        digest = Digest(
            user_id=user.id, digest_type=digest_type, sent_at=now, status=DigestStatus.SENT
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
        sent += 1

    await session.flush()

    return DispatchStats(
        users_considered=len(users),
        sent=sent,
        skipped_no_content=skipped_no_content,
        failed=failed,
    )
