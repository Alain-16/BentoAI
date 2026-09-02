import uuid
from decimal import Decimal

from pydantic import BaseModel

from bentoai.modules.planner.models import RequirementPriority


class OfferRead(BaseModel):

    merchant_name: str
    merchant_domain: str
    price_amount: Decimal
    currency: str
    availability: str
    product_url: str | None = None
    image_url: str | None = None


class RecommendedProductRead(BaseModel):
    product_id: str
    provider: str
    title: str

    score: float
    breakdown: dict[str, float]
    reason: str
    trade_offs: list[str]

    rating_value: float | None = None
    rating_count: int | None = None

    offer: OfferRead | None = None
    image_urls: list[str] = []


class RequirementRecommendationsRead(BaseModel):
    requirement_id: uuid.UUID
    category: str
    priority: RequirementPriority
    quantity: int = 1

  
    considered: int
    rejected: dict[str, int]

    products: list[RecommendedProductRead] = []


class MissionRecommendationsRead(BaseModel):
    mission_id: uuid.UUID
    status: str
    requirements: list[RequirementRecommendationsRead] = []
    notes: list[str] = []


def to_schema(recommendations: list[dict]) -> list[RequirementRecommendationsRead]:
    """Turn what the service built into what the API returns."""

    from bentoai.modules.evaluation.filtering import cheapest_purchasable

    out: list[RequirementRecommendationsRead] = []

    for group in recommendations:
        requirement = group["requirement"]
        products: list[RecommendedProductRead] = []

        for item in group["items"]:
            candidate = item["candidate"]
            ranked = item["ranked"]

            offer = cheapest_purchasable(candidate)

            products.append(
                RecommendedProductRead(
                    product_id=candidate.source_product_id,
                    provider=candidate.provider,
                    title=candidate.title,
                    score=ranked.get("score", 0.0),
                    breakdown=ranked.get("breakdown") or {},
                    reason=ranked.get("reason", ""),
                    trade_offs=ranked.get("trade_offs") or [],
                    rating_value=candidate.rating_value,
                    rating_count=candidate.rating_count,
                    offer=(
                        OfferRead(
                            merchant_name=offer.merchant_name,
                            merchant_domain=offer.merchant_domain,
                            price_amount=offer.price_amount,
                            currency=offer.currency,
                            availability=offer.availability.value,
                            product_url=offer.product_url,
                            image_url=offer.image_url,
                        )
                        if offer
                        else None
                    ),
                    image_urls=candidate.image_urls,
                )
            )

        out.append(
            RequirementRecommendationsRead(
                requirement_id=requirement.id,
                category=requirement.category,
                priority=requirement.priority,
                quantity=requirement.quantity,
                considered=group["considered"],
                rejected=group["rejected"],
                products=products,
            )
        )

    return out