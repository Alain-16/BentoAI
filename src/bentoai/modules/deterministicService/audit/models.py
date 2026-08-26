import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bentoai.shared.mixins import _enum
from bentoai.shared.database import Base
from bentoai.shared.mixins import UUIDMixin

class ActorType(str, Enum):
    """Who caused the event."""

    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"
    PROVIDER = "provider"


class AuditEvent(UUIDMixin, Base):
    """One thing that happened, worth being able to look up later.

    """

    __tablename__ = "audit_events"

    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shopping_missions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    actor_type: Mapped[ActorType] = mapped_column(_enum(ActorType))

    
    event_type: Mapped[str] = mapped_column(String(100), index=True)


    event_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        
        Index("ix_audit_events_mission_id_created_at", "mission_id", "created_at")
    )