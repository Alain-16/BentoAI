import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bentoai.config import Settings
from bentoai.modules.commerce.dtos import CandidateProduct
from bentoai.modules.commerce.gateway import CommerceGateway, ProviderFailure
from bentoai.modules.evaluation import agent
from bentoai.modules.evaluation.filtering import apply_hard_filters
from bentoai.modules.evaluation.scoring import ScoredCandidate, score_candidates
from bentoai.modules.planner.models import (
    MissionRequirement,
    RequirementPriority,
    RequirementStatus,
    ShoppingMission,
)

logger = logging.getLogger(__name__)


class NothingToEvaluate(Exception):
    """Discovery has no products"""


@dataclass
class RequirementResult:
    requirement: MissionRequirement
    ranked: list[ScoredCandidate] = field(default_factory=list)
    rejected_tally: dict[str, int] = field(default_factory=dict)
    considered: int=0


@dataclass
class EvaluationOutcome:
    results: list[RequirementResult] = field(default_factory=list)
    missing_ids: list[str] = field (default_factory=list)
    requested_count: int=0
    failures: list[ProviderFailure] = field(default_factory=list)

    @property
    def unranked_required(self) -> list[str]:
        """Required things we could not recommend anything for."""
        return [
            r.requirement.category
            for r in self.results
            if not r.ranked and r.requirement.priority is RequirementPriority.REQUIRED
        ]


class EvaluationService:
    def __init__(self,gateway:CommerceGateway, settings:Settings) -> None:
        self.gateway= gateway
        self.settings = settings

    async def run(self, mission:ShoppingMission) -> EvaluationOutcome:
        stored = (mission.discovery_results or {}).get("requirements")

        if not stored:
            raise NothingToEvaluate(str(mission.id))

        ids_by_requirement = self._read_stored_ids(stored)

        products, missing, failures = await self._rehydrate(mission, ids_by_requirement)

        outcome = EvaluationOutcome(
            missing_ids=missing,
            requested_count=sum(len(v) for v in ids_by_requirement.values()),
            failures=failures,
        )

        by_id = {str(r.id): r for r in mission.requirements}

        for requirement_id, product_id in ids_by_requirement.items():
            requirement = by_id.get(requirement_id)

            if requirement is None:

                logger.info("Skipping candidates for removed requirement %s", requirement_id)
                continue

            candidates = [products[pid] for pid in product_id if pid in products]
            outcome.results.append(
                await self._evaluate_one(mission, requirement, candidates)
            )

        outcome.results.sort(key=lambda r: r.requirement.position)

        self._write_back(mission, outcome)
        return outcome

    def _read_stored_ids(self, stored: dict) -> dict[str, list[str]]:

        ids_by_requirement: dict[str, list[str]] = {}

        for requirement_id, entry in stored.items():
            product_ids: list[str] = []
            seen: set[str] = set()

            for candidate in (entry or {}).get("candidates") or []:
                product_id = candidate.get("product_id")
                if product_id and product_id not in seen:
                    seen.add(product_id)
                    product_ids.append(product_id)

            ids_by_requirement[str(requirement_id)] = product_ids

        return ids_by_requirement


    async def _rehydrate(self, mission:ShoppingMission, ids_by_requirement: dict[str, list[str]]) -> tuple[dict[str, CandidateProduct], list[str], list[ProviderFailure]]:


        # Flattened and de-duplicated, keeping first-seen order.
        all_ids: list[str] = []
        seen: set[str] = set()
        for product_ids in ids_by_requirement.values():
            for product_id in product_ids:
                if product_id not in seen:
                    seen.add(product_id)
                    all_ids.append(product_id)

        if not all_ids:
            return {}, [], []

        ships_to = (mission.discovery_results or {}).get("ships_to_country")

        found = await self.gateway.lookup(
            all_ids,
            ships_to_country=ships_to,
            currency=mission.budget_currency,
        )

        products = {c.source_product_id: c for c in found.candidates}

        missing = [product_id for product_id in all_ids if product_id not in products]
        if missing:
            logger.info(
                "lookup_incomplete asked=%d got=%d missing=%d",
                len(all_ids),
                len(products),
                len(missing),
            )

        return products, missing, found.failures

    # -- judging one requirement -----------------------------------------

    async def _evaluate_one(
        self,
        mission: ShoppingMission,
        requirement: MissionRequirement,
        candidates: list[CandidateProduct],
    ) -> RequirementResult:
        """Filter, shortlist, judge and score one requirement's candidates."""
        result = RequirementResult(requirement=requirement, considered=len(candidates))

        if not candidates:
            return result

        # Cheap rules first, so the model only ever reads plausible products.
        filtered = apply_hard_filters(candidates, mission, requirement.quantity)
        result.rejected_tally = filtered.tally()

        if not filtered.accepted:
            return result

        shortlist = agent.shortlist(filtered.accepted)

        evaluation = await agent.evaluate_requirement(mission, requirement, shortlist)

        # The shortlist is passed again, in the same order, because the model
        # answered by position within it.
        result.ranked = score_candidates(shortlist, evaluation.assessments)

        return result

    # -- writing the answer back -----------------------------------------

    def _write_back(self, mission: ShoppingMission, outcome: EvaluationOutcome) -> None:
        """Store ids and our own scores on the mission - never product data.

       
        
        """
        requirements: dict[str, dict] = {}

        for result in outcome.results:
            requirements[str(result.requirement.id)] = {
                "considered": result.considered,
                "rejected": result.rejected_tally,
                "ranked": [
                    {
                        "product_id": scored.candidate.source_product_id,
                        "provider": scored.candidate.provider,
                        "score": scored.score,
                        "breakdown": scored.breakdown,
                        "reason": scored.reason,
                        "trade_offs": scored.trade_offs,
                    }
                    for scored in result.ranked
                ],
            }

            # A requirement we can recommend something for is satisfied. One we
            # cannot goes back to pending, so the workspace can show the
            # customer where the plan still has a hole.
            result.requirement.status = (
                RequirementStatus.SATISFIED if result.ranked else RequirementStatus.PENDING
            )

        mission.evaluation_results = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "requirements": requirements,
            "missing_ids": outcome.missing_ids,
            "requested_count": outcome.requested_count,
            "failures": [
                {"provider": f.provider, "reason": f.reason} for f in outcome.failures
            ],
        }


