"""Interest-category data-access functions."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import InterestCategory, UserInterest


async def list_categories(session: AsyncSession) -> list[InterestCategory]:
    result = await session.execute(
        select(InterestCategory)
        .where(InterestCategory.is_predefined.is_(True))
        .order_by(InterestCategory.key)
    )
    return list(result.scalars().all())


async def get_user_categories(session: AsyncSession, user_id: int) -> list[InterestCategory]:
    result = await session.execute(
        select(InterestCategory)
        .join(UserInterest, UserInterest.category_id == InterestCategory.id)
        .where(UserInterest.user_id == user_id)
        .order_by(InterestCategory.key)
    )
    return list(result.scalars().all())


class InvalidCategoryIds(ValueError):
    def __init__(self, invalid_ids: set[int]) -> None:
        self.invalid_ids = invalid_ids
        super().__init__(f"Unknown category ids: {sorted(invalid_ids)}")


async def set_user_categories(
    session: AsyncSession, user_id: int, category_ids: list[int]
) -> list[InterestCategory]:
    """Replace the user's full predefined-category selection.

    Validates every id exists before touching any rows — a partial write
    on a bad id would leave the user in a confusing half-updated state.
    """
    requested = set(category_ids)
    if requested:
        result = await session.execute(
            select(InterestCategory.id).where(InterestCategory.id.in_(requested))
        )
        found = set(result.scalars().all())
        if found != requested:
            raise InvalidCategoryIds(requested - found)

    await session.execute(
        delete(UserInterest).where(
            UserInterest.user_id == user_id, UserInterest.category_id.is_not(None)
        )
    )
    for category_id in requested:
        session.add(UserInterest(user_id=user_id, category_id=category_id))
    await session.flush()

    return await get_user_categories(session, user_id)
