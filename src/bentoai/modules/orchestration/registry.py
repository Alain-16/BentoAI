from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.orchestration.orchestrator import ShoppingOrchestrator
from bentoai.modules.planner.models import MissionStatus
from bentoai.modules.planner.step import PlanningStep
from bentoai.modules.discovery.step import DiscoveryStep
from bentoai.modules.evaluation.step import EvaluationStep
from functools import lru_cache
from bentoai.modules.commerce.gateway import CommerceGateway
from bentoai.modules.commerce.providers.shopify_global import ShopifyGlobalCatalogProvider
from bentoai.config.settings import get_settings
from bentoai.shared.http import get_http_client
from bentoai.modules.deterministicService.basket.step import BasketOptimizerStep

@lru_cache
def get_gateway() -> CommerceGateway:

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


def build_orchestrator(session:AsyncSession) -> ShoppingOrchestrator:

    gateway = get_gateway()
    settings = get_settings()

    orchestrator = ShoppingOrchestrator(session)

    orchestrator.register(MissionStatus.DRAFT, PlanningStep(session))

    orchestrator.register(MissionStatus.SEARCHING, DiscoveryStep(gateway, settings))

    orchestrator.register(MissionStatus.EVALUATING, EvaluationStep(gateway, settings))

    orchestrator.register(MissionStatus.REVIEW, BasketOptimizerStep(gateway, settings))


    return orchestrator