async def build_recommendations(
    mission: ShoppingMission, gateway: CommerceGateway
) -> list[dict]:
    """Put fresh product data back onto the stored scores, for showing a customer.
    """
    stored = (mission.evaluation_results or {}).get("requirements") or {}
    if not stored:
        return []

    all_ids: list[str] = []
    seen: set[str] = set()
    for entry in stored.values():
        for ranked in entry.get("ranked") or []:
            product_id = ranked.get("product_id")
            if product_id and product_id not in seen:
                seen.add(product_id)
                all_ids.append(product_id)

    products: dict[str, CandidateProduct] = {}
    if all_ids:
        found = await gateway.lookup(
            all_ids,
            ships_to_country=(mission.discovery_results or {}).get("ships_to_country"),
            currency=mission.budget_currency,
        )
        products = {c.source_product_id: c for c in found.candidates}

    recommendations: list[dict] = []

    for requirement in sorted(mission.requirements, key=lambda r: r.position):
        entry = stored.get(str(requirement.id))
        if entry is None:
            continue

        items: list[dict] = []
        for ranked in entry.get("ranked") or []:
            candidate = products.get(ranked.get("product_id"))
            if candidate is None:
                continue
            items.append({"candidate": candidate, "ranked": ranked})

        recommendations.append(
            {
                "requirement": requirement,
                "considered": entry.get("considered", 0),
                "rejected": entry.get("rejected") or {},
                "items": items,
            }
        )

    return recommendations