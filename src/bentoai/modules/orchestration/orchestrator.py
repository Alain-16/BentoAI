import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.deterministicService.audit.models import ActorType, AuditEvent
from bentoai.modules.orchestration.steps import WorkflowStep
from bentoai.modules.planner.models import MissionStatus, ShoppingMission
from bentoai.modules.planner.repository import MissionNotFound, MissionRepository
from bentoai.modules.planner.state_machine import assert_can_transition
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_STEP_PER_RUN = 12

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

class StopReason(str, Enum):

    WAITING_FOR_CUSTOMER = "waiting_for_customer"

    HELD = "held"

    NO_FURTHER_STEP= "no_further_step"

    STEP_LIMIT = "step_limit"

    FAILED= "failed"

@dataclass
class RunReport:

    mission_id:uuid.UUID
    status:MissionStatus
    stop_reason:StopReason
    steps_run: int = 0
    notes: list[str] = field(default_factory=list)
    error: str | None = None





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

        mission.pending_questions = list(outcome.questions)

        self._record(mission, outcome.event_type,{**outcome.event_payload, "notes": outcome.notes})

        await self.session.commit()
        await self.session.refresh(mission)

        logger.info(
            "mission_advanced mission_id=%s from=%s to=%s",
            mission.id,
            started_at.value,
            mission.status.value,

        )

        return mission,outcome.notes

    async def run_until_blocked(self,mission_id:uuid.UUID, user_id: uuid.UUID) -> RunReport:

        mission = await self.repo.get_for_user(mission_id, user_id)
        if mission is None:
            raise MissionNotFound(str(mission_id))

        notes: list[str] = []
        steps_run = 0

        while True:

            if mission.pending_questions:
                reason= StopReason.WAITING_FOR_CUSTOMER
                break

            if mission.status not in self._steps:
                reason= StopReason.NO_FURTHER_STEP
                break

            if steps_run >= MAX_STEP_PER_RUN:
                reason = StopReason.STEP_LIMIT
                break

            before = mission.status
            mission, step_notes = await self.advance(mission_id, user_id, expected_from=before)

            notes.extend(step_notes)
            steps_run+=1

            if mission.status is before:
                reason = StopReason.HELD
                break

        report = RunReport(
            mission_id=mission_id,
            status=mission.status,
            stop_reason=reason,
            steps_run=steps_run,
            notes=notes,
        )

        self._record(
            mission,
            "RUN_FINISHED",
            {
                "stop_reason": reason.value,
                "steps_run": steps_run,
                "status": mission.status.value,
                "questions": len(mission.pending_questions or []),

            },
        )

        await self.session.commit()

        logger.info(
            "mission_run_finished mission_id=%s status=%s steps=%s reason=%s",
            mission.id,
            mission.status.value,
            steps_run,
            reason.value,
        )
        return report

    def _move(self,mission:ShoppingMission,target:MissionStatus) -> None:

        if target is mission.status:
            logger.info("mission_holding mission_id=%s at=%s", mission.id, target.value)
            return

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


