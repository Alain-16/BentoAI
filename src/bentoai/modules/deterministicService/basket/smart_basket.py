import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bentoai.modules.commerce.dtos import CandidateProduct, MerchantOffer
from bentoai.modules.commerce.models import Merchant, ProviderType
from bentoai.modules.planner.models import (
    Basket,
    BasketItem,
    BasketStatus,
    MissionRequirement,
    ShoppingMission,
)

logger = logging.getLogger(__name__)


async def ensure_basket(session: AsyncSession, mission: ShoppingMission) -> Basket:
    """The one draft basket for this mission, made if it does not exist.
    """
    stmt = (
        select(Basket)
        .where(Basket.mission_id == mission.id, Basket.status == BasketStatus.DRAFT)
        .options(selectinload(Basket.items))
    )
    basket = await session.scalar(stmt)

    if basket is None:
        basket = Basket(
            mission_id=mission.id,
            status=BasketStatus.DRAFT,
            currency=mission.budget_currency,
        )
        session.add(basket)
      
        await session.flush()
        logger.info("smart_basket_created mission_id=%s", mission.id)

    return basket


async def get_or_create_merchant(
    session: AsyncSession, offer: MerchantOffer
) -> Merchant | None:
    """Find the merchant behind an offer, recording it the first time we see it.
    """
    domain = (offer.merchant_domain or "").strip().lower()
    if not domain:
       
        return None

    merchant = await session.scalar(select(Merchant).where(Merchant.domain == domain))
    if merchant is not None:
        return merchant

    merchant = Merchant(
        name=offer.merchant_name or domain,
        domain=domain,
        provider_type=(
            ProviderType.SHOPIFY_GLOBAL
            if offer.provider == "shopify_global"
            else ProviderType.OTHER
        ),
    )
    session.add(merchant)
    await session.flush()
    logger.info("merchant_recorded domain=%s", domain)
    return merchant


async def select_product(
    session: AsyncSession,
    mission: ShoppingMission,
    requirement: MissionRequirement,
    candidate: CandidateProduct,
    offer: MerchantOffer,
    *,
    by: str = "customer",
) -> BasketItem:
    """Put one product in the basket for one requirement..
    """
    basket = await ensure_basket(session, mission)
    merchant = await get_or_create_merchant(session, offer)

    existing = next(
        (item for item in basket.items if item.requirement_id == requirement.id), None
    )

    if existing is None:
        existing = BasketItem(basket_id=basket.id, requirement_id=requirement.id)
        basket.items.append(existing)

    existing.provider = candidate.provider
    existing.source_product_id = candidate.source_product_id
    existing.source_variant_id = offer.source_variant_id
    existing.merchant_id = merchant.id if merchant else None

    existing.title_snapshot = candidate.title[:500]
    existing.image_url = offer.image_url or (
        candidate.image_urls[0] if candidate.image_urls else None
    )
    existing.unit_price_amount = offer.price_amount
    existing.currency = offer.currency
    existing.quantity = requirement.quantity
    existing.variant_snapshot = {
        "merchant_name": offer.merchant_name,
        "merchant_domain": offer.merchant_domain,
        "product_url": offer.product_url,
        "checkout_url": offer.checkout_url,
    }
    existing.item_metadata = {"selected_by": by}

    recalculate(basket)
    await session.flush()

    logger.info(
        "basket_item_selected mission_id=%s requirement=%s product=%s by=%s",
        mission.id,
        requirement.category,
        candidate.source_product_id,
        by,
    )
    return existing


async def seed_from_optimizer(
    session: AsyncSession,
    mission: ShoppingMission,
    picks: list[tuple[MissionRequirement, CandidateProduct, MerchantOffer]],
) -> Basket:
    """Fill an empty basket with what the optimizer worked out..
    """
    basket = await ensure_basket(session, mission)

    if basket.items:
        logger.info(
            "smart_basket_already_filled mission_id=%s items=%d - not reseeding",
            mission.id,
            len(basket.items),
        )
        return basket

    for requirement, candidate, offer in picks:
        await select_product(
            session, mission, requirement, candidate, offer, by="optimizer"
        )

    logger.info("smart_basket_seeded mission_id=%s items=%d", mission.id, len(picks))
    return basket


def prune_orphans(basket: Basket, live_requirement_ids: set[uuid.UUID]) -> list[str]:
    """Drop items whose requirement no longer exists.
    """
    orphans = [
        item
        for item in basket.items
        if item.requirement_id is None or item.requirement_id not in live_requirement_ids
    ]

    for item in orphans:
        basket.items.remove(item)

    if orphans:
        recalculate(basket)
        logger.info("basket_orphans_removed count=%d", len(orphans))

    return [item.title_snapshot for item in orphans]


def recalculate(basket: Basket) -> None:
    """Add the basket up from its rows.
    """
    subtotal = sum(
        (item.unit_price_amount * item.quantity for item in basket.items),
        Decimal("0.00"),
    )
    basket.subtotal_amount = subtotal
    
    basket.total_amount = subtotal


def selected_by_requirement(basket: Basket) -> dict[str, str]:
    """requirement id -> product id, for marking the pool."""
    return {
        str(item.requirement_id): item.source_product_id
        for item in basket.items
        if item.requirement_id
    }
