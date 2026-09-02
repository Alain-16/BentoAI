import logging

from bentoai.config import Settings
from bentoai.modules.deterministicService.basket.service import BasketOptimizerService
from bentoai.modules.commerce.gateway import CommerceGateway
from bentoai.modules.orchestration.steps import StepOutcome
from bentoai.modules.planner.models import MissionStatus, ShoppingMission

logger = logging.getLogger(__name__)


class BasketOptimizerStep:

    working_status = None

    def __init__(self, gateway:CommerceGateway,settings:Settings) -> None:
        self.gateway=gateway
        self.settings=settings

    async def run(self,mission:ShoppingMission) -> StepOutcome:
        outcome = await BasketOptimizerService(self.gateway, self.settings).run(mission)
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