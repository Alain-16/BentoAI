import logging

from bentoai.modules.deterministicService.basket.contract import BasketComparison
from bentoai.modules.deterministicService.basket.optimizer import RequirementOptions
from bentoai.modules.planner.models import ShoppingMission
from bentoai.shared.llm import ModelRefused, generate_structured


logger = logging.getLogger(__name__)

MAX_REASON_CHARS = 220


SYSTEM_PROMPT = """\
You help a customer choose between the last few products for each thing their \
shopping mission needs.

Every product you are shown has already passed the checks - it is for sale, it \
reaches them, and it is affordable on its own. Two or three are left per \
requirement. Your job is to say which one this particular customer should take, \
and to describe the others clearly enough that they could reasonably disagree \
with you.

For each requirement, choose the option that best suits this customer - the \
space they have, how they said they will use it, the level they are at. Where \
options are close, prefer the one that is more clearly described over the one \
making bigger claims with less to back them up.

Write one short note per option, and make the notes distinguish them. "Good \
ergonomic chair" said three times helps nobody. Say what is actually different: \
"the only one with a headrest", "cheapest, but no lumbar adjustment", "best \
reviewed of the three".

Then write one sentence saying why your choice wins for this customer.

Do not try to make the whole basket fit a budget, and do not add up prices. \
That is worked out separately, afterwards, in ordinary arithmetic. Your \
preference for one requirement will be weighed against every other requirement \
by something that can count properly. Choose the best product for each need and \
leave the totals alone.

Judge only what you are shown. Do not invent specifications or prices, and do \
not refer to products that are not in the list.\
"""


async def compare(
        mission: ShoppingMission, pool: list[RequirementOptions]
) -> BasketComparison:

    if not pool:
        return BasketComparison()

    try:
        result = await generate_structured(
            system= SYSTEM_PROMPT,
            user_message=_build_prompt(mission, pool),
            output_model=BasketComparison,
        )

    except ModelRefused as exc:
        logger.warning("comparison_refused mission=%s reaseon=%s", mission.id, exc)
        return BasketComparison()

    logger.info(
        "comparison_complete requirements=%d choice=%d",
        len(pool),
        len(result.choices),
    )

    return result


def _build_prompt(mission: ShoppingMission, pool: list[RequirementOptions]) -> str:
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

    for requirement_index, requirement_options in enumerate(pool, start=1):
        requirement = requirement_options.requirement
        lines.append("")
        lines.append(
            f"Requirement {requirement_index}: {requirement.category} "
            f"({requirement.priority.value})"
        )

        for option_index, option in enumerate(requirement_options.options, start=1):
            lines.append(
                f"  {option_index}. {option.title} - {option.price} {option.currency} "
                f"from {option.merchant_name}"
            )
            if option.reason:
                lines.append(f"     Earlier note: {_trim(option.reason)}")
            if option.trade_offs:
                lines.append(f"     Trade-offs: {'; '.join(option.trade_offs)}")

    return "\n".join(lines)

def _trim(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= MAX_REASON_CHARS else flat[:MAX_REASON_CHARS].rstrip() + "..."


def preferred_products(
    comparison: BasketComparison, pool: list[RequirementOptions]
) -> dict[str, str]:

    preferred: dict[str, str] = {}

    for choice in comparison.choices:
        if not 1 <= choice.requirement_index <= len(pool):
            logger.warning(
                "Ignoring a choice for requirement %s - only %d were shown",
                choice.requirement_index,
                len(pool),
            )
            continue

        requirement_options = pool[choice.requirement_index - 1]
        options = requirement_options.options

        if not 1 <= choice.preferred_option_index <= len(options):
            logger.warning(
                "Ignoring option %s for %r - only %d were offered",
                choice.preferred_option_index,
                requirement_options.requirement.category,
                len(options),
            )
            continue

        preferred[str(requirement_options.requirement.id)] = options[
            choice.preferred_option_index - 1
        ].product_id

    return preferred


def notes_by_product(
    comparison: BasketComparison, pool: list[RequirementOptions]
) -> dict[str, str]:
    
    notes: dict[str, str] = {}

    for choice in comparison.choices:
        if not 1 <= choice.requirement_index <= len(pool):
            continue
        options = pool[choice.requirement_index - 1].options

        for note in choice.notes:
            if 1 <= note.option_index <= len(options):
                notes[options[note.option_index - 1].product_id] = note.note

    return notes