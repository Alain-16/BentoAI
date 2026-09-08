"""Shared setup for every test.

The one import below is load-bearing. SQLAlchemy resolves relationships by
class name - ShoppingMission.user points at "User" as a string - and it can
only do that once every model has been imported somewhere. bentoai.models
imports them all.

Without it, the first test that constructs a mission fails with
"expression 'User' failed to locate a name", which says nothing about the real
cause and costs an hour the first time you meet it.
"""

import uuid
from decimal import Decimal

import pytest

import bentoai.models  # noqa: F401  - registers every mapper

from bentoai.modules.commerce.dtos import Availability, CandidateProduct, MerchantOffer
from bentoai.modules.planner.models import MissionRequirement, RequirementPriority


@pytest.fixture
def make_requirement():
    """Build a requirement the way the database would hand one back.

    id is passed explicitly because the UUID default only fires on insert. A
    hand-built requirement has id=None, and solve() keys its preferences by
    str(requirement.id) - so without this the preference bonus silently never
    matches anything.
    """

    def build(category="adjustable dumbbells", *, priority=RequirementPriority.REQUIRED,
              position=0, quantity=1):
        return MissionRequirement(
            id=uuid.uuid4(),
            category=category,
            priority=priority,
            position=position,
            quantity=quantity,
        )

    return build


@pytest.fixture
def make_candidate():
    """A product with one purchasable offer, which is the normal case."""

    def build(title, price, *, rating=None, count=None,
              availability=Availability.IN_STOCK, merchant="Fitness Depot"):
        return CandidateProduct(
            provider="shopify_global",
            source_product_id=f"gid://shopify/p/{title.replace(' ', '')}",
            title=title,
            rating_value=rating,
            rating_count=count,
            offers=[
                MerchantOffer(
                    provider="shopify_global",
                    source_variant_id=f"gid://shopify/v/{title.replace(' ', '')}",
                    merchant_name=merchant,
                    merchant_domain=f"{merchant.lower().replace(' ', '-')}.myshopify.com",
                    price_amount=Decimal(price),
                    currency="CAD",
                    availability=availability,
                )
            ],
        )

    return build


@pytest.fixture
def make_group(make_candidate):
    """One entry in what build_recommendations returns.

    Shape: {"requirement": ..., "items": [{"candidate": ..., "ranked": {...}}]}
    Only those two keys are read by build_option_pool.
    """

    def build(requirement, products):
        # products: list of (title, price, score) or (title, price, score, rating, count)
        items = []
        for spec in products:
            title, price, score = spec[0], spec[1], spec[2]
            rating = spec[3] if len(spec) > 3 else None
            count = spec[4] if len(spec) > 4 else None
            items.append(
                {
                    "candidate": make_candidate(title, price, rating=rating, count=count),
                    "ranked": {
                        "score": score,
                        "reason": f"{title} reason",
                        "trade_offs": [],
                        "breakdown": {"requirement_match": 1.0, "quality": 0.8,
                                      "price": 0.5, "preference_match": 1.0},
                    },
                }
            )
        return {"requirement": requirement, "items": items}

    return build
