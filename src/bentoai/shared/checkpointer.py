"""Durable history for LangGraph runs.

Owns a Postgres connection pool, which is why it sits beside database.py rather
than inside the graph: the graph describes a workflow, this holds a resource
with a lifetime.

WHY A SECOND DRIVER

The application talks to Postgres through asyncpg. LangGraph's checkpointer
speaks psycopg3 and nothing else. So there are two drivers and two pools against
the same database. That is the price of this feature, and it is worth knowing
rather than discovering.

WHAT IT IS AND IS NOT FOR

It is not how a mission resumes. A mission resumes because every step commits
before the next one starts, so mission.status already says where things got to -
call /run again and it carries on from there, checkpointer or not.

What this adds is a record of the graph's own execution per mission: which nodes
ran, in what order, with what state between them. That is what makes a stalled
run inspectable after the fact instead of guessable.
"""

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from bentoai.config import get_settings

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_saver: AsyncPostgresSaver | None = None


def _psycopg_dsn() -> str:
    """Turn the SQLAlchemy URL into one psycopg understands.

    SQLAlchemy writes the driver into the scheme - postgresql+asyncpg://... -
    because it needs to know which driver to load. psycopg wants a plain
    postgresql:// URL and rejects the rest. Same database, same credentials,
    different spelling.
    """
    return get_settings().db.url_str.replace("postgresql+asyncpg://", "postgresql://", 1)


async def get_checkpointer() -> AsyncPostgresSaver:
    """The shared checkpointer, opened and prepared on first use.

    Built once because it holds a pool. setup() creates the tables LangGraph
    needs - note those are created here rather than by Alembic, so they will not
    appear in the migration history. That is LangGraph's schema to manage, and
    letting two systems own the same tables is worse than the inconsistency.
    """
    global _pool, _saver

    if _saver is not None:
        return _saver

    _pool = AsyncConnectionPool(
        conninfo=_psycopg_dsn(),
        max_size=5,
        # Rows come back as dictionaries and statements are not prepared -
        # both are what AsyncPostgresSaver expects, and it fails in confusing
        # ways without them.
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": None},
        open=False,
    )
    await _pool.open()

    _saver = AsyncPostgresSaver(_pool)
    await _saver.setup()

    logger.info("langgraph_checkpointer_ready")
    return _saver


async def close_checkpointer() -> None:
    """Shut the pool down. Called when the application stops."""
    global _pool, _saver

    if _pool is not None:
        await _pool.close()

    _pool = None
    _saver = None
