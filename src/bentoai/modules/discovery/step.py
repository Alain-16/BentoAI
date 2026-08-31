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

        if outcome.unmet_optional:
            notes.append(
                "Nothing found for these optional items:" + ", ".join(outcome.unmet_optional)
            )

        if outcome.unmet_required:
            notes.append(
                "No products found for these required items: " + ", ".join(outcome.unmet_required)
                + ". Try /discover again or reword the requirement."
            )
            next_status = MissionStatus.SEARCHING
        else:
            next_status = MissionStatus.EVALUATING

        return StepOutcome(
            next_status=next_status,
            event_type="DISCOVERY_COMPLETE",
            event_payload={
                "requirement_count": outcome.requirement_count,
                "candidate_count": outcome.candidate_count,
                "provider_failures": len(outcome.failures),
                "unmet_required": outcome.unmet_required,
                "unmet_optional": outcome.unmet_optional,
            },
            notes=notes,
        )

    
