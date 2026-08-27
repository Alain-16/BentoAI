import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bentoai.shared.database import Base
from bentoai.shared.mixins import TimestampMixin, UUIDMixin


class User(UUIDMixin,TimestampMixin,Base):

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True,nullable=False)

    refresh_token: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",cascade="all, delete-orphan"
    )

    missions: Mapped[list["ShoppingMission"]] = relationship(back_populates="user")


class OtpCode(UUIDMixin, TimestampMixin,Base):

    __tablename__ = "otp_codes"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)

    code_hash: Mapped[str] = mapped_column(String(64))

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_otp_codes_email_expires_at", "email", "expires_at"),
    )


class RefreshToken(UUIDMixin,TimestampMixin,Base):

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),index=True)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )

    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")