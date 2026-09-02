import uuid
from decimal import Decimal

from pydantic import BaseModel

from bentoai.modules.planner.models import RequirementPriority


class BasketOptionRead(BaseModel):
    """One product the customer may choose for one requirement."""

    product_id: str
    provider: str
    title: str

    price_amount: Decimal
    currency: str
    merchant_name: str
    merchant_domain: str
    product_url: str | None = None
    image_url: str | None = None

    score: float

    
    included_as: str

    
    note: str = ""

    reason: str = ""
    trade_offs: list[str] = []

    preferred: bool = False
    chosen: bool = False


class BasketRequirementRead(BaseModel):
    requirement_id: uuid.UUID
    category: str
    priority: RequirementPriority
    options: list[BasketOptionRead] = []


class MissionBasketRead(BaseModel):
    mission_id: uuid.UUID
    status: str

    budget_amount: Decimal | None = None
    budget_currency: str

    total: Decimal
    remaining: Decimal | None = None

    # False when the required items cannot be afforded at all. The basket still
    # comes back, showing the cheapest possible version and the shortfall.
    feasible: bool = True

    requirements: list[BasketRequirementRead] = []
    notes: list[str] = []


def to_schema(mission, view: dict) -> MissionBasketRead:
    """Turn what the service built into what the API returns."""
    requirements: list[BasketRequirementRead] = []

    for group in view.get("groups") or []:
        requirement = group["requirement"]
        options: list[BasketOptionRead] = []

        for entry in group["options"]:
            stored = entry["stored"]
            candidate = entry["candidate"]
            offer = entry["offer"]

            options.append(
                BasketOptionRead(
                    product_id=candidate.source_product_id,
                    provider=candidate.provider,
                    title=candidate.title,
                    price_amount=offer.price_amount,
                    currency=offer.currency,
                    merchant_name=offer.merchant_name,
                    merchant_domain=offer.merchant_domain,
                    product_url=offer.product_url,
                    image_url=offer.image_url,
                    score=stored.get("score", 0.0),
                    included_as=stored.get("included_as", ""),
                    note=stored.get("note", ""),
                    reason=stored.get("reason", ""),
                    trade_offs=stored.get("trade_offs") or [],
                    preferred=bool(stored.get("preferred")),
                    chosen=bool(stored.get("chosen")),
                )
            )

        requirements.append(
            BasketRequirementRead(
                requirement_id=requirement.id,
                category=requirement.category,
                priority=requirement.priority,
                options=options,
            )
        )

    return MissionBasketRead(
        mission_id=mission.id,
        status=mission.status.value,
        budget_amount=mission.budget_amount,
        budget_currency=mission.budget_currency,
        total=view.get("total", 0),
        remaining=view.get("remaining"),
        feasible=view.get("feasible", True),
        requirements=requirements,
        notes=view.get("notes") or [],
    )