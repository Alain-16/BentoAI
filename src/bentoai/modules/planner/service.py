"""Creating and reading shopping missions.

"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.modules.deterministicService.audit.models import ActorType, AuditEvent
from bentoai.modules.planner.models import MissionStatus, ShoppingMission
from bentoai.modules.planner.repository import MissionNotFound, MissionRepository
from bentoai.modules.planner.schemas import MissionCreate


logger = logging.getLogger(__name__)


class MissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MissionRepository(session)

    async def create_mission(
        self, user_id: uuid.UUID, payload: MissionCreate
    ) -> ShoppingMission:
        
        mission = ShoppingMission(
            user_id=user_id,
            status=MissionStatus.DRAFT,
            goal=payload.goal,
            budget_amount=payload.budget_amount,
            budget_currency=payload.budget_currency,
            location=payload.location,
        )
        await self.repo.add(mission)

        self.session.add(
            AuditEvent(
                mission_id=mission.id,
                user_id=user_id,
                actor_type=ActorType.USER,
                event_type="MISSION_CREATED",
                event_payload={"goal": payload.goal},
            )
        )

        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def get_mission(
        self, mission_id: uuid.UUID, user_id: uuid.UUID
    ) -> ShoppingMission:
        
        mission = await self.repo.get_for_user(mission_id, user_id)
        if mission is None:
            raise MissionNotFound(str(mission_id))
        return mission