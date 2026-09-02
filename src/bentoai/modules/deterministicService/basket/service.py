import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from bentoai.config import Settings
from bentoai.modules.deterministicService.basket import agent
from bentoai.modules.deterministicService.basket.optimizer import (
    BasketSolution,
    Option,
    RequirementOptions,
    build_option_pool,
    solve,
)
from bentoai.modules.commerce.dtos import CandidateProduct
from bentoai.modules.commerce.gateway import CommerceGateway, ProviderFailure
from bentoai.modules.evaluation.service import build_recommendations
from bentoai.modules.planner.models import ShoppingMission


logger = logging.getLogger(__name__)


class NothingToOptimize(Exception):
    """There is nothing to build a basket from.

    Two different situations reach here and they need different answers, so the
    reason travels on the exception rather than being guessed at by the caller.

    NOT_EVALUATED  evaluation has not run yet - running it is the fix.
    NO_PRODUCTS    it ran and nothing survived. Running it again changes
                   nothing, because the filter is deterministic over the same
                   candidates. The customer has to change something.
    """

    NOT_EVALUATED = "not_evaluated"
    NO_PRODUCTS = "no_products"

    def __init__(self, mission_id: str, reason: str) -> None:
        super().__init__(f"{mission_id}: {reason}")
        self.mission_id = mission_id
        self.reason = reason


@dataclass
class OptimizerOutcome:
    pool: list[RequirementOptions] = field(default_factory=list)
    solution: BasketSolution = field(default_factory=BasketSolution)
    failures: list[ProviderFailure] = field(default_factory=list)

class BasketOptimizerService:

    def __init__(self, gateway:CommerceGateway, settings:Settings) -> None:
        self.gateway=gateway
        self.settings=settings


    async def run(self,mission:ShoppingMission)-> OptimizerOutcome:
        if not(mission.evaluation_results or {}).get("requirements"):
            raise NothingToOptimize(str(mission.id), NothingToOptimize.NOT_EVALUATED)

        recommendations= await build_recommendations(mission, self.gateway)

        pool = build_option_pool(recommendations)

        if not pool:
            # Evaluation ran fine; everything it looked at was rejected.
            raise NothingToOptimize(str(mission.id), NothingToOptimize.NO_PRODUCTS)

        comparison = await agent.compare(mission, pool)
        preferred = agent.preferred_products(comparison, pool)
        notes = agent.notes_by_product(comparison,pool)

        solution = solve(pool,mission.budget_amount, preferred)

        self._write_back(mission,pool, solution, preferred,notes)

        return OptimizerOutcome(pool=pool,solution=solution)

    def _write_back(
            self,
            mission: ShoppingMission,
            pool: list[RequirementOptions],
            solution: BasketSolution,
            preferred: dict[str, str],
            notes: dict[str, str],
    ) -> None:

        chosen = {
            str(choice.requirement.id): choice.option.product_id
            for choice in solution.choices
            if choice.option is not None
        }

        requirements: dict[str, str] = {}

        for requirement_options in pool:
            requirement_id = str(requirement_options.requirement.id)
            requirements[requirement_id] = {
                "options": [
                    {
                        "product_id": option.product_id,
                        "provider": option.provider,
                        "score": option.score,
                        "included_as": option.included_as,
                        "reason": option.reason,
                        "trade_offs": list(option.trade_offs),
                        "note": notes.get(option.product_id, ""),
                        "preferred": preferred.get(requirement_id) == option.product_id,
                        "chosen": chosen.get(requirement_id) == option.product_id,
                    }
                    for option in requirement_options.options
                ],
            }

            mission.basket_options = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "requirements": requirements,
            "feasible": solution.feasible,
            "notes": solution.notes,
            }

async def build_basket_view(
    mission: ShoppingMission, gateway: CommerceGateway
) -> dict:
    """Put fresh prices back onto the stored basket, and re-check the sums.

    """
    stored = (mission.basket_options or {}).get("requirements") or {}
    if not stored:
        return {}

    all_ids: list[str] = []
    seen: set[str] = set()
    for entry in stored.values():
        for option in entry.get("options") or []:
            product_id = option.get("product_id")
            if product_id and product_id not in seen:
                seen.add(product_id)
                all_ids.append(product_id)

    products: dict[str, CandidateProduct] = {}
    failures: list[ProviderFailure] = []
    if all_ids:
        found = await gateway.lookup(
            all_ids,
            ships_to_country=(mission.discovery_results or {}).get("ships_to_country"),
            currency=mission.budget_currency,
        )
        products = {c.source_product_id: c for c in found.candidates}
        failures = found.failures

    from bentoai.modules.evaluation.filtering import cheapest_purchasable

    groups: list[dict] = []
    total = Decimal("0.00")
    gone: list[str] = []

    for requirement in sorted(mission.requirements, key=lambda r: r.position):
        entry = stored.get(str(requirement.id))
        if entry is None:
            continue

        options: list[dict] = []
        for option in entry.get("options") or []:
            candidate = products.get(option.get("product_id"))
            if candidate is None:
                if option.get("chosen"):
                    gone.append(requirement.category)
                continue

            offer = cheapest_purchasable(candidate)
            if offer is None:
                continue

            if option.get("chosen"):
                total += offer.price_amount

            options.append({"stored": option, "candidate": candidate, "offer": offer})

        groups.append({"requirement": requirement, "options": options})

    notes = list((mission.basket_options or {}).get("notes") or [])
    budget = mission.budget_amount

    if gone:
        notes.append(
            "These are no longer available and have dropped out of the basket: "
            + ", ".join(gone)
            + ". Rebuild the basket to replace them."
        )

  
    if budget is not None and total > budget:
        notes.append(
            f"Prices have changed since this basket was built. It now comes to "
            f"{total}, which is {total - budget} over budget."
        )

    for failure in failures:
        notes.append(f"{failure.provider} could not be reached: {failure.reason}")

    return {
        "groups": groups,
        "total": total,
        "remaining": (budget - total) if budget is not None else None,
        "feasible": bool((mission.basket_options or {}).get("feasible", True)),
        "notes": notes,
    }
