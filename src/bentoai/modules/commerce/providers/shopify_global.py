"""
shopify's Global Catalog — every merchant on the platform, one endpoint.
"""

import asyncio
import logging
import uuid

import httpx

from bentoai.modules.commerce.dtos import CandidateProduct, ProductSearchQuery
from bentoai.modules.commerce.normalization import normalize_search_response
from bentoai.modules.commerce.providers.base import (
    CommerceProvider,
    ProviderCapability,
    ProviderRateLimited,
    ProviderRejected,
    ProviderTimeout,
    ProviderUnavailable,
)

logger = logging.getLogger(__name__)

_HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}

_LOOKUP_BATCH_SIZE = 50

# Waiting a moment and asking again is the whole strategy. The catalog sends no
# Retry-After or rate-limit headers, so there is nothing to read — these numbers
# come from watching how it behaves. Eight sequential requests never tripped the
# limit; three at once did.
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 3.0)


class ShopifyGlobalCatalogProvider(CommerceProvider):

    name = "shopify_global"

    capabilities = frozenset(
        {ProviderCapability.CATALOG_SEARCH, ProviderCapability.CATALOG_LOOKUP}
    )

    def __init__(self,*, endpoint: str, agent_profile_url:str,client:httpx.AsyncClient,timeout_seconds: int = 30) -> None:
        self.endpoint= endpoint
        self.agent_profile_url=agent_profile_url
        self._client= client
        self._timeout= timeout_seconds


    async def search_products(self, query:ProductSearchQuery) -> list[CandidateProduct]:

        catalog: dict = {
            "query": query.query,
            "filters": {"available": query.available_only},
            "pagination": {"limit": query.limit},
        }

        context: dict = {}
        if query.ships_to_country:
            context["address_country"] = query.ships_to_country
            
            catalog["filters"]["ships_to"] = {"country": query.ships_to_country}
        if query.currency:
            context["currency"] = query.currency
        if context:
            catalog["context"] = context

        structured = await self._call("search_catalog", {"catalog": catalog})
        return normalize_search_response(structured, self.name)

    async def lookup_products(
        self,
        ids: list[str],
        *,
        ships_to_country: str | None = None,
        currency: str | None = None,
    ) -> list[CandidateProduct]:
      
        found: list[CandidateProduct] = []

        for start in range(0, len(ids), _LOOKUP_BATCH_SIZE):
            batch = ids[start : start + _LOOKUP_BATCH_SIZE]

            catalog: dict = {"ids": batch}
            context: dict = {}
            if ships_to_country:
                context["address_country"] = ships_to_country
            if currency:
                context["currency"] = currency
            if context:
                catalog["context"] = context

            structured = await self._call("lookup_catalog", {"catalog": catalog})
            found.extend(normalize_search_response(structured, self.name))

        return found

    async def _call(self, tool: str, arguments: dict) -> dict:
        """Make an MCP call, waiting and trying again if told to slow down.

        A search changes nothing, so repeating it is safe — that is the test
        §10.2 sets for whether an operation may be retried. A rejected or
        malformed request is never retried, because the answer would be the same
        and the attempt would spend a rate-limited call for nothing.
        """
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self._dispatch(tool, arguments)
            except ProviderRateLimited:
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
                delay = _BACKOFF_SECONDS[attempt]
                logger.info(
                    "Rate limited by %s, waiting %.1fs before retrying",
                    self.name,
                    delay,
                )
                await asyncio.sleep(delay)

        raise AssertionError("unreachable")  # pragma: no cover

    async def _dispatch(self, tool: str, arguments: dict) -> dict:
        """Make one MCP call and hand back the useful part of the answer."""
        body = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": {
                    **arguments,
                    "meta": {
                        # Points at a document describing what our agent can do.
                        
                        "ucp-agent": {"profile": self.agent_profile_url},
                        # Lets the provider recognise a retry of the same
                        
                        "idempotency-key": str(uuid.uuid4()),
                    },
                },
            },
        }

        try:
            response = await self._client.post(
                self.endpoint, json=body, headers=_HEADERS, timeout=self._timeout
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(self.name, "the catalog did not answer in time") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429:
                raise ProviderRateLimited(self.name, "too many requests") from exc
            if status >= 500:
                raise ProviderUnavailable(self.name, f"server error {status}") from exc
            raise ProviderRejected(self.name, f"request refused ({status})") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(self.name, "could not be reached") from exc

        payload = response.json()

       
        if "error" in payload:
            detail = payload["error"]
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            raise ProviderRejected(self.name, message or "unknown error")

        return (payload.get("result") or {}).get("structuredContent") or {}


        