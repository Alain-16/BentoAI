from typing import Annotated
from fastapi import Depends
from bentoai.config import Settings, get_settings
from bentoai.shared.database import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession


SettingsDeps = Annotated[Settings, Depends(get_settings)]

DbSession = Annotated[AsyncSession, Depends(get_db_session)]