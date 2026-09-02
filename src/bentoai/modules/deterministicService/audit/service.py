import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.deterministicService.audit.models import AuditEvent


async def recent_for_mission(
    session: AsyncSession, mission_id: uuid.UUID, limit: int = 200
) -> list[AuditEvent]:
    """Every event for one mission, oldest first.

    """
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.mission_id == mission_id)
        .order_by(AuditEvent.created_at)
        .limit(limit)
    )
    return list(await session.scalars(stmt))


def describe(event: AuditEvent) -> tuple[str, str]:
    """Turn one stored event into a headline and a supporting line.

    """
    payload = event.event_payload or {}

    if event.event_type == "MISSION_CREATED":
        return "Mission created", str(payload.get("goal") or "")

    if event.event_type == "PLAN_GENERATED":
        count = payload.get("requirement_count") or 0
        detail = f"{count} things to buy" if count else ""
        return "Built your shopping plan", detail

    if event.event_type == "DISCOVERY_COMPLETE":
        found = payload.get("candidate_count") or 0
        categories = payload.get("requirement_count") or 0
        return (
            "Searched available catalogues",
            f"Found {found} products across {categories} categories",
        )

    if event.event_type == "EVALUATION_COMPLETE":
        ranked = payload.get("ranked_total") or 0
        categories = payload.get("requirement_count") or 0
        missing = payload.get("missing_products") or 0

        detail = f"Ranked {ranked} products across {categories} categories"
        if missing:
            detail += f"; {missing} were no longer in the catalogue"
        return "Compared and ranked products", detail

    if event.event_type == "BASKET_OPTIMIZED":
        total = payload.get("total")
        selected = payload.get("selected_count") or 0
        if payload.get("feasible") is False:
            return "Could not fit your plan in the budget", "See the options above"
        return (
            "Built your basket",
            f"{selected} items, {total}" if total else f"{selected} items",
        )

    if event.event_type == "RUN_FINISHED":
        reason = payload.get("stop_reason")
        if reason == "waiting_for_customer":
            return "Waiting on you", "Answer the question above to carry on"
        if reason == "held":
            return "Paused", "Nothing moved on the last step"
        return "Finished for now", ""

    if event.event_type == "RUN_FAILED":
        # The technical detail is kept in the payload for us; what is shown says
        # what it means for the customer (§10.2 rule 5).
        return "Something went wrong", "The run stopped early. Try again."

    if event.event_type == "QUESTIONS_ANSWERED":
        answered = payload.get("answered") or []
        return "Thanks - carrying on", ", ".join(answered)

    # An event type nobody has written phrasing for yet. Showing the raw name is
    # ugly but honest, and it makes the omission obvious rather than hiding it.
    return event.event_type.replace("_", " ").capitalize(), ""