import logging

from bentoai.config import Settings
from bentoai.modules.commerce.gateway import CommerceGateway
from bentoai.modules.discovery.service import DiscoveryService
from bentoai.modules.orchestration.steps import StepOutcome
from bentoai.modules.planner.models import MissionStatus, ShoppingMission

logger = logging.getLogger(__name__)


class DiscoveryStep:

    working_status = None

    def __init__(self, gateway: CommerceGateway, settings:Settings) -> None:

        self.gateway=gateway
        self.settings=settings


    async def run(self,mission: ShoppingMission) -> StepOutcome:
        outcome = await DiscoveryService(self.gateway, self.settings).run(mission)

        notes = [
            f"{failure.provider} could not be searched: {failure.reason}"

            for failure in outcome.failures
        ]

        return StepOutcome(
            next_status=MissionStatus.EVALUATING,
            event_type="DISCOVERY_COMPLETE",
            event_payload={
                "requirement_count": outcome.requirement_count,
                "candidate_count": outcome.candidate_count,
                "provider_failures": len(outcome.failures),
            },
            notes=notes,
        )

    
