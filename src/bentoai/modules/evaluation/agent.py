import logging

from bentoai.modules.commerce.dtos import CandidateProduct
from bentoai.modules.evaluation.contracts import RequirementEvaluation
from bentoai.modules.evaluation.filtering import cheapest_purchasable
from bentoai.modules.planner.models import MissionRequirement, ShoppingMission
from bentoai.shared.llm import ModelRefused,generate_structured

logger = logging.getLogger(__name__)


SHORTLIST_SIZE = 8

MAX_FIELD_CHARS = 400


SYSTEM_PROMPT = """\
You product manager, you judge how well products suit a customer's shopping mission.

You are given one thing the mission needs, what the customer said about \
themselves, and a numbered list of products that are all genuinely for sale \
and within budget. For each product, say how well it fits.

Judge three things separately.

requirement_fit is whether the product does the job. A bench that does not \
adjust is a poor fit for "adjustable bench" no matter how good it is.

preference_fit is whether it suits this particular customer - the space they \
have, their experience level, how they said they want to use it. A superb \
commercial-grade machine is a poor preference fit for someone with a small \
apartment who said they are starting out.

confidence is how much the listing actually told you. Product descriptions \
are written to sell and their specifications are often vague or partly \
guessed. If you cannot tell whether something is genuinely compact because \
nobody stated a size, say your confidence is low. Do not quietly turn an \
assumption into a verdict - a wrong confident answer costs the customer more \
than an honest uncertain one.

In trade_offs, name what the customer gives up by choosing this one. Be \
concrete and short: "heavier than the others", "no warranty stated", "takes \
up more floor space". Leave it empty if there is genuinely nothing to note.

In reason, write one sentence a shopper would understand, about this product. \
It is shown on the product card, so write it for them and not for us.

Judge only what you are shown. Do not invent specifications, prices, sizes, \
or availability, and do not compare against products that are not in the list.\


"""


async def evaluate_requirement(mission:ShoppingMission, requirement: MissionRequirement, candidates: list[CandidateProduct]) -> RequirementEvaluation:


    if not candidates:
        return RequirementEvaluation()

    prompt = _build_prompt(mission, requirement, candidates)

    try:
        result = generate_structured(
            system=SYSTEM_PROMPT,
            user_message=prompt,
            output_model=RequirementEvaluation,
        )

    except ModelRefused as exc:

        logger.warning("evaluation_refused requirement=%s reason=%s", requirement.category, exc)

        return RequirementEvaluation()

    logger.info(

        "evaluation_complete requirement=%s candidates=%d assessments=%d",
        requirement.category,
        len(candidates),
        len(result.assessments),


    )

    return result


def _build_prompt(mission:ShoppingMission, requirement:MissionRequirement, candidates: list[CandidateProduct]) -> str:

    lines = [f"Mission: {mission.goal}"]

    if mission.location:
        lines.append(f"Customer location: {mission.location}")

    constraints = (mission.constraints or {}).get("items") or []
    if constraints:
        lines.append("Constraints:")
        lines += [f"  - {c.get('type')}: {c.get('value')}" for c in constraints]

    preferences = (mission.preferences or {}).get("items") or []
    if preferences:
        lines.append("Preferences:")
        lines += [f"  - {p.get('type')}: {p.get('value')}" for p in preferences]

    lines.append("")
    lines.append(f"Requirement: {requirement.category} ({requirement.priority.value})")
    if requirement.description:
        lines.append(f"What would satisfy it: {requirement.description}")

    lines.append("")
    lines.append("Products:")

    for index, candidate in enumerate(candidates, start=1):
        lines.append("")
        lines.append(f"  {index}. {candidate.title}")

        offer = cheapest_purchasable(candidate)
        if offer is not None:
            lines.append(f"     Price: {offer.price_amount} {offer.currency}")
            lines.append(f"     Sold by: {offer.merchant_name}")

        # Ratings go in because "4.9 from 705 people" and "4.9 from 3 people"
        # are different facts, and a reader who sees only the 4.9 cannot tell
        # them apart. Scoring weighs the count too, separately.
        if candidate.rating_value is not None:
            count = candidate.rating_count or 0
            lines.append(f"     Rated {candidate.rating_value} from {count} ratings")

        if candidate.description:
            lines.append(f"     {_trim(candidate.description)}")

        for key in ("top_features", "tech_specs", "unique_selling_points"):
            value = candidate.attributes.get(key)
            if value:
                label = key.replace("_", " ").capitalize()
                lines.append(f"     {label}: {_trim(value)}")

    return "\n".join(lines)

def _trim(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= MAX_FIELD_CHARS:
        return flat
    return flat[:MAX_FIELD_CHARS].rstrip() + "..."


def shortlist(candidates: list[CandidateProduct]) -> list[CandidateProduct]:
 
    return candidates[:SHORTLIST_SIZE]
