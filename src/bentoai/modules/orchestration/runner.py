import asyncio
import logging
import uuid

from bentoai.modules.deterministicService.audit.models import AuditEvent, ActorType
from bentoai.modules.orchestration.registry import build_orchestrator
from bentoai.shared.database import get_session_factory


logger = logging.getLogger(__name__)


_running: set[uuid.UUID] = set()

_tasks: set[asyncio.Task]= set()


def is_running(mission_id:uuid.UUID) -> bool:
    return mission_id in _running

def start_run(mission_id:uuid.UUID, user_id:uuid.UUID) -> bool:

    if mission_id in _running:
        logger.info("run_alredy_in_flight mission_id=%s", mission_id)
        return False

    _running.add(mission_id)

    task = asyncio.create_task(_run(mission_id,user_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return True


async def _run(mission_id:uuid.UUID, user_id:uuid.UUID) -> None:
    session_factory = get_session_factory()

    try:

        async with session_factory() as session:
            orchestrator = build_orchestrator(session)
            await orchestrator.run_until_blocked(mission_id, user_id)

    except Exception as exc:
        logger.exception("mission_run_failed mission_id=%s", mission_id)
        await _record_failure(mission_id, user_id, exc)

    finally:
        _running.discard(mission_id)


async def _record_failure(mission_id:uuid.UUID, user_id:uuid.UUID, exc: Exception) -> None:
    try:
        async with get_session_factory()() as session:
            session.add(
                AuditEvent(
                    mission_id=mission_id,
                    user_id=user_id,
                    actor_type=ActorType.SYSTEM,
                    event_type="RUN_FAILED",
                    event_payload={
                        "error": type(exc).__name__,
                        "detail": str(exc)[:500],
                    },
                )
            )
            await session.commit()
    except Exception:  # pragma: no cover
        logger.exception("Could not record the failure for mission %s", mission_id)

        
