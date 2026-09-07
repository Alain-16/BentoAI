"""The workflow as a LangGraph.
"""

import logging
import uuid
from typing import TYPE_CHECKING, TypedDict

from langgraph.graph import END, StateGraph

from bentoai.modules.planner.models import MissionStatus

if TYPE_CHECKING:  # pragma: no cover
    from bentoai.modules.orchestration.orchestrator import ShoppingOrchestrator

logger = logging.getLogger(__name__)


class RunState(TypedDict):
    """What travels between nodes. The mission itself stays in the database."""

    mission_id: str
    user_id: str

    # Where the mission is now, and where it was before the last step ran.
    # Equal means the step held, which is how a run ends.
    status: str
    previous: str | None

    has_questions: bool
    steps_run: int
    notes: list[str]


def stop_reason(state: RunState, node_names: set[str], max_steps: int) -> str | None:
    """Why this run should end, or None if it should carry on.

    One function, used by the router to decide and by the caller to report, so
    the reason a run stopped and the decision to stop it can never disagree.
    """
    if state["has_questions"]:
        return "waiting_for_customer"

    # A step ran and left the mission where it started. Running it again would
    # cost the same money for the same answer.
    if state["previous"] is not None and state["status"] == state["previous"]:
        return "held"

    if state["steps_run"] >= max_steps:
        return "step_limit"

    if state["status"] not in node_names:
        return "no_further_step"

    return None


def build_run_graph(orchestrator: "ShoppingOrchestrator", max_steps: int):
    """Compile a graph from whatever steps are registered.


    """
    node_names = {status.value for status in orchestrator.steps}

    def make_node(status: MissionStatus):
        async def node(state: RunState) -> dict:
            # advance() is unchanged - it runs one step, applies the state
            # transition, writes the audit event and commits. The graph decides
            # when to call it, not what it does.
            mission, notes = await orchestrator.advance(
                uuid.UUID(state["mission_id"]),
                uuid.UUID(state["user_id"]),
                expected_from=status,
            )
            return {
                "previous": status.value,
                "status": mission.status.value,
                "has_questions": bool(mission.pending_questions),
                "steps_run": state["steps_run"] + 1,
                "notes": state["notes"] + notes,
            }

        return node

    def route(state: RunState) -> str:
        reason = stop_reason(state, node_names, max_steps)
        if reason is not None:
            logger.info(
                "graph_stop mission_id=%s reason=%s at=%s",
                state["mission_id"],
                reason,
                state["status"],
            )
            return END
        # Otherwise the next node is simply the one registered for the state the
        # mission is now in.
        return state["status"]

    graph = StateGraph(RunState)

    for status in orchestrator.steps:
        graph.add_node(status.value, make_node(status))

    # Where to begin is the same question as where to go next, so the entry
    # point uses the same router. On the first pass "previous" is None, so the
    # held check cannot fire and it simply picks the node for the mission's
    # current state.
    graph.set_conditional_entry_point(route, {**{n: n for n in node_names}, END: END})

    for name in node_names:
        graph.add_conditional_edges(
            name, route, {**{n: n for n in node_names}, END: END}
        )

    return graph.compile()
