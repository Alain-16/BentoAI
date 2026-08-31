import logging
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

from bentoai.modules.commerce.dtos import Availability, CandidateProduct, MerchantOffer
from bentoai.modules.planner.models import ShoppingMission

logger = logging.getLogger(__name__)

class RejectionReason(str, Enum):


    NO_OFFERS = "no_offers"
    OUT_OF_STOCK = "out_of_stock"
    CURRENCY_MISMATCH = "currency_mismatch"
    OVER_BUDGET = "over_budget"
    EXCLUDED_BRAND = "excluded_brand"


@dataclass(frozen=True)
class Rejection:
    product_id: str
    title: str
    reason: RejectionReason


@dataclass
class FilterOutcome:
    accepted: list[CandidateProduct] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)

    def tally(self) -> dict[str, int]:
        """How many fell at each rule, for the audit event and the logs."""
        counts: dict[str, int] = {}
        for rejection in self.rejected:
            counts[rejection.reason.value] = counts.get(rejection.reason.value, 0) + 1
        return counts


def purchasable_offers(candidate: CandidateProduct) -> list[MerchantOffer]:
    """The offers we could actually put in a basket.

    
    """
    return [o for o in candidate.offers if o.availability is not Availability.OUT_OF_STOCK]


def cheapest_purchasable(candidate: CandidateProduct) -> MerchantOffer | None:
    """The lowest-priced offer we could actually buy, or None if there is none."""
    offers = purchasable_offers(candidate)
    return min(offers, key=lambda o: o.price_amount) if offers else None


def excluded_brands(mission: ShoppingMission) -> list[str]:
    """Brand names the customer ruled out, lower-cased for comparing.

    
    """
    items = (mission.constraints or {}).get("items") or []
    return [
        str(item.get("value", "")).strip().lower()
        for item in items
        if "brand" in str(item.get("type", "")).lower()
        and str(item.get("strength", "")).lower() == "hard"
        and str(item.get("value", "")).strip()
    ]


def apply_hard_filters(
    candidates: list[CandidateProduct], mission: ShoppingMission
) -> FilterOutcome:
    """Keep the candidates that could work; record why the rest could not.

    """
    outcome = FilterOutcome()

    budget = mission.budget_amount
    currency = (mission.budget_currency or "").upper()
    banned = excluded_brands(mission)

    for candidate in candidates:
        reason = _first_failure(candidate, budget, currency, banned)

        if reason is None:
            outcome.accepted.append(candidate)
        else:
            outcome.rejected.append(
                Rejection(
                    product_id=candidate.source_product_id,
                    title=candidate.title,
                    reason=reason,
                )
            )

    logger.info(
        "hard_filter kept=%d rejected=%d reasons=%s",
        len(outcome.accepted),
        len(outcome.rejected),
        outcome.tally(),
    )
    return outcome


def _first_failure(
    candidate: CandidateProduct,
    budget: Decimal | None,
    currency: str,
    banned: list[str],
) -> RejectionReason | None:
    """Run the rules in order and return the first one this product breaks."""

    
    if not candidate.offers:
        return RejectionReason.NO_OFFERS

    offer = cheapest_purchasable(candidate)
    if offer is None:
        return RejectionReason.OUT_OF_STOCK


    if currency and offer.currency.upper() != currency:
        return RejectionReason.CURRENCY_MISMATCH

 
    if budget is not None and offer.price_amount > budget:
        return RejectionReason.OVER_BUDGET

    # A brand the customer ruled out. We match on the title
    if banned:
        title = candidate.title.lower()
        if any(brand in title for brand in banned):
            return RejectionReason.EXCLUDED_BRAND

    return None