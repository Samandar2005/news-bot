"""users, user_interests, custom_interests, notification_settings.

Language lives directly on User (it's read on nearly every request); only
digest scheduling toggles get their own table.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import Language
from shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from shared.models.digest import Digest
    from shared.models.interest import InterestCategory

EMBEDDING_DIM = 1024  # must match whichever embedding model is configured


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[Language] = mapped_column(
        String(2), default=Language.EN, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    interests: Mapped[list["UserInterest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    custom_interests: Mapped[list["CustomInterest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notification_settings: Mapped[NotificationSettings | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    digests: Mapped[list["Digest"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User telegram_id={self.telegram_id}>"


class UserInterest(Base):
    __tablename__ = "user_interests"
    __table_args__ = (
        CheckConstraint(
            "(category_id IS NOT NULL AND custom_interest_id IS NULL) OR "
            "(category_id IS NULL AND custom_interest_id IS NOT NULL)",
            name="exactly_one_of_category_or_custom",
        ),
        UniqueConstraint("user_id", "category_id", name="uq_user_category"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("interest_categories.id", ondelete="CASCADE"), nullable=True
    )
    custom_interest_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("custom_interests.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="interests")
    category: Mapped["InterestCategory | None"] = relationship(back_populates="user_interests")
    custom_interest: Mapped["CustomInterest | None"] = relationship(
        back_populates="user_interest"
    )


class CustomInterest(Base):
    __tablename__ = "custom_interests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phrase: Mapped[str] = mapped_column(String(256), nullable=False)
    # Semantic matching is v2 (spec 1.5); nullable until that ships.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="custom_interests")
    user_interest: Mapped["UserInterest | None"] = relationship(
        back_populates="custom_interest", uselist=False
    )


class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    morning_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evening_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    morning_time: Mapped[dt.time] = mapped_column(
        Time, default=dt.time(7, 0), nullable=False
    )
    evening_time: Mapped[dt.time] = mapped_column(
        Time, default=dt.time(19, 0), nullable=False
    )
    # Fixed default for MVP (spec 1.4) — per-user timezones are v2.
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent", nullable=False)

    user: Mapped["User"] = relationship(back_populates="notification_settings")
