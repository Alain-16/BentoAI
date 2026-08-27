from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bentoai.config import Settings, get_settings
from bentoai.modules.deterministicService.users.models import User
from bentoai.modules.orchestration.orchestrator import ShoppingOrchestrator
from bentoai.modules.orchestration.registry import build_orchestrator
from bentoai.shared.database import get_db_session

SettingsDeps = Annotated[Settings, Depends(get_settings)]

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

DEV_USER_EMAIL="dev@bentoai.local"

async def get_current_user(session: DbSession) -> User:
    """Return the development user, creating it the first time it is asked for."""
    user = await session.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

def get_orchestrator(session: DbSession) -> ShoppingOrchestrator:
    return build_orchestrator(session)

OrchestratorDep = Annotated[ShoppingOrchestrator, Depends(get_orchestrator)]
