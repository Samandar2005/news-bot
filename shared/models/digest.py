"""digests, digest_items — one row per send event, plus the stories it
contained. Split into two tables so we can tell what a user already
received (used by the repeat-story penalty in the ranking formula,
spec Phase 6) without re-parsing rendered message text.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import DigestStatus, DigestType
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.event import NewsEvent
    from shared.models.user import User


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    digest_type: Mapped[DigestType] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[DigestStatus] = mapped_column(String(24), nullable=False)

    user: Mapped["User"] = relationship(back_populates="digests")
    items: Mapped[list["DigestItem"]] = relationship(
        back_populates="digest", cascade="all, delete-orphan"
    )


class DigestItem(Base):
    __tablename__ = "digest_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    digest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("digests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("news_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)

    digest: Mapped["Digest"] = relationship(back_populates="items")
    event: Mapped["NewsEvent"] = relationship(back_populates="digest_items")
