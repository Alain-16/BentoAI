import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

class UUIDMixin:

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-100,
    )

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(

        DateTime(timezone=True),

        server_default=func.now(),
        nullable=False,
        sort_order=100,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=101,

    )