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
from bentoai.modules.evaluation.schemas import MissionRecommendationsRead, to_schema
from bentoai.modules.evaluation.service import NothingToEvaluate, build_recommendations
from bentoai.modules.orchestration.registry import get_gateway

router = APIRouter(prefix="/missions", tags=["missions"])

@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission(payload: MissionCreate, session:DbSession, user:CurrentUser) -> MissionRead:

    mission = await MissionService(session).create_mission(user.id, payload)
    return MissionRead.model_validate(mission)


@router.post("/{mission_id}/plan", response_model=MissionWithPlan)
async def plan_mission(mission_id:uuid.UUID,orchestrator: OrchestratorDep, user: CurrentUser) -> MissionWithPlan:

    try:
        mission, _ = await orchestrator.advance(mission_id, user.id, expected_from=MissionStatus.DRAFT)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MISSION NOT FOUND")
    except (UnexpectedState, NoStepForState, InvalidTransition) as exc:

        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    return MissionWithPlan.model_validate(mission)

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


@router.post("/{mission_id}/discover", response_model=MissionWithPlan)
async def discover_products(mission_id: uuid.UUID, orchestrator:OrchestratorDep, user: CurrentUser) -> MissionWithPlan:


    try:
        mission, _ = await orchestrator.advance(
            mission_id, user.id, expected_from=MissionStatus.SEARCHING
        )

    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    except (UnexpectedState, NoStepForState, InvalidTransition) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    return MissionWithPlan.model_validate(mission)



@router.get("/{mission_id}/recommendations", response_model=MissionRecommendationsRead)
async def get_recommendations(

    mission_id:uuid.UUID,
    session: DbSession,
    orchestrator: OrchestratorDep,
    user:CurrentUser,

) -> MissionRecommendationsRead:


    notes: list[str] = []

    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mission not found")

    if mission.status is MissionStatus.EVALUATING:
        try:
            mission, notes = await orchestrator.advance(mission_id, user.id, expected_from=MissionStatus.EVALUATING)
        except NothingToEvaluate:
            raise HTTPException(status.HTTP_409_CONFLICT, "Discovery has not run for this mission yet")

        except (UnexpectedState, NoStepForState, InvalidTransition) as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    elif not mission.evaluation_results:
        raise HTTPException(status.HTTP_409_CONFLICT,f"This mission is in {mission.status.value}. Run /discover first." )

    recommendations = await build_recommendations(mission, get_gateway())

    return MissionRecommendationsRead(
        mission_id=mission.id,
        status=mission.status.value,
        requirements=to_schema(recommendations),
        notes=notes
    )
