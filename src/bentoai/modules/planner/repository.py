import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bentoai.modules.planner.models import MissionRequirement, ShoppingMission



class MissionNotFound(Exception):
     """No mission with that id belongs to this user.

    Lives here rather than in the service or the orchestrator because both of
    them need it, and both already import this module.
    """


class MissionRepository:

    def __init__(self,session:AsyncSession) -> None:
          self.session = session

    async def add(self,mission:ShoppingMission) -> ShoppingMission:

        self.session.add(mission)

        await self.session.flush()
        return mission

    async def get_for_user(self,mission_id: uuid.UUID, user_id:uuid.UUID) -> ShoppingMission | None:

         stmt = (
              select(ShoppingMission).where(
                   ShoppingMission.id == mission_id,
                   ShoppingMission.user_id == user_id,
              )
              .options(selectinload(ShoppingMission.requirements))
         )
         return await self.session.scalar(stmt)

    async def replace_requirements(self, mission:ShoppingMission, requirements:list[MissionRequirement]) -> None:

         mission.requirements.clear()
         mission.requirements.extend(requirements)
         await self.session.flush()
         
         