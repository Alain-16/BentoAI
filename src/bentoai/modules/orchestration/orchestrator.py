import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.deterministicService.audit.models import ActorType, AuditEvent
from bentoai.modules.orchestration.steps import WorkflowStep
from bentoai.modules.planner.models import MissionStatus, ShoppingMission
from bentoai.modules.planner.repository import MissionNotFound, MissionRepository
from bentoai.modules.planner.state_machine import assert_can_transition

logger = logging.getLogger(__name__)

class NoStepForState(Exception):

    def __init__(self,status:MissionStatus) -> None:

        super().__init__(f"No workflow step is registered for state {status.value}.")
        self.status = status

class UnexpectedState(Exception):
    
    def __init__(self, expected: MissionStatus, actual: MissionStatus) -> None:
        super().__init__(
            f"Expected the mission to be in {expected.value}, found {actual.value}."
        )
        self.expected = expected
        self.actual = actual


class ShoppingOrchestrator:

    def __init__(self, session:AsyncSession) -> None:
        self.session = session
        self.repo = MissionRepository(session)

        self._steps: dict[MissionStatus, WorkflowStep] = {}

    def register(self,trigger_status:MissionStatus, step:WorkflowStep) -> None:

        if trigger_status in self._steps:
            raise ValueError(f"a step is already registered for {trigger_status}")
        self._steps[trigger_status] = step


    async def advance(self,mission_id:uuid.UUID, user_id:uuid.UUID, expected_from:MissionStatus | None = None) -> tuple[ShoppingMission, list[str]]:

        mission = await self.repo.get_for_user(mission_id,user_id)

        if mission is None:
            raise MissionNotFound(str(mission_id))

        if expected_from is not None and mission.status is not expected_from:
            raise UnexpectedState(expected_from, mission.status)

        step = self._steps.get(mission.status)
        if step is None:
            raise NoStepForState(mission.status)

        started_at = mission.status

        if step.working_status is not None and step.working_status is not mission.status:

            self._move(mission, step.working_status)
            await self.session.flush()

        outcome = await step.run(mission)

        self._move(mission,outcome.next_status)
        self._record(mission, outcome.event_type,outcome.event_payload)

        await self.session.commit()
        await self.session.refresh(mission)

        logger.info(
            "mission_advanced mission_id=%s from=%s to=%s",
            mission.id,
            started_at.value,
            mission.status.value,

        )

        return mission,outcome.notes

    def _move(self,mission:ShoppingMission,target:MissionStatus) -> None:

        assert_can_transition(mission.status, target)
        mission.status = target

    def _record(self,mission:ShoppingMission,event_type:str, payload:dict) -> None:

        self.session.add(
            AuditEvent(
                mission_id=mission.id,
                user_id=mission.user_id,
                actor_type=ActorType.SYSTEM,
                event_type=event_type,
                event_payload=payload,
            )
        )


