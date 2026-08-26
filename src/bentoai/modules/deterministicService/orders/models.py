import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bentoai.shared.mixins import _enum
from bentoai.shared.database import Base
from bentoai.shared.mixins import TimestampMixin,UUIDMixin

class OrderStatus(str, Enum):
   

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(UUIDMixin, TimestampMixin, Base):
  

    __tablename__ = "orders"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_missions.id", ondelete="CASCADE"), index=True
    )

    
    checkout_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("checkouts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    provider: Mapped[str] = mapped_column(String(50))
    external_order_id: Mapped[str] = mapped_column(String(255))

    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus), default=OrderStatus.PENDING
    )

    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CAD")

    placed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

  
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        
        UniqueConstraint(
            "provider", "external_order_id", name="uq_orders_provider_external_order_id"
        ),
    )

class OrderItem(UUIDMixin, TimestampMixin, Base):
        

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

 
    basket_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("basket_items.id", ondelete="SET NULL"), nullable=True
    )

    source_product_id: Mapped[str] = mapped_column(String(255))
    title_snapshot: Mapped[str] = mapped_column(String(500))

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CAD")

    order: Mapped["Order"] = relationship(back_populates="items")