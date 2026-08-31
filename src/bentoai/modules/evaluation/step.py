import logging

from bentoai.config import Settings
from bentoai.modules.commerce.gateway import CommerceGateway
from bentoai.modules.evaluation.service import EvaluationService
from bentoai.modules.orchestration.steps import StepOutcome
from bentoai.modules.planner.models import MissionStatus, ShoppingMission

logger = logging.getLogger(__name__)


class EvaluationStep:
    """Wraps the evaluation half as one workflow step.
"""
    working_status = None

    def __init__(self, gateway: CommerceGateway, settings: Settings) -> None:
        self.gateway = gateway
        self.settings = settings

    async def run(self, mission: ShoppingMission) -> StepOutcome:
        outcome = await EvaluationService(self.gateway, self.settings).run(mission)

        notes = [
            f"{failure.provider} could not be reached: {failure.reason}"
            for failure in outcome.failures
        ]

        if outcome.missing_ids:
            notes.append(
                f"{len(outcome.missing_ids)} of {outcome.requested_count} products "
                "are no longer in the catalog and were left out."
            )

        unranked = outcome.unranked_required
        if unranked:
            notes.append(
                "Nothing suitable was found for: "
                + ", ".join(unranked)
                + ". Change or reword these requirements and search again."
            )

  
        return StepOutcome(
            next_status=MissionStatus.REVIEW,
            event_type="EVALUATION_COMPLETE",
            event_payload={
                "requirement_count": len(outcome.results),
                "ranked_total": sum(len(r.ranked) for r in outcome.results),
                "requested_products": outcome.requested_count,
                "missing_products": len(outcome.missing_ids),
                "provider_failures": len(outcome.failures),
                "unranked_required": unranked,
            },
            notes=notes,
        )