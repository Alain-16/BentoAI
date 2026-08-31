import logging

from bentoai.modules.discovery.contracts import DiscoveryPlan
from bentoai.modules.planner.models import MissionRequirement, ShoppingMission
from bentoai.shared.llm import generate_structured

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """ \
You write product search queries. You are given a customer's shopping mission \
and the list of things it needs, and you return the phrases to search a product \
catalogue with.

Write one to three phrases per requirement. Use more than one only when the \
requirement genuinely splits — different forms of the same thing that would not \
turn up in one search. Two phrases that would return the same products are a \
wasted search.

Write what a person would type into a shop, not a description. "compact \
adjustable dumbbells" finds things; "dumbbells that are suitable for a customer \
with limited space who wants to train for strength" does not.

Fold in the parts of the mission that change which products are right — small \
space, beginner, quiet, portable. Leave out the parts that do not help a text \
search: prices and budgets, the country they live in, whether something is in \
stock. Those are applied as filters afterwards, and putting them in the words \
only matches products that happen to mention them.

Keep each phrase to the category and the qualities that matter. Do not name \
specific brands or models unless the customer named them.

Set ships_to_country to the two-letter code for wherever the customer said they \
are. Leave it out if they did not say.\

"""


async def plan_searches(mission:ShoppingMission, requirements: list[MissionRequirement]) -> DiscoveryPlan:

    lines = [f"Mission: {mission.goal}"]

    if mission.location:
        lines.append(f"customer location {mission.location}")

    constraints = (mission.constraints or {}).get("items") or []

    if constraints:
        lines.append("Constraints:")
        lines += [f" - {c.get('type')}: {c.get('value')}" for c in constraints]

    preferences = (mission.preferences or {}).get("items") or []
    if preferences:
        lines.append("Preferences:")
        lines += [f"  - {p.get('type')}: {p.get('value')}" for p in preferences]

    lines.append("")
    lines.append("Requirements:")
    for index, requirement in enumerate(requirements, start=1):
        detail = f" — {requirement.description}" if requirement.description else ""
        lines.append(
            f"  {index}. {requirement.category} "
            f"({requirement.priority.value}){detail}"
        )

    plan = await generate_structured(
        system=SYSTEM_PROMPT,
        user_message="\n".join(lines),
        output_model=DiscoveryPlan
    )
    logger.info(
        "discovery_plan requirements=%d searches=%d ships_to=%s",
        len(requirements),
        sum(len(s.queries) for s in plan.searches),
        plan.ships_to_country,
    )

    return plan