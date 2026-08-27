from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from functools import lru_cache
from sqlalchemy.ext.asyncio import (
    AsyncEngine,AsyncSession,async_sessionmaker,create_async_engine,
)
from collections.abc import AsyncGenerator

from bentoai.config.settings import get_settings

NAMING_CONVENTION = {
    # An index — makes looking up rows by this column fast.
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    # A uniqueness rule — no two rows may share this value.
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # A check rule — the value has to satisfy some condition.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    # A link to a row in another table.
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    # The column that identifies each row uniquely.
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):

    metadata = MetaData(naming_convention=NAMING_CONVENTION)



@lru_cache
def get_engine() -> AsyncEngine:

    settings = get_settings()

    return create_async_engine(
        settings.db.url_str,

        echo=settings.db.echo,

        pool_size = settings.db.pool_size,

        max_overflow=settings.db.max_overflow,

        pool_pre_ping = settings.db.pool_pre_ping,
    )

@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:

    return async_sessionmaker(
        bind=get_engine(),

        expire_on_commit=False,
    )

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            yield session
        except Exception:
     
            raise