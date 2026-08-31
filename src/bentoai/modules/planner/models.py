import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bentoai.shared.database import Base
from bentoai.shared.mixins import TimestampMixin, UUIDMixin
from bentoai.shared.mixins import _enum

class MissionStatus(str, Enum):

    DRAFT = "draft"
    PLANNING = "planning"
    SEARCHING = "searching"
    EVALUATING = "evaluating"
    REVIEW = "review"
    BASKET_READY = "basket_ready"
    CHECKOUT_PENDING = "checkout_pending"
    PURCHASED = "purchased"
    TRACKING = "tracking"
    COMPLETE = "complete"


class RequirementPriority(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class RequirementStatus(str, Enum):
    PENDING = "pending"
    SATISFIED = "satisfied"
    SKIPPED = "skipped"


class BasketStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    CHECKED_OUT = "checked_out"
    ABANDONED = "abandoned"




class ShoppingMission(UUIDMixin, TimestampMixin,Base):

    __tablename__ = "shopping_missions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[MissionStatus] = mapped_column(
        _enum(MissionStatus), default=MissionStatus.DRAFT, nullable=False
    )

    
    goal: Mapped[str] = mapped_column(Text)

   
    budget_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    budget_currency: Mapped[str] = mapped_column(String(3), default="CAD")

    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    constraints: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    planning_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="missions")
    requirements: Mapped[list["MissionRequirement"]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="MissionRequirement.position",
    )
    baskets: Mapped[list["Basket"]] = relationship(
        back_populates="mission", cascade="all,delete-orphan"
    )

    discovery_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    evaluation_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_shopping_missions_user_id_status", "user_id", "status"),
    )



class MissionRequirement(UUIDMixin,TimestampMixin,Base):

    __tablename__ = "mission_requirements"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_missions.id", ondelete="CASCADE"), index=True
    )

    category: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    priority: Mapped[RequirementPriority] = mapped_column(
        _enum(RequirementPriority), default=RequirementPriority.REQUIRED
    )

    status: Mapped[RequirementStatus] = mapped_column(
        _enum(RequirementStatus), default=RequirementStatus.PENDING
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

   
    budget_allocation: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    mission: Mapped["ShoppingMission"] = relationship(back_populates="requirements")



class Basket(UUIDMixin, TimestampMixin, Base):
 
    __tablename__ = "baskets"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_missions.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[BasketStatus] = mapped_column(
        _enum(BasketStatus), default=BasketStatus.DRAFT, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="CAD")


    subtotal_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )

    mission: Mapped["ShoppingMission"] = relationship(back_populates="baskets")
    items: Mapped[list["BasketItem"]] = relationship(
        back_populates="basket", cascade="all, delete-orphan"
    )


class BasketItem(UUIDMixin, TimestampMixin, Base):


    __tablename__ = "basket_items"

    basket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("baskets.id", ondelete="CASCADE"), index=True
    )

   
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mission_requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True)
    


    provider: Mapped[str] = mapped_column(String(50))
    source_product_id: Mapped[str] = mapped_column(String(255))
    source_variant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    title_snapshot: Mapped[str] = mapped_column(String(500))
    variant_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CAD")


    item_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=True)

    basket: Mapped["Basket"] = relationship(back_populates="items")