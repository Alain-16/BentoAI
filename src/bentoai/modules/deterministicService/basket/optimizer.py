import itertools
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from bentoai.modules.planner.models import MissionRequirement, RequirementPriority

logger = logging.getLogger(__name__)


POOL_SIZE = 3

BEST_SLOTS = 2

OPTIONAL_WEIGHT = 0.5

PREFERENCE_BONUS = 0.10

MAX_COMBINATIONS = 250_000



@dataclass
class Option:

    product_id: str
    provider: str
    title: str
    price: Decimal
    currency: str
    merchant_name: str
    score: float
    reason:str
    trade_offs: tuple[str, ...] = ()

    included_as: str = "best score"


@dataclass
class RequirementOptions:

    requirement: MissionRequirement
    options: list[Option] = field(default_factory=list)

    @property
    def is_optional(self) -> bool:
        return self.requirement.priority is RequirementPriority.OPTIONAL

@dataclass
class Choice:

    requirement: MissionRequirement
    option: Option | None


@dataclass
class BasketSolution:
    choices: list[Choice] = field(default_factory=list)

    total: Decimal = Decimal("0.00")
    remaining: Decimal | None = None

    feasible: bool = True
    shortfall: Decimal | None = None

    notes: list[str] = field(default_factory=list)

    @property
    def selected(self) -> list[Choice]:
        return [c for c in self.choices if c.option is not None]



def build_option_pool(recommendations: list[dict]) -> list[RequirementOptions]:

    pool: list[RequirementOptions] = []

    for group in recommendations:
        items = group.get("items") or []

        if not items:
            continue

        options = [_to_option(item) for item in items]

        chosen = options[:BEST_SLOTS]

        cheapest = min(options, key=lambda o: o.price)

        # The guard covers only the extra option. If the cheapest product is
        # already one of the two best-scoring, the pool is simply shorter -
        # there is no reason to pad it with a third product nobody needs.
        if all(o.product_id != cheapest.product_id for o in chosen):
            chosen.append(
                Option(**{**cheapest.__dict__, "included_as": "cheapest that passed"})
            )

        # Every requirement that had anything to offer belongs in the pool,
        # whether or not it gained that third option.
        pool.append(
            RequirementOptions(requirement=group["requirement"], options=chosen)
        )

    logger.info(
        "option_pool requirements=%d options=%d",
        len(pool),
        sum(len(r.options) for r in pool),
    )

    return pool



def _to_option(item:dict) -> Option:

    candidate = item["candidate"]
    ranked = item["ranked"]

    from bentoai.modules.evaluation.filtering import cheapest_purchasable

    offer = cheapest_purchasable(candidate)

    return Option(
        product_id=candidate.source_product_id,
        provider=candidate.provider,
        title=candidate.title,
        price=offer.price_amount if offer else Decimal("0.00"),
        currency=offer.currency if offer else "",
        merchant_name=offer.merchant_name if offer else "",
        score=float(ranked.get("score") or 0.0),
        reason=ranked.get("reason") or "",
        trade_offs=tuple(ranked.get("trade_offs") or ()),
    )


def solve(
    pool: list[RequirementOptions],
    budget: Decimal | None,
    preferred: dict[str, str] | None = None,
) -> BasketSolution:
    """Find the best combination of one product per requirement that fits.
    """
    preferred = preferred or {}

    if not pool:
        return BasketSolution(notes=["There were no products to choose from."])

    groups = _trim_to_searchable(pool)

    best_value: float | None = None
    best_total = Decimal("0.00")
    best_combo: tuple[Option | None, ...] | None = None

    for combo in itertools.product(*groups):
        total = sum((o.price for o in combo if o is not None), Decimal("0.00"))

        if budget is not None and total > budget:
            continue

        value = _value_of(combo, pool, preferred)

        # Highest value wins. Between two baskets we value equally, the cheaper
        # one wins - the customer keeps the difference.
        if best_value is None or value > best_value or (
            value == best_value and total < best_total
        ):
            best_value, best_total, best_combo = value, total, combo

    if best_combo is None:
        # Nothing fits. Return the cheapest required-only basket so the customer
        # can see the real number instead of an empty page.
        return _cheapest_possible(pool, budget)

    solution = BasketSolution(
        choices=[
            Choice(requirement=ro.requirement, option=option)
            for ro, option in zip(pool, best_combo, strict=True)
        ],
        total=best_total,
        remaining=(budget - best_total) if budget is not None else None,
    )

    solution.notes = _explain(solution, pool, preferred)

    logger.info(
        "basket_solved items=%d total=%s remaining=%s",
        len(solution.selected),
        solution.total,
        solution.remaining,
    )
    return solution


