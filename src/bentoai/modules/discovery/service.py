import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bentoai.config import Settings
from bentoai.modules.commerce.dtos import CandidateProduct, ProductSearchQuery
from bentoai.modules.commerce.gateway import CommerceGateway, ProviderFailure
from bentoai.modules.discovery import agent
from bentoai.modules.planner.models import MissionRequirement, ShoppingMission, RequirementPriority

logger = logging.getLogger(__name__)

MAX_QUERIES_PER_REQUIREMENT = 3


class NothingToSearchFor(Exception):
      """The mission has no requirements, so there is nothing to look for."""


@dataclass
class DiscoveryOutcome:
      requirement_count: int =0
      candidate_count: int =0
      failures: list[ProviderFailure] = field(default_factory=list)
      unmet_required: list[str] = field(default_factory=list)
      unmet_optional: list[str] = field(default_factory=list)


class DiscoveryService:

    def __init__(
                  self, gateway: CommerceGateway, settings: Settings
      ) -> None:

            self.gateway= gateway
            self.settings= settings


    async def run(self, mission: ShoppingMission) -> DiscoveryOutcome:

        requirements = sorted(mission.requirements, key=lambda r: r.position)
        if not requirements:
            raise NothingToSearchFor(str(mission.id))

        plan = await agent.plan_searches(mission, requirements)

        # The agent answered with positions; turn them back into requirements.
        by_index = {index: req for index, req in enumerate(requirements, start=1)}

        outcome = DiscoveryOutcome(requirement_count=len(requirements))
        stored: dict[str, dict] = {}

        for search in plan.searches:
            requirement = by_index.get(search.requirement_index)
            if requirement is None:
                logger.warning(
                    "Ignoring searches for requirement %s — no such position",
                    search.requirement_index,
                )
                continue

            queries = [q.strip() for q in search.queries if q.strip()]
            queries = queries[:MAX_QUERIES_PER_REQUIREMENT]
            if not queries:
                continue

            candidates, failures = await self._search(
                queries, plan.ships_to_country, mission.budget_currency
            )
            outcome.failures.extend(failures)
            outcome.candidate_count += len(candidates)

            stored[str(requirement.id)] = {
                "queries": queries,
                "candidates": [
                    {
                        "product_id": c.source_product_id,
                        "provider": c.provider,
                        "variant_ids": [o.source_variant_id for o in c.offers],
                    }
                    for c in candidates
                ],
            }
            if not candidates:
                    if requirement.priority is RequirementPriority.REQUIRED:
                        outcome.unmet_required.append(requirement.category)
                    else:
                        outcome.unmet_optional.append(requirement.category)

        
        searched = set(stored)
        for requirement in requirements:
            if str(requirement.id) in searched:
                continue
            if requirement.priority is RequirementPriority.REQUIRED:
                outcome.unmet_required.append(requirement.category)
            else:
                outcome.unmet_optional.append(requirement.category)

        mission.discovery_results = {
            "searched_at": datetime.now(timezone.utc).isoformat(),
            "ships_to_country": plan.ships_to_country,
            "requirements": stored,
            "failures": [
                {"provider": f.provider, "reason": f.reason} for f in outcome.failures
            ],
        }

        return outcome

    async def _search(
              self,queries: list[str], ships_to_country: str | None, currency: str
    ) -> tuple[list[CandidateProduct], list[ProviderFailure]]:

         search_queries = [
              ProductSearchQuery(
                   query=query,
                   ships_to_country=ships_to_country,
                   currency=currency,
                   available_only=True,
                   limit=self.settings.commerce.search_limit,

              )
              for query in queries
         ]

         # One at a time, deliberately. Running a requirement's phrases together
         # is what got us rate limited: eight sequential requests to the catalog
         # never tripped the limit, three simultaneous ones did. Discovery is
         # slow either way, so the few extra seconds buy results rather than
         # empty categories.
         outcomes = [await self.gateway.search(q) for q in search_queries]

         merged: dict[str, CandidateProduct] = {}
         failures: list[ProviderFailure] = []

         for outcome in outcomes:
                failures.extend(outcome.failures)
                for candidate in outcome.candidates:
                     merged.setdefault(candidate.source_product_id,candidate)
                     
         capped = list(merged.values())[
              :self.settings.commerce.max_candidates_per_requirement
              
         ]

         return capped, failures

          
