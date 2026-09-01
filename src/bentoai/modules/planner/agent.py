"""The Planning Agent.

Turns a broad goal into structured requirements. It reasons and returns data. It
does not touch the database, search anything, or move the mission's state — the
shape of this module is what enforces that. It takes a request and returns a
result, and has no other way to affect anything.
"""
import logging
from bentoai.modules.planner.contracts import PlanningRequest, PlanningResult
from bentoai.shared.llm import generate_structured

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You plan shopping missions. A customer describes something they want to \
accomplish, and you work out the categories of product needed to accomplish it.

Break the goal into concrete product categories a shop would recognise. Mark a \
category required when the goal fails without it, and optional when it improves \
the outcome but is not essential. Order them so the most important come first.

Separate hard constraints from soft preferences. A hard constraint disqualifies \
a product outright — it does not ship to their country, it does not fit the \
space they have. A soft preference is something they would like: a style, a \
brand leaning, a quality level. Getting this wrong is costly in both \
directions. A preference treated as hard throws away good options, and a \
constraint treated as soft recommends things that cannot work.

Name product categories, not specific products. You have not searched anything \
and you do not know what is in stock, what it costs, or what is currently \
available. Do not state specifications or prices as fact.

If something is genuinely missing and would change the plan, say so in \
missing_information rather than guessing. Do not fill it with questions you \
could reasonably answer yourself — only what actually blocks a good plan. \
Notify the user so that the user can make some changes in the goal.

Where they are is one of those things. It decides which shops can reach them \
and which currency their prices come back in, so without it the products \
found may be ones they cannot buy or cannot price.

So if they have not said where they are at all, ask - plainly, for example: \
"Which country should these be delivered to?" But if they have named any \
place, take it and move on. Do not ask them to confirm it, spell it out, or \
add the country to a city you already recognise. A question they have already \
answered teaches them their answers are not being read.

Budget allocations are rough guidance for a later step, not decisions. Leave \
them out when you have no sound basis for a split.\

The customer may state a budget or a location inside their sentence rather than \
filling in a field. Read those out and return them. Report only what they \
actually said — never estimate a budget they did not give, and never guess a \
location from anything other than their own words. Leave either one out when \
they did not mention it.\
"""


async def run_planning(request: PlanningRequest) -> PlanningResult:

    lines = [f"Goal: {request.goal}"]

    if request.budget_amount is not None:
        lines.append(f"Budget {request.budget_amount} {request.budget_currency}")

    if request.location:
        lines.append(f"Delivering to: {request.location}")

    result = await generate_structured(
        system=SYSTEM_PROMPT,
        user_message="\n".join(lines),
        output_model=PlanningResult,
    )

    logger.info(
        "planning_complete requirements=%d constraints=%d questions=%d",
        len(result.requirements),
        len(result.constraints),
        len(result.missing_information),
    )

    return result