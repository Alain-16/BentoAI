from enum import Enum

from bentoai.modules.commerce.dtos import CandidateProduct, ProductSearchQuery


class ProviderCapability(str, Enum):

    CATALOG_SEARCH = "catalog_search"
    CATALOG_LOOKUP = "catalog_lookup"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"
    ORDERS = "order"


class ProviderError(Exception):

    def __init__(self,provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.reason = message


class ProviderTimeout(ProviderError):
    """ the provider didn't answer"""


class ProviderUnavailable(ProviderError):
    """The provider is down or unreachable."""


class ProviderRateLimited(ProviderError):
    """We are calling too often."""


class ProviderRejected(ProviderError):
    """The provider understood us and said no — our request was wrong."""


class CapabilityNotSupported(ProviderError):
    """This provider cannot do that at all."""


class CommerceProvider:

    name: str = "unnamed"
    capabilities: frozenset[ProviderCapability] = frozenset()

    def supports(self, capability:ProviderCapability) -> bool:
        return capability in self.capabilities

    def _unsupported(self, capability: ProviderCapability) -> CapabilityNotSupported:
        return CapabilityNotSupported(self.name, f"cannot {capability.value}")

    async def search_products(
            self,query:ProductSearchQuery
    ) -> list[CandidateProduct]:

        raise self._unsupported(ProviderCapability.CATALOG_SEARCH)

    async def lookup_products(self, ids: list[str], *, ships_to_country: str | None = None, currency:str | None = None) -> list[CandidateProduct]:
        raise self._unsupported(ProviderCapability.CATALOG_LOOKUP)

    async def get_product(
        self,
        product_id: str,
        *,
        ships_to_country: str | None = None,
        currency: str | None = None,
    ) -> CandidateProduct | None:
        raise self._unsupported(ProviderCapability.PRODUCT_DETAIL)

    
    async def create_cart(self, *args, **kwargs):
        raise self._unsupported(ProviderCapability.CART)

    async def update_cart(self, *args, **kwargs):
        raise self._unsupported(ProviderCapability.CART)

    async def create_checkout(self, *args, **kwargs):
        raise self._unsupported(ProviderCapability.CHECKOUT)

    async def get_checkout(self, *args, **kwargs):
        raise self._unsupported(ProviderCapability.CHECKOUT)

    async def get_order(self, *args, **kwargs):
        raise self._unsupported(ProviderCapability.ORDERS)
    