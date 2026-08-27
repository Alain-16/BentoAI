import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.orchestration.steps import StepOutcome
from bentoai.modules.planner import agent
from bentoai.modules.planner.contracts import PlanningRequest, PlanningResult
from bentoai.modules.planner.models import (
    MissionRequirement,
    MissionStatus,
    RequirementPriority,
    ShoppingMission,
)

logger = logging.getLogger(__name__)

class PlanningStep:
    """Runs the Planning Agent and turns its answer into stored requirements."""

    # The mission sits in PLANNING while this runs and lands in SEARCHING when it
    # finishes, matching the path DRAFT -> PLANNING -> SEARCHING in §3.3.
    working_status = MissionStatus.PLANNING

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, mission: ShoppingMission) -> StepOutcome:
        result = await agent.run_planning(
            PlanningRequest(
                goal=mission.goal,
                budget_amount=mission.budget_amount,
                budget_currency=mission.budget_currency,
                location=mission.location,
            )
        )

        self._apply(mission, result)

        return StepOutcome(
            next_status=MissionStatus.SEARCHING,
            event_type="PLAN_GENERATED",
            event_payload={
                "requirement_count": len(result.requirements),
                "rationale": result.rationale,
            },
            notes=result.missing_information,
        )

    def _apply(self, mission: ShoppingMission, result: PlanningResult) -> None:
        """Write the agent's answer onto the mission.

        Nothing the model returned is trusted with money. Budget allocations are
        checked against the real budget here, in ordinary code, because an LLM is
        never the authority on financial figures (Principle 5) — including ones
        it only suggested.
        """
        mission.goal = result.goal

        # Stored as JSON on the mission, which is what §8.3 prescribes for
        # constraints and preferences: variable in shape, never joined against,
        # and always read and written alongside the mission itself.
        mission.constraints = {
            "items": [c.model_dump(mode="json") for c in result.constraints]
        }
        mission.preferences = {
            "items": [p.model_dump(mode="json") for p in result.preferences]
        }
        mission.planning_metadata = {
            "rationale": result.rationale,
            "missing_information": result.missing_information,
        }

        budget = mission.budget_amount
        requirements: list[MissionRequirement] = []

        for position, planned in enumerate(result.requirements):
            allocation: Decimal | None = None

            if planned.suggested_budget_allocation is not None:
                # Convert through str, not float. Decimal(0.1) inherits the tiny
                # error a float already carries; Decimal("0.1") does not.
                allocation = Decimal(str(planned.suggested_budget_allocation))

                # A suggestion larger than the whole budget is nonsense, so drop
                # it rather than store a figure that would mislead the filter.
                if budget is not None and allocation > budget:
                    logger.warning(
                        "Discarding allocation %s for %r — exceeds budget %s",
                        allocation,
                        planned.category,
                        budget,
                    )
                    allocation = None

            requirements.append(
                MissionRequirement(
                    category=planned.category,
                    description=planned.description,
                    priority=RequirementPriority(planned.priority.value),
                    # The order the agent returned them in, kept so the plan reads
                    # the same way every time it is loaded.
                    position=position,
                    budget_allocation=allocation,
                    attributes={},
                )
            )

        mission.requirements.clear()
        mission.requirements.extend(requirements)