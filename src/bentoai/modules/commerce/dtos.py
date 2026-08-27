from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Availability(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
   
    UNKNOWN = "unknown"


class MerchantOffer(BaseModel):
    """One merchant's offer of a product.


    """

    provider: str
    source_variant_id: str

    merchant_name: str
    merchant_domain: str
    merchant_external_id: str | None = None


    price_amount: Decimal
    currency: str

    availability: Availability
    condition: list[str] = Field(default_factory=list)

    product_url: str | None = None
    checkout_url: str | None = None

    supports_native_checkout: bool = False

    image_url: str | None = None


class CandidateProduct(BaseModel):
    """A product being considered for one requirement (§5.5)."""

    provider: str
    source_product_id: str

    title: str
    description: str | None = None

    rating_value: float | None = None
    rating_count: int | None = None

  
    attributes: dict[str, str] = Field(default_factory=dict)

  
    image_urls: list[str] = Field(default_factory=list)

    offers: list[MerchantOffer] = Field(default_factory=list)

    @property
    def cheapest_offer(self) -> MerchantOffer | None:
        available = [o for o in self.offers if o.availability is Availability.IN_STOCK]
        return min(available, key=lambda o: o.price_amount) if available else None


class ProductSearchQuery(BaseModel):
    """One search, in provider-independent terms.

    """

    query: str
    ships_to_country: str | None = None
    currency: str | None = None
    available_only: bool = True
    limit: int = 20