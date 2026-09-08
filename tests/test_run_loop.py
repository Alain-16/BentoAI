"""The run loop's stop conditions.

The most expensive thing in the backend to get wrong. A loop that fails to
terminate is not a hang - it is a catalog search and eight model calls, over and
over, billed.

Two steps deliberately do not move the mission: DiscoveryStep holds at SEARCHING
when a required item found nothing, and BasketOptimizerStep returns REVIEW every
time. So the loop cannot stop at "no step registered" - it has to notice that a
step ran and changed nothing.
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from bentoai.modules.orchestration.orchestrator import (
    MAX_STEP_PER_RUN,
    ShoppingOrchestrator,
    StopReason,
)
from bentoai.modules.planner.models import MissionStatus as S


class FakeSession:
    """Enough of a session for the orchestrator to record and commit against.

    Real database work is not what these tests are about - what runs, in what
    order, and when it stops is.
    """

    def add(self, obj):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture
def orchestrator():
    def build(status, next_status, *, registered, questions_after=None):
        o = ShoppingOrchestrator(FakeSession())
        mission = SimpleNamespace(
            id=uuid.uuid4(), user_id=uuid.uuid4(), status=status, pending_questions=[]
        )

        # The step objects are never called - advance is stubbed below. What
        # matters is which states have something registered, because that is
        # what the router reads.
        for state in registered:
            o._steps[state] = object()

        async def get_for_user(mission_id, user_id):
            return mission

        o.repo.get_for_user = get_for_user

        calls = {"n": 0}

        async def advance(mission_id, user_id, expected_from=None):
            calls["n"] += 1
            mission.status = next_status(mission.status)
            if questions_after is not None and calls["n"] == questions_after:
                mission.pending_questions = [{"id": "location", "field": "location"}]
            return mission, [f"note {calls['n']}"]

        o.advance = advance
        return o, mission

    return build


HEALTHY = {
    S.DRAFT: S.SEARCHING,
    S.SEARCHING: S.EVALUATING,
    S.EVALUATING: S.REVIEW,
    # The basket optimizer holds. This is the one that makes a naive loop spin.
    S.REVIEW: S.REVIEW,
}
ALL_STEPS = (S.DRAFT, S.SEARCHING, S.EVALUATING, S.REVIEW)


def run(o, mission):
    return asyncio.run(o.run_until_blocked(mission.id, mission.user_id))


def test_a_healthy_mission_runs_to_review_and_stops(orchestrator):
    o, mission = orchestrator(S.DRAFT, lambda s: HEALTHY[s], registered=ALL_STEPS)

    report = run(o, mission)

    assert report.steps_run == 4
    assert report.status is S.REVIEW
    assert report.stop_reason is StopReason.HELD
    assert len(report.notes) == 4, "every step's notes must be collected"


def test_a_step_that_holds_immediately_runs_once(orchestrator):
    """The basket optimizer at REVIEW. Once, not forever.

    If this ever reads more than 1, the no-progress check is broken and every
    run is rebuilding the basket in a loop.
    """
    o, mission = orchestrator(S.REVIEW, lambda s: S.REVIEW, registered=(S.REVIEW,))

    report = run(o, mission)

    assert report.steps_run == 1
    assert report.stop_reason is StopReason.HELD


def test_a_pending_question_stops_the_run(orchestrator):
    """Carrying on would search and evaluate against information we know is
    missing - a mission with no destination comes back with prices in every
    merchant's own currency and nothing usable."""
    o, mission = orchestrator(
        S.DRAFT, lambda s: HEALTHY[s], registered=ALL_STEPS, questions_after=1
    )

    report = run(o, mission)

    assert report.steps_run == 1
    assert report.stop_reason is StopReason.WAITING_FOR_CUSTOMER


def test_a_mission_already_blocked_runs_nothing(orchestrator):
    o, mission = orchestrator(S.SEARCHING, lambda s: s, registered=(S.SEARCHING,))
    mission.pending_questions = [{"id": "location"}]

    report = run(o, mission)

    assert report.steps_run == 0
    assert report.stop_reason is StopReason.WAITING_FOR_CUSTOMER


def test_a_state_with_no_step_ends_the_run(orchestrator):
    o, mission = orchestrator(S.COMPLETE, lambda s: s, registered=(S.DRAFT,))

    report = run(o, mission)

    assert report.steps_run == 0
    assert report.stop_reason is StopReason.NO_FURTHER_STEP


def test_a_cycle_is_stopped_by_the_step_limit(orchestrator):
    """Nothing in the state machine allows this today. The limit exists so that
    if something ever does, it costs twelve steps rather than an afternoon."""
    flip = {S.SEARCHING: S.EVALUATING, S.EVALUATING: S.SEARCHING}
    o, mission = orchestrator(
        S.SEARCHING, lambda s: flip[s], registered=(S.SEARCHING, S.EVALUATING)
    )

    report = run(o, mission)

    assert report.steps_run == MAX_STEP_PER_RUN
    assert report.stop_reason is StopReason.STEP_LIMIT
