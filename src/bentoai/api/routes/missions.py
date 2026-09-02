"""Mission endpoints (§9.2).

These expose product operations. There is no /planner-agent route — agents are
implementation details behind the mission workflow, and §9.2 says the public API
represents product capabilities rather than internal components.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from bentoai.modules.deterministicService.basket.schemas import MissionBasketRead
from bentoai.modules.deterministicService.basket.schemas import to_schema as basket_to_schema
from bentoai.modules.deterministicService.basket.service import NothingToOptimize, build_basket_view
from bentoai.modules.deterministicService.audit.service import describe, recent_for_mission
from bentoai.api.deps import CurrentUser, DbSession, OrchestratorDep
from bentoai.modules.orchestration.orchestrator import NoStepForState, UnexpectedState
from bentoai.modules.planner.models import MissionStatus
from bentoai.modules.planner.repository import MissionNotFound
from bentoai.modules.planner.schemas import (
    MissionCreate,
    MissionRead,
    MissionWithPlan,
    RequirementRead,
    ActivityEventRead,
    AnswerSubmission,
    MissionRunRead
)
from bentoai.modules.planner.service import MissionService
from bentoai.modules.planner.state_machine import InvalidTransition
from bentoai.modules.evaluation.schemas import MissionRecommendationsRead, to_schema
from bentoai.modules.evaluation.service import NothingToEvaluate, build_recommendations
from bentoai.modules.orchestration.registry import get_gateway
from bentoai.modules.orchestration import runner
from bentoai.modules.deterministicService.audit.models import ActorType,AuditEvent

router = APIRouter(prefix="/missions", tags=["missions"])

@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission(payload: MissionCreate, session:DbSession, user:CurrentUser) -> MissionRead:

    mission = await MissionService(session).create_mission(user.id, payload)
    return MissionRead.model_validate(mission)

@router.post("/{mission_id}/run", response_model=MissionRunRead, status_code=status.HTTP_202_ACCEPTED)
async def run_mission(mission_id:uuid.UUID, session:DbSession, user:CurrentUser) -> MissionRunRead:

    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mission not found")

    started = runner.start_run(mission.id,user.id)

    return MissionRunRead(
        mission_id=mission.id,
        status=mission.status,
        started=started,
        pending_questions=mission.pending_questions or [],
    )

@router.get("/{mission_id}/activity", response_model=list[ActivityEventRead])
async def get_activity(
    mission_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[ActivityEventRead]:
    
    try:
        await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")

    events = await recent_for_mission(session, mission_id)

    activity: list[ActivityEventRead] = []
    for event in events:
        title, detail = describe(event)
        activity.append(
            ActivityEventRead(
                id=event.id,
                at=event.created_at,
                event_type=event.event_type,
                title=title,
                detail=detail,
                notes=(event.event_payload or {}).get("notes") or [],
            )
        )

    return activity   

@router.post("/{mission_id}/answers", response_model=MissionWithPlan)
async def answer_questions(
    mission_id: uuid.UUID,
    payload: AnswerSubmission,
    session: DbSession,
    user: CurrentUser,
) -> MissionWithPlan:

    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")

    if not mission.pending_questions:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This mission is not waiting on anything."
        )

    answered: list[str] = []

    if payload.location:
        mission.location = payload.location
        answered.append("location")

    if payload.budget_amount is not None:
        mission.budget_amount = payload.budget_amount
        answered.append("budget_amount")

    if payload.budget_currency:
        mission.budget_currency = payload.budget_currency.upper()

    if not answered:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "None of the pending questions were answered."
        )

    mission.pending_questions = [
        question
        for question in mission.pending_questions
        if question.get("field") not in answered
    ]

    session.add(
        AuditEvent(
            mission_id=mission.id,
            user_id=user.id,
            actor_type=ActorType.USER,
            event_type="QUESTIONS_ANSWERED",
            event_payload={"answered": answered},
        )
    )

    await session.commit()
    await session.refresh(mission)

    if not mission.pending_questions:
        runner.start_run(mission.id, user.id)

    return MissionWithPlan.model_validate(mission)


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


@router.get("/{mission_id}/basket", response_model=MissionBasketRead)
async def get_basket(
    mission_id: uuid.UUID,
    session: DbSession,
    orchestrator: OrchestratorDep,
    user:CurrentUser,
) -> MissionBasketRead:

    notes: list[str] = []

    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mission not found")

    if mission.status is MissionStatus.REVIEW and not mission.basket_options:
        try:
            mission, notes = await orchestrator.advance(
                mission_id, user.id, expected_from=MissionStatus.REVIEW
            )
        except NothingToOptimize as exc:
            if exc.reason == NothingToOptimize.NO_PRODUCTS:
                # Sending them back to /recommendations here would be wrong -
                # it already ran, and running it again gives the same answer.
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Evaluation found no usable products for this mission - "
                    "every candidate was rejected. See the rejection reasons "
                    "in /recommendations; a missing location is the usual cause.",
                )
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This mission has not been evaluated yet. "
                "Call /recommendations first.",
            )
        except (UnexpectedState, NoStepForState, InvalidTransition) as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    elif not mission.basket_options:
        raise HTTPException(
            status.HTTP_409_CONFLICT, 
            f"This mission is in {mission.status.value}. "
            "Run /discover and /recommendations first.",
        )

    view = await build_basket_view(mission, get_gateway())

    schema = basket_to_schema(mission, view)
    schema.notes = notes + schema.notes
    return schema
        