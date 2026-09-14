"""One-time / idempotent seed data.

Run with:  python -m backend.db.seed

Currently seeds the 14 predefined interest categories from the spec
(product description, item 3). Safe to re-run — uses upsert-by-key so it
won't create duplicates or wipe manually-tuned `default_weight` values on
categories that already exist... actually it *does* refresh weights, since
these are meant to be edited here and re-seeded; see comment below.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import session_scope
from shared.models import InterestCategory

# key, name_en, name_ru, name_uz, default_weight
# Weights are a manually curated starting point (spec Phase 6.3) — broadly
# impactful categories (World News, Natural Disasters, Politics) start
# higher than niche technical ones (Python, Startups). Tune freely; this
# file is the source of truth for these values.
PREDEFINED_CATEGORIES: list[tuple[str, str, str, str, float]] = [
    ("world_news", "World News", "Мировые новости", "Jahon yangiliklari", 0.80),
    ("politics", "Politics", "Политика", "Siyosat", 0.75),
    ("technology", "Technology", "Технологии", "Texnologiya", 0.55),
    ("programming", "Programming", "Программирование", "Dasturlash", 0.40),
    ("python", "Python", "Python", "Python", 0.35),
    (
        "artificial_intelligence",
        "Artificial Intelligence",
        "Искусственный интеллект",
        "Sun'iy intellekt",
        0.55,
    ),
    ("cybersecurity", "Cybersecurity", "Кибербезопасность", "Kiberxavfsizlik", 0.55),
    ("science", "Science", "Наука", "Fan", 0.60),
    ("business", "Business", "Бизнес", "Biznes", 0.60),
    ("finance", "Finance", "Финансы", "Moliya", 0.60),
    ("natural_disasters", "Natural Disasters", "Стихийные бедствия", "Tabiiy ofatlar", 0.85),
    ("space", "Space", "Космос", "Kosmos", 0.50),
    ("startups", "Startups", "Стартапы", "Startaplar", 0.45),
    (
        "software_development",
        "Software Development",
        "Разработка ПО",
        "Dasturiy ta'minot ishlab chiqish",
        0.40,
    ),
]


async def seed_categories(session: AsyncSession) -> None:
    result = await session.execute(select(InterestCategory))
    existing = {c.key: c for c in result.scalars().all()}

    created, updated = 0, 0
    for key, name_en, name_ru, name_uz, weight in PREDEFINED_CATEGORIES:
        if key in existing:
            cat = existing[key]
            cat.name_en, cat.name_ru, cat.name_uz = name_en, name_ru, name_uz
            cat.default_weight = weight
            updated += 1
        else:
            session.add(
                InterestCategory(
                    key=key,
                    name_en=name_en,
                    name_ru=name_ru,
                    name_uz=name_uz,
                    is_predefined=True,
                    default_weight=weight,
                )
            )
            created += 1

    print(f"Categories: {created} created, {updated} updated.")


async def main() -> None:
    async with session_scope() as session:
        await seed_categories(session)


if __name__ == "__main__":
    asyncio.run(main())
