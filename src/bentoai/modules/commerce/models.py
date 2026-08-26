import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bentoai.shared.mixins import _enum
from bentoai.shared.database import Base
from bentoai.shared.mixins import TimestampMixin, UUIDMixin


class ProviderType(str, Enum):
    SHOPIFY_GLOBAL = "shopify_global"
    UCP = "ucp"
    OTHER = "other"


class MerchantStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNREACHABLE = "unreachable"


class CheckoutStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"



class Merchant(UUIDMixin, TimestampMixin, Base):
  

    __tablename__ = "merchants"

    name: Mapped[str] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    provider_type: Mapped[ProviderType] = mapped_column(_enum(ProviderType))
    ucp_profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

  
    capabilities: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

  
    auth_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    status: Mapped[MerchantStatus] = mapped_column(
        _enum(MerchantStatus), default=MerchantStatus.ACTIVE
    )


class Checkout(UUIDMixin, TimestampMixin, Base):
  

    __tablename__ = "checkouts"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_missions.id", ondelete="CASCADE"), index=True
    )
    basket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("baskets.id", ondelete="CASCADE"), index=True
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    provider: Mapped[str] = mapped_column(String(50))
    status: Mapped[CheckoutStatus] = mapped_column(
        _enum(CheckoutStatus), default=CheckoutStatus.CREATED
    )

 
    external_checkout_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")

   
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )


    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)