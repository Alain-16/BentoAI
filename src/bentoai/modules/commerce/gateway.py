"""The one door between the application and external commerce.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from bentoai.modules.commerce.dtos import CandidateProduct, ProductSearchQuery
from bentoai.modules.commerce.providers.base import (
    CommerceProvider,
    ProviderCapability,
    ProviderError,
)

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ProviderFailure:
    provider: str
    reason: str


@dataclass
class SearchOutcome:
    """What came back, and what went wrong on the way."""

    candidates: list[CandidateProduct] = field(default_factory=list)
    failures: list[ProviderFailure] = field(default_factory=list)


class CommerceGateway:
    def __init__(self) -> None:
        self._providers: list[CommerceProvider] = []

    def register(self, provider: CommerceProvider) -> None:
        self._providers.append(provider)

    def providers_for(self, capability: ProviderCapability) -> list[CommerceProvider]:
        """Only the providers that say they can do this."""
        return [p for p in self._providers if p.supports(capability)]

    async def search(self, query: ProductSearchQuery) -> SearchOutcome:
        """Ask every catalog-capable provider the same question at once.

        """
        providers = self.providers_for(ProviderCapability.CATALOG_SEARCH)
        if not providers:
            return SearchOutcome()

        # return_exceptions keeps one failing call from cancelling the others.
        results = await asyncio.gather(
            *(p.search_products(query) for p in providers),
            return_exceptions=True,
        )

        outcome = SearchOutcome()

        for provider, result in zip(providers, results, strict=True):
            if isinstance(result, ProviderError):
                logger.warning("Search failed on %s: %s", provider.name, result.reason)
                outcome.failures.append(ProviderFailure(provider.name, result.reason))
            elif isinstance(result, BaseException):
                # Something we did not anticipate. Recorded rather than raised,
                # for the same reason as above, but logged with a stack trace
                # because an unexpected error is a bug rather than weather.
                logger.exception(
                    "Unexpected error searching %s", provider.name, exc_info=result
                )
                outcome.failures.append(ProviderFailure(provider.name, "unexpected error"))
            else:
                outcome.candidates.extend(result)

        return outcome

    async def lookup(
        self,
        ids: list[str],
        *,
        ships_to_country: str | None = None,
        currency: str | None = None,
    ) -> SearchOutcome:
        """Resolve stored identifiers to current data across providers."""
        providers = self.providers_for(ProviderCapability.CATALOG_LOOKUP)
        outcome = SearchOutcome()

        for provider in providers:
            try:
                outcome.candidates.extend(
                    await provider.lookup_products(
                        ids, ships_to_country=ships_to_country, currency=currency
                    )
                )
            except ProviderError as exc:
                logger.warning("Lookup failed on %s: %s", provider.name, exc.reason)
                outcome.failures.append(ProviderFailure(provider.name, exc.reason))

        return outcome