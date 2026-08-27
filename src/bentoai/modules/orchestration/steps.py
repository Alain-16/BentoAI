from dataclasses import dataclass, field

from typing import Protocol
from bentoai.modules.planner.models import MissionStatus, ShoppingMission



@dataclass(frozen=True)
class StepOutcome:

    next_status: MissionStatus

    event_type: str
    event_payload: dict = field(default_factory=dict)

    notes: list[str] = field(default_factory=list)


class WorkflowStep(Protocol):

    working_status: MissionStatus | None

    async def run(self,mission: ShoppingMission) -> StepOutcome:
        ...
