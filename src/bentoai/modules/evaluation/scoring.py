import logging
from dataclasses import dataclass, field
from bentoai.modules.commerce.dtos import CandidateProduct
from bentoai.modules.evaluation.contracts import (
    FitLevel,Confidence,CandidateAssessment
)

from bentoai.modules.evaluation.filtering import cheapest_purchasable

logger = logging.getLogger(__name__)


WEIGHT_REQUIREMENT=0.25
WEIGHT_QUALITY=0.25
WEIGHT_PRICE=0.25
WEIGHT_PREFERENCE=0.25

FIT_VALUES = {FitLevel.HIGH: 1.0, FitLevel.MEDIUM: 0.6, FitLevel.LOW: 0.2}

CONFIDENCE_VALUES = {Confidence.HIGH: 1.0, Confidence.MEDIUM: 0.6, Confidence.LOW: 0.2}

NEUTRAL = 0.5

RATING_CONFIDENCE_K= 50


@dataclass
class ScoredCandidate:
    """One product, ranked, with the reasoning kept attached."""

    candidate: CandidateProduct
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    trade_offs: list[str] = field(default_factory=list)
    reason: str = ""


def score_candidates(
    candidates: list[CandidateProduct],
    assessments: list[CandidateAssessment],
) -> list[ScoredCandidate]:
    """Rank one requirement's candidates, best first.
    """
    if not candidates:
        return []

    
    by_index: dict[int, CandidateAssessment] = {}
    for assessment in assessments:
        if 1 <= assessment.candidate_index <= len(candidates):
            by_index[assessment.candidate_index] = assessment
        else:
            logger.warning(
                "Ignoring assessment for product %s - only %d were shown",
                assessment.candidate_index,
                len(candidates),
            )

    price_scores = _price_scores(candidates)

    scored: list[ScoredCandidate] = []

    for index, candidate in enumerate(candidates, start=1):
        assessment = by_index.get(index)

        requirement_score = _semantic_score(
            assessment.requirement_fit if assessment else None,
            assessment.confidence if assessment else None,
        )
        preference_score = _semantic_score(
            assessment.preference_fit if assessment else None,
            assessment.confidence if assessment else None,
        )
        quality_score = _quality_score(candidate)
        price_score = price_scores[index - 1]

        total = (
            requirement_score * WEIGHT_REQUIREMENT
            + quality_score * WEIGHT_QUALITY
            + price_score * WEIGHT_PRICE
            + preference_score * WEIGHT_PREFERENCE
        )

        scored.append(
            ScoredCandidate(
                candidate=candidate,
                score=round(total, 4),
                breakdown={
                    "requirement_match": round(requirement_score, 4),
                    "quality": round(quality_score, 4),
                    "price": round(price_score, 4),
                    "preference_match": round(preference_score, 4),
                },
                trade_offs=list(assessment.trade_offs) if assessment else [],
                reason=assessment.reason if assessment else "",
            )
        )

    # Highest score first. Ties break on the cheaper product, because between
    # two things we rate equally the customer keeps the difference.
    scored.sort(key=lambda s: (-s.score, _price_of(s.candidate)))
    return scored


def _semantic_score(fit: FitLevel | None, confidence: Confidence | None) -> float:
   
    if fit is None:
        return NEUTRAL

    raw = FIT_VALUES[fit]
    weight = CONFIDENCE_VALUES.get(confidence or Confidence.MEDIUM, 0.7)
    return NEUTRAL + (raw - NEUTRAL) * weight


def _quality_score(candidate: CandidateProduct) -> float:
    """How good this product looks, from its rating and how many people rated it."""
    if candidate.rating_value is None:
        return NEUTRAL

    # Ratings come back on a 1-to-5 scale, so 1 becomes 0.0 and 5 becomes 1.0.
    normalized = (candidate.rating_value - 1.0) / 4.0
    normalized = min(1.0, max(0.0, normalized))

 
    count = candidate.rating_count or 0
    trust = count / (count + RATING_CONFIDENCE_K)

    return NEUTRAL + (normalized - NEUTRAL) * trust


def _price_scores(candidates: list[CandidateProduct]) -> list[float]:
 
    prices = [_price_of(c) for c in candidates]

    cheapest = min(prices)
    dearest = max(prices)
    spread = dearest - cheapest

    # Everything costs the same, so price tells the customer nothing here.
    if spread <= 0:
        return [NEUTRAL] * len(candidates)

    return [1.0 - (price - cheapest) / spread for price in prices]


def _price_of(candidate: CandidateProduct) -> float:

    offer = cheapest_purchasable(candidate)
    return float(offer.price_amount) if offer else 0.0