def _value_of(
    combo: tuple[Option | None, ...],
    pool: list[RequirementOptions],
    preferred: dict[str, str],
) -> float:
  
    total = 0.0

    for requirement_options, option in zip(pool, combo, strict=True):
        if option is None:
            continue

        value = option.score
        if preferred.get(str(requirement_options.requirement.id)) == option.product_id:
            value += PREFERENCE_BONUS

        if requirement_options.is_optional:
            value *= OPTIONAL_WEIGHT

        total += value

    return total


def _trim_to_searchable(pool: list[RequirementOptions]) -> list[list[Option | None]]:
   
    groups: list[list[Option | None]] = []
    for requirement_options in pool:
        choices: list[Option | None] = list(requirement_options.options)
        if requirement_options.is_optional:
            choices.append(None)
        groups.append(choices)

    while _combination_count(groups) > MAX_COMBINATIONS:
        biggest = max(range(len(groups)), key=lambda i: len(groups[i]))
        if len(groups[biggest]) <= 1:
            break
        weakest = min(
            (c for c in groups[biggest] if c is not None),
            key=lambda o: o.score,
            default=None,
        )
        if weakest is None:
            break
        groups[biggest].remove(weakest)
        logger.info("Trimmed %r from the pool to keep the search small", weakest.title)

    return groups


def _combination_count(groups: list[list[Option | None]]) -> int:
    count = 1
    for group in groups:
        count *= max(1, len(group))
    return count


def _cheapest_possible(
    pool: list[RequirementOptions], budget: Decimal | None
) -> BasketSolution:
   
    choices: list[Choice] = []
    total = Decimal("0.00")

    for requirement_options in pool:
        if requirement_options.is_optional or not requirement_options.options:
            choices.append(Choice(requirement_options.requirement, None))
            continue
        cheapest = min(requirement_options.options, key=lambda o: o.price)
        choices.append(Choice(requirement_options.requirement, cheapest))
        total += cheapest.price

    shortfall = (total - budget) if budget is not None else None

    notes = []
    if shortfall is not None and shortfall > 0:
        notes.append(
            f"The required items alone come to {total}, which is {shortfall} over "
            "the budget. Raise the budget, or drop or reword a requirement."
        )
    notes.append("Optional items were left out because the budget is already exceeded.")

    return BasketSolution(
        choices=choices,
        total=total,
        remaining=(budget - total) if budget is not None else None,
        feasible=False,
        shortfall=shortfall if shortfall and shortfall > 0 else None,
        notes=notes,
    )


def _explain(
    solution: BasketSolution,
    pool: list[RequirementOptions],
    preferred: dict[str, str],
) -> list[str]:
 
    notes: list[str] = []

    for requirement_options, choice in zip(pool, solution.choices, strict=True):
        wanted_id = preferred.get(str(requirement_options.requirement.id))
        if not wanted_id:
            continue

        wanted = next(
            (o for o in requirement_options.options if o.product_id == wanted_id), None
        )
        if wanted is None:
            continue

        if choice.option is None:
            notes.append(
                f"{requirement_options.requirement.category} was left out to stay "
                f"within budget."
            )
        elif choice.option.product_id != wanted.product_id:
            saved = wanted.price - choice.option.price
            notes.append(
                f"For {requirement_options.requirement.category}, "
                f"{choice.option.title} was chosen over {wanted.title}, "
                f"saving {saved} {choice.option.currency}."
            )

    skipped = [
        c.requirement.category
        for c in solution.choices
        if c.option is None and c.requirement.priority is RequirementPriority.OPTIONAL
    ]
    if skipped and not notes:
        notes.append("These optional items did not fit: " + ", ".join(skipped) + ".")

    return notes
       
    

