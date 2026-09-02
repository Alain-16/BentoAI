import logging

from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.config import Settings
from bentoai.modules.deterministicService.basket.service import BasketOptimizerService
from bentoai.modules.commerce.gateway import CommerceGateway
from bentoai.modules.orchestration.steps import StepOutcome
from bentoai.modules.planner.models import MissionStatus, ShoppingMission

logger = logging.getLogger(__name__)


class BasketOptimizerStep:

    working_status = None

    def __init__(
        self, session: AsyncSession, gateway: CommerceGateway, settings: Settings
    ) -> None:
        # Taken explicitly, the way PlanningStep does it, rather than reached
        # for through the mission. The step writes basket rows now, and a
        # session it was handed is easier to follow than one it went looking
        # for.
        self.session = session
        self.gateway = gateway
        self.settings = settings

    async def run(self,mission:ShoppingMission) -> StepOutcome:
        outcome = await BasketOptimizerService(
            self.session, self.gateway, self.settings
        ).run(mission)
        solution = outcome.solution

        notes= list(solution.notes)

        if not solution.feasible:
            notes.insert(0, "No basket fits this budget")

        return StepOutcome(
            next_status=MissionStatus.REVIEW,
            event_type="BASKET_OPTIMIZED",
            event_payload={
                "requirement_count": len(outcome.pool),
                "option_count": sum(len(r.options) for r in outcome.pool),
                "selected_count": len(solution.selected),
                "total": str(solution.total),
                "remaining": str(solution.remaining) if solution.remaining is not None else None,
                "feasible": solution.feasible,
            },
            notes=notes,
        )