import logging
from decimal import Decimal

from bentoai.modules.commerce.dtos import (
    Availability,
    CandidateProduct,
    MerchantOffer,
)

logger = logging.getLogger(__name__)


# Most currencies split into hundredths, so 69900 means 699.00. A few do not —
# 5000 JPY is five thousand yen, not fifty. Dividing everything by a hundred
# would quietly make those baskets a hundred times too cheap.
ZERO_DECIMAL_CURRENCIES = frozenset(
    {"BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF",
     "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}
)


def money_from_minor_units(amount: int | str, currency: str) -> Decimal:
    """Turn a whole number of the smallest currency unit into a real amount."""
    exponent = 0 if currency.upper() in ZERO_DECIMAL_CURRENCIES else 2
    # scaleb shifts the decimal point without ever going through a float, so the
    # value stays exact.
    return Decimal(str(amount)).scaleb(-exponent)


def normalize_search_response(structured: dict, provider: str) -> list[CandidateProduct]:
    """Convert a catalog search response into candidates."""
    candidates: list[CandidateProduct] = []

    for raw in structured.get("products") or []:
        product = normalize_product(raw, provider)
        if product is not None:
            candidates.append(product)

    return candidates


def normalize_product(raw: dict, provider: str) -> CandidateProduct | None:
    """Convert one product. Returns None if it cannot be used."""
    product_id = raw.get("id")
    title = raw.get("title")

    if not product_id or not title:
        # No identifier or no name means we could never show it or fetch it
        # again. Dropping it is better than carrying a broken record forward.
        logger.debug("Skipping a product with no id or title from %s", provider)
        return None

    offers = [
        offer
        for offer in (normalize_offer(v, provider) for v in raw.get("variants") or [])
        if offer is not None
    ]

    if not offers:
        # A product nobody is selling is not a candidate.
        return None

    description = (raw.get("description") or {}).get("plain")
    rating = raw.get("rating") or {}

    return CandidateProduct(
        provider=provider,
        source_product_id=product_id,
        title=title,
        description=description,
        rating_value=rating.get("value"),
        rating_count=rating.get("count"),
        attributes=_attributes(raw.get("metadata") or {}),
        image_urls=[m["url"] for m in raw.get("media") or [] if m.get("url")],
        offers=offers,
    )


def normalize_offer(variant: dict, provider: str) -> MerchantOffer | None:
    """Convert one merchant's offer. Returns None if it cannot be used."""
    variant_id = variant.get("id")
    price = variant.get("price") or {}
    amount = price.get("amount")
    currency = price.get("currency")

    if not variant_id or amount is None or not currency:
        # Without a price there is nothing to compare, budget, or buy.
        return None

    seller = variant.get("seller") or {}
    media = variant.get("media") or []

    return MerchantOffer(
        provider=provider,
        source_variant_id=variant_id,
        merchant_name=seller.get("name") or "Unknown merchant",
        merchant_domain=seller.get("domain") or "",
        merchant_external_id=seller.get("id"),
        price_amount=money_from_minor_units(amount, currency),
        currency=currency.upper(),
        availability=_availability(variant.get("availability")),
        condition=variant.get("condition") or [],
        product_url=variant.get("url"),
        checkout_url=variant.get("checkout_url"),
        supports_native_checkout=bool(
            (variant.get("eligible") or {}).get("native_checkout")
        ),
        image_url=media[0]["url"] if media and media[0].get("url") else None,
    )


def _availability(raw: dict | None) -> Availability:
    """Read stock status, keeping "we do not know" separate from "no".
    """
    if not raw or "available" not in raw:
        return Availability.UNKNOWN
    return Availability.IN_STOCK if raw["available"] else Availability.OUT_OF_STOCK


def _attributes(metadata: dict) -> dict[str, str]:
    """Keep the provider's free-text descriptions as they are.


    """
    attributes: dict[str, str] = {}

    for key in ("top_features", "tech_specs"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            attributes[key] = value

    selling_points = metadata.get("unique_selling_points")
    if isinstance(selling_points, list) and selling_points:
        attributes["unique_selling_points"] = "\n".join(str(p) for p in selling_points)

    return attributes