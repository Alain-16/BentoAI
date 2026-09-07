"""The workflow: which steps exist, and what state triggers each one.

This is the readable map. One line per agent, keyed by the mission state that
calls for it. Adding a fifth agent means writing its step and adding a line
here - never an if/elif chain in the orchestrator, and never a route per agent
(§9.2 forbids exposing agents as endpoints).

WHY THERE ARE NO EDGES IN THIS FILE

Because the mission's own status already carries them. Discovery holds at
SEARCHING when it finds nothing; the basket optimizer always returns REVIEW;
REVIEW goes back to SEARCHING when a customer edits their plan. An edge saying
"after discovery, evaluate" would be wrong in every one of those cases.

So the graph is compiled from the table below rather than from a list of edges,
and the one router in orchestrator.py asks the mission where it got to. There is
one description of the workflow, and this is it.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.config.settings import get_settings
from bentoai.modules.commerce.gateway import CommerceGateway
from bentoai.modules.commerce.providers.shopify_global import (
    ShopifyGlobalCatalogProvider,
)
from bentoai.modules.deterministicService.basket.step import BasketOptimizerStep
from bentoai.modules.discovery.step import DiscoveryStep
from bentoai.modules.evaluation.step import EvaluationStep
from bentoai.modules.orchestration.orchestrator import ShoppingOrchestrator
from bentoai.modules.planner.models import MissionStatus
from bentoai.modules.planner.step import PlanningStep
from bentoai.shared.http import get_http_client


@lru_cache
def get_gateway() -> CommerceGateway:
    """The one door to external commerce, built once.

    Cached because the providers behind it hold an HTTP client with a
    connection pool. A new gateway per request would open a new pool per
    request.
    """
    settings = get_settings()
    gateway = CommerceGateway()

    gateway.register(
        ShopifyGlobalCatalogProvider(
            endpoint=settings.commerce.shopify_catalog_endpoint,
            agent_profile_url=settings.commerce.shopify_agent_profile_url,
            client=get_http_client(),
            timeout_seconds=settings.commerce.request_timeout_seconds,
        )
    )

    return gateway


def build_orchestrator(session: AsyncSession) -> ShoppingOrchestrator:
    """The workflow, assembled.

    Read the four lines below and you know what this product does: it plans,
    it searches, it compares, it builds a basket - and which state each of
    those happens in.
    """
    gateway = get_gateway()
    settings = get_settings()

    orchestrator = ShoppingOrchestrator(session)

    orchestrator.register(MissionStatus.DRAFT, PlanningStep(session))
    orchestrator.register(MissionStatus.SEARCHING, DiscoveryStep(gateway, settings))
    orchestrator.register(MissionStatus.EVALUATING, EvaluationStep(gateway, settings))

    # Registered at REVIEW and returns REVIEW, so the mission holds where it is.
    # Only one step may register per state, and REVIEW is now taken - so
    # POST /selections and /approve move the mission through
    # apply_customer_decision instead of through a step.
    orchestrator.register(
        MissionStatus.REVIEW, BasketOptimizerStep(session, gateway, settings)
    )

    return orchestrator
