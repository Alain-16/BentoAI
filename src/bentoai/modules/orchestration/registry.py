from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.orchestration.orchestrator import ShoppingOrchestrator
from bentoai.modules.planner.models import MissionStatus
from bentoai.modules.planner.step import PlanningStep


def build_orchestrator(session:AsyncSession) -> ShoppingOrchestrator:

    orchestrator = ShoppingOrchestrator(session)

    orchestrator.register(MissionStatus.DRAFT, PlanningStep(session))


    return orchestrator