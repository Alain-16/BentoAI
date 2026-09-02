import uuid
from decimal import Decimal

from pydantic import BaseModel

from bentoai.modules.planner.models import RequirementPriority

class RatingRead(BaseModel):

    value: float
    count: int


class SelectionIn(BaseModel):
    """What the customer sends when they Keep or Swap.

    One shape for both, because they are one operation: "this is my choice for
    this requirement". Two endpoints would be two code paths that must never
    disagree about what a selection means.
    """

    requirement_id: uuid.UUID
    product_id: str


class BasketOptionRead(BaseModel):
    """One product the customer may choose for one requirement."""

    product_id: str
    provider: str
    title: str

    price_amount: Decimal
    currency: str

    # How many, and what that comes to. Both are sent because a card shows the
    # unit price and the basket shows the line - deriving one in the frontend
    # would be the same arithmetic in a second place.
    quantity: int = 1
    line_total: Decimal

    # Who put this in the basket - "optimizer" or "customer". None when it is
    # not the chosen one. Lets the workspace say "you changed this".
    selected_by: str | None = None

    # What it cost when it was chosen, if that is not what it costs now.
    price_was: Decimal | None = None
    merchant_name: str
    merchant_domain: str
    product_url: str | None = None
    image_url: str | None = None
    ratings: RatingRead | None = None
    score: float

    
    included_as: str

    # requirement_match / quality / price / preference_match, each 0-1. Shown as
    # dots in the comparison. The overall score is deliberately not sent.
    breakdown: dict[str, float] = {}

    
    note: str = ""

    reason: str = ""
    trade_offs: list[str] = []

    preferred: bool = False
    chosen: bool = False




class BasketRequirementRead(BaseModel):
    requirement_id: uuid.UUID
    category: str
    priority: RequirementPriority
    quantity: int = 1
    options: list[BasketOptionRead] = []


class BasketBlockerRead(BaseModel):
    """Something that has to be sorted out before this basket can be approved."""

    requirement_id: uuid.UUID
    category: str
    title: str
    # "no_longer_listed" or "out_of_stock". Different problems: one might come
    # back, the other will not.
    reason: str
    replacement: dict | None = None


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

    # What the review screen needs. Empty blockers means the basket can be
    # approved; anything in it must be resolved first.
    blockers: list[BasketBlockerRead] = []
    item_count: int = 0
    merchant_count: int = 0
    requirements_met: int = 0
    requirements_total: int = 0


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
                    quantity=requirement.quantity,
                    line_total=offer.price_amount * requirement.quantity,
                    merchant_name=offer.merchant_name,
                    merchant_domain=offer.merchant_domain,
                    product_url=offer.product_url,
                    image_url=offer.image_url,
                    ratings=(RatingRead(value=candidate.rating_value, count=candidate.rating_count or 0) if candidate.rating_value is not None else None),
                    score=stored.get("score", 0.0),
                    included_as=stored.get("included_as", ""),
                    breakdown=stored.get("breakdown") or {},
                    note=stored.get("note", ""),
                    reason=stored.get("reason", ""),
                    trade_offs=stored.get("trade_offs") or [],
                    preferred=bool(stored.get("preferred")),
                    # Not the stored flag any more. chosen now means "this is
                    # what the customer has in their basket", which the view
                    # works out from basket_items.
                    chosen=bool(entry.get("chosen")),
                    selected_by=entry.get("selected_by"),
                    price_was=entry.get("price_was"),
                )
            )

        requirements.append(
            BasketRequirementRead(
                requirement_id=requirement.id,
                category=requirement.category,
                priority=requirement.priority,
                quantity=requirement.quantity,
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
        blockers=[BasketBlockerRead(**b) for b in view.get("blockers") or []],
        item_count=view.get("item_count", 0),
        merchant_count=view.get("merchant_count", 0),
        requirements_met=view.get("requirements_met", 0),
        requirements_total=view.get("requirements_total", 0),
    )