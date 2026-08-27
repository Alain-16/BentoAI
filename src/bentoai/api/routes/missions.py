"""Mission endpoints (§9.2).

These expose product operations. There is no /planner-agent route — agents are
implementation details behind the mission workflow, and §9.2 says the public API
represents product capabilities rather than internal components.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from bentoai.api.deps import CurrentUser, DbSession, OrchestratorDep
from bentoai.modules.orchestration.orchestrator import NoStepForState, UnexpectedState
from bentoai.modules.planner.models import MissionStatus
from bentoai.modules.planner.repository import MissionNotFound
from bentoai.modules.planner.schemas import (
    MissionCreate,
    MissionRead,
    MissionWithPlan,
    RequirementRead,
)
from bentoai.modules.planner.service import MissionService
from bentoai.modules.planner.state_machine import InvalidTransition

router = APIRouter(prefix="/missions", tags=["missions"])

@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission(payload: MissionCreate, session:DbSession, user:CurrentUser) -> MissionRead:

    mission = await MissionService(session).create_mission(user.id, payload)
    return MissionRead.model_validate(mission)


@router.post("/{mission_id}/plan", response_model=MissionWithPlan)
async def plan_mission(mission_id:uuid.UUID,orchestrator: OrchestratorDep, user: CurrentUser) -> MissionWithPlan:

    try:
        mission, questions = await orchestrator.advance(mission_id, user.id, expected_from=MissionStatus.DRAFT)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MISSION NOT FOUND")
    except (UnexpectedState, NoStepForState, InvalidTransition) as exc:

        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    response = MissionWithPlan.model_validate(mission)
    response.missing_information = questions

    return response

@router.get("/{mission_id}", response_model=MissionWithPlan)
async def get_mission(
    mission_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> MissionWithPlan:
    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return MissionWithPlan.model_validate(mission)


@router.get("/{mission_id}/requirements", response_model=list[RequirementRead])
async def get_requirements(
    mission_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[RequirementRead]:
    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return [RequirementRead.model_validate(r) for r in mission.requirements]