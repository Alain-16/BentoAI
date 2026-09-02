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
from bentoai.modules.deterministicService.basket.smart_basket import (
    ensure_basket,
    prune_orphans,
    seed_from_optimizer,
    selected_by_requirement,
)
from bentoai.modules.evaluation.filtering import cheapest_purchasable
from bentoai.modules.evaluation.service import build_recommendations
from bentoai.modules.planner.models import ShoppingMission

from sqlalchemy.ext.asyncio import AsyncSession


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

    def __init__(
        self, session: AsyncSession, gateway: CommerceGateway, settings: Settings
    ) -> None:
        self.session = session
        self.gateway = gateway
        self.settings = settings


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

        # Turn the winning combination into a basket the customer owns. Only
        # fills an empty one - see seed_from_optimizer - so re-running the
        # optimizer never overwrites a choice somebody made by hand.
        await seed_from_optimizer(
            self.session, mission, self._picks(recommendations, solution)
        )

        return OptimizerOutcome(pool=pool,solution=solution)

    def _picks(self, recommendations: list[dict], solution) -> list[tuple]:
        """Match the solver's chosen product ids back to real products.

        The solver works with a small Option carrying only what it needs for
        arithmetic. Writing a basket row needs the whole product and its offer,
        which the rehydrated recommendations still hold - so they are looked up
        here by id rather than dragged through a solver that has no use for
        them.
        """
        by_product = {
            item["candidate"].source_product_id: item["candidate"]
            for group in recommendations
            for item in group["items"]
        }

        picks = []
        for choice in solution.choices:
            if choice.option is None:
                continue
            candidate = by_product.get(choice.option.product_id)
            if candidate is None:
                continue
            offer = cheapest_purchasable(candidate)
            if offer is None:
                continue
            picks.append((choice.requirement, candidate, offer))

        return picks

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
                        "breakdown": option.breakdown,
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
    session: AsyncSession, mission: ShoppingMission, gateway: CommerceGateway
) -> dict:
    """The basket as it stands right now, with live prices.

    Two things are merged here. The Smart Basket says what the customer has
    chosen; the stored option pool says what else they could choose instead. The
    workspace needs both - one to show the basket, one to offer the swap.

    Every price is fetched again rather than read back. A price the customer
    sees has to be the price they would pay, and §5.11 is explicit that a stale
    one must never reach checkout. The stored snapshot is still used, but only
    to notice that something has moved.
    """
    stored = (mission.basket_options or {}).get("requirements") or {}
    if not stored:
        return {}

    basket = await ensure_basket(session, mission)

    # A requirement can disappear if the customer edits their plan and searches
    # again. An item pointing at one that is gone belongs to no part of the plan
    # any more, so it goes - and is reported rather than quietly vanishing.
    live_requirement_ids = {r.id for r in mission.requirements}
    dropped = prune_orphans(basket, live_requirement_ids)

    chosen_product = selected_by_requirement(basket)
    snapshot_price = {
        str(item.requirement_id): item.unit_price_amount
        for item in basket.items
        if item.requirement_id
    }

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

    groups: list[dict] = []
    total = Decimal("0.00")
    gone: list[str] = []
    moved: list[str] = []
    blockers: list[dict] = []

    for requirement in sorted(mission.requirements, key=lambda r: r.position):
        key = str(requirement.id)
        entry = stored.get(key)
        if entry is None:
            continue

        # What the customer picked. Before they have picked anything the basket
        # holds the optimizer's seed, so this is filled either way; the stored
        # flag is only a fallback for a mission optimised before baskets
        # existed.
        selected_id = chosen_product.get(key)

        options: list[dict] = []
        # Why the thing they chose cannot be bought, if it cannot. Recorded per
        # requirement so the review screen can name it and offer a way out,
        # rather than the item quietly vanishing from the list.
        blocked: str | None = None
        blocked_title: str | None = None

        for option in entry.get("options") or []:
            product_id = option.get("product_id")
            candidate = products.get(product_id)

            if candidate is None:
                if product_id == selected_id:
                    gone.append(requirement.category)
                    blocked = "no_longer_listed"
                    blocked_title = (option.get("title") or "").strip() or None
                continue

            offer = cheapest_purchasable(candidate)
            if offer is None:
                # Every offer is explicitly out of stock. Different from the
                # product disappearing, and worth saying differently - one may
                # come back, the other will not.
                if product_id == selected_id:
                    blocked = "out_of_stock"
                    blocked_title = candidate.title
                continue

            is_chosen = (
                product_id == selected_id
                if selected_id is not None
                else bool(option.get("chosen"))
            )

            was = snapshot_price.get(key) if is_chosen else None
            if is_chosen:
                total += offer.price_amount * requirement.quantity
                if was is not None and was != offer.price_amount:
                    moved.append(
                        f"{candidate.title} was {was} and is now {offer.price_amount}"
                    )

            options.append(
                {
                    "stored": option,
                    "candidate": candidate,
                    "offer": offer,
                    "chosen": is_chosen,
                    "selected_by": (
                        (
                            next(
                                (
                                    (i.item_metadata or {}).get("selected_by")
                                    for i in basket.items
                                    if str(i.requirement_id) == key
                                ),
                                "optimizer",
                            )
                        )
                        if is_chosen
                        else None
                    ),
                    "price_was": was if was != offer.price_amount else None,
                }
            )

        # Something else this requirement could have instead. The pool has
        # already been filtered and priced, so the best remaining option is a
        # real offer rather than a suggestion to go and look again.
        replacement = None
        if blocked:
            available = [o for o in options if not o["chosen"]]
            if available:
                best = max(available, key=lambda o: o["stored"].get("score") or 0)
                replacement = {
                    "product_id": best["candidate"].source_product_id,
                    "title": best["candidate"].title,
                    "price": best["offer"].price_amount * requirement.quantity,
                    "currency": best["offer"].currency,
                    "merchant_name": best["offer"].merchant_name,
                }

            blockers.append(
                {
                    "requirement_id": str(requirement.id),
                    "category": requirement.category,
                    "title": blocked_title or requirement.category,
                    "reason": blocked,
                    "replacement": replacement,
                }
            )

        groups.append(
            {
                "requirement": requirement,
                "options": options,
                "selected": next((o for o in options if o["chosen"]), None),
                "blocked": blocked,
            }
        )

    notes = list((mission.basket_options or {}).get("notes") or [])
    budget = mission.budget_amount

    if dropped:
        notes.append(
            "Removed from your basket because the plan changed: "
            + ", ".join(dropped)
            + "."
        )

    if gone:
        notes.append(
            "No longer available and dropped out of the basket: "
            + ", ".join(gone)
            + ". Pick a replacement below."
        )

    if moved:
        notes.append("Prices have changed since you chose: " + "; ".join(moved) + ".")

    if budget is not None and total > budget:
        notes.append(
            f"This basket comes to {total}, which is {total - budget} over budget."
        )

    for failure in failures:
        notes.append(f"{failure.provider} could not be reached: {failure.reason}")

    selected_items = [g["selected"] for g in groups if g["selected"]]
    merchants = {
        item["offer"].merchant_domain for item in selected_items if item["offer"].merchant_domain
    }

    return {
        "groups": groups,
        "total": total,
        "remaining": (budget - total) if budget is not None else None,
        "feasible": bool((mission.basket_options or {}).get("feasible", True)),
        "notes": notes,
        # Everything the review screen needs to say whether this can be
        # approved, and what it is approving.
        "blockers": blockers,
        "item_count": len(selected_items),
        "merchant_count": len(merchants),
        "requirements_total": len(mission.requirements),
        "requirements_met": len(selected_items),
    }
