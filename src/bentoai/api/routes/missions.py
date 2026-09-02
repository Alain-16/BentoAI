"""Mission endpoints (§9.2).

These expose product operations. There is no /planner-agent route — agents are
implementation details behind the mission workflow, and §9.2 says the public API
represents product capabilities rather than internal components.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from bentoai.modules.deterministicService.basket.schemas import MissionBasketRead
from bentoai.modules.deterministicService.basket.schemas import to_schema as basket_to_schema
from bentoai.modules.deterministicService.basket.schemas import SelectionIn
from bentoai.modules.deterministicService.basket.service import NothingToOptimize, build_basket_view
from bentoai.modules.deterministicService.basket.smart_basket import (
    ensure_basket,
    select_product,
)
from bentoai.modules.deterministicService.audit.service import describe, recent_for_mission
from bentoai.api.deps import CurrentUser, DbSession, OrchestratorDep
from bentoai.modules.orchestration.orchestrator import NoStepForState, UnexpectedState
from bentoai.modules.planner.models import BasketStatus, MissionStatus
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

    view = await build_basket_view(session, mission, get_gateway())

    schema = basket_to_schema(mission, view)
    schema.notes = notes + schema.notes
    return schema
        

@router.post("/{mission_id}/selections", response_model=MissionBasketRead)
async def select_basket_product(
    mission_id: uuid.UUID,
    payload: SelectionIn,
    session: DbSession,
    user: CurrentUser,
) -> MissionBasketRead:
    """Choose a product for one requirement. This is both Keep and Swap.

    The product has to be one of the options already offered for that
    requirement. That is not fussiness - the pool is what survived the hard
    filter and was priced, so anything outside it has not been checked against
    the budget, the destination or availability, and putting it in a basket
    would skip every one of those.
    """
    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")

    if not mission.basket_options:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "There is no basket to change yet. Open /basket first.",
        )

    view = await build_basket_view(session, mission, get_gateway())

    group = next(
        (g for g in view.get("groups", []) if g["requirement"].id == payload.requirement_id),
        None,
    )
    if group is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "That requirement is not part of this mission."
        )

    entry = next(
        (
            option
            for option in group["options"]
            if option["candidate"].source_product_id == payload.product_id
        ),
        None,
    )
    if entry is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "That product is not one of the options for this requirement.",
        )

    await select_product(
        session,
        mission,
        group["requirement"],
        entry["candidate"],
        entry["offer"],
        by="customer",
    )
    await session.commit()
    await session.refresh(mission)

    # Rebuilt rather than patched. The totals, the "you changed this" marker and
    # the price comparison all follow from the selection, and deriving them a
    # second way here would be the same logic in two places waiting to disagree.
    view = await build_basket_view(session, mission, get_gateway())
    return basket_to_schema(mission, view)


@router.post("/{mission_id}/approve", response_model=MissionBasketRead)
async def approve_basket(
    mission_id: uuid.UUID,
    session: DbSession,
    orchestrator: OrchestratorDep,
    user: CurrentUser,
) -> MissionBasketRead:
    """Accept the basket, moving the mission to BASKET_READY.

    This does not buy anything and it does not charge anybody. Checkout is a
    later phase (§12.3 V4); what this does is mark the basket as the one the
    customer has settled on, which is what §3.3 means by REVIEW -> BASKET_READY.
    The screen says exactly that, because a button that sounds like it spends
    money and does not is worse than no button.

    Prices are re-checked here rather than trusted. §5.11 is explicit that a
    stale price must not reach checkout, and this is the last point before it
    would.
    """
    try:
        mission = await MissionService(session).get_mission(mission_id, user.id)
    except MissionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")

    if mission.status is not MissionStatus.REVIEW:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This mission is in {mission.status.value}, so there is nothing to approve.",
        )

    # A fresh look, not the numbers from whenever the page was opened.
    view = await build_basket_view(session, mission, get_gateway())

    if not view or not view.get("item_count"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "There is nothing in this basket to approve."
        )

    if view.get("blockers"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Some items cannot be bought right now. Resolve them before approving.",
        )

    basket = await ensure_basket(session, mission)
    basket.status = BasketStatus.APPROVED

    try:
        await orchestrator.apply_customer_decision(
            mission,
            MissionStatus.BASKET_READY,
            "BASKET_APPROVED",
            {
                "total": str(view["total"]),
                "item_count": view["item_count"],
                "merchant_count": view["merchant_count"],
            },
        )
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    return basket_to_schema(mission, view)
