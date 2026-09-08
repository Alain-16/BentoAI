"""The hard filter and the scoring engine.

Between them these decide which products a customer ever sees. They are also
where a mistake is silent: a filter rule that rejects too much produces an empty
category, and a scoring weight that is wrong produces a plausible-looking
recommendation that happens to be the wrong one.
"""

from decimal import Decimal

import pytest

from bentoai.modules.commerce.dtos import Availability
from bentoai.modules.evaluation.contracts import (
    CandidateAssessment,
    Confidence,
    FitLevel,
)
from bentoai.modules.evaluation.filtering import RejectionReason, apply_hard_filters
from bentoai.modules.evaluation.scoring import (
    NEUTRAL,
    WEIGHTS_BY_PRIORITY,
    score_candidates,
)
from bentoai.modules.planner.models import MissionPriority, ShoppingMission


@pytest.fixture
def mission():
    def build(budget="200", currency="CAD", constraints=None,
              priority=MissionPriority.BALANCED):
        m = ShoppingMission(
            goal="gym clothes",
            budget_amount=Decimal(budget) if budget else None,
            budget_currency=currency,
            priority=priority,
        )
        m.constraints = constraints or {}
        m.preferences = {}
        return m

    return build


# -- the hard filter --------------------------------------------------------


def test_an_affordable_in_stock_product_passes(mission, make_candidate):
    outcome = apply_hard_filters([make_candidate("Shirt", "47.00")], mission())

    assert len(outcome.accepted) == 1
    assert outcome.tally() == {}


def test_a_product_dearer_than_the_whole_budget_is_rejected(mission, make_candidate):
    outcome = apply_hard_filters([make_candidate("Chair", "400.00")], mission("200"))

    assert outcome.accepted == []
    assert outcome.tally() == {RejectionReason.OVER_BUDGET.value: 1}


def test_quantity_is_priced_as_a_whole_line(mission, make_candidate):
    """Three shirts at 80 break a 200 budget even though one shirt does not."""
    shirts = [make_candidate("Shirt", "80.00")]

    assert len(apply_hard_filters(shirts, mission("200"), 1).accepted) == 1
    assert apply_hard_filters(shirts, mission("200"), 3).accepted == []


def test_an_out_of_stock_product_is_rejected(mission, make_candidate):
    gone = make_candidate("Shirt", "40.00", availability=Availability.OUT_OF_STOCK)

    outcome = apply_hard_filters([gone], mission())

    assert outcome.tally() == {RejectionReason.OUT_OF_STOCK.value: 1}


def test_unknown_stock_is_not_the_same_as_out_of_stock(mission, make_candidate):
    """"We do not know" is not "no".

    §5.7 asks us to reject what is out of stock. Judging the unknown ones is the
    Evaluation Agent's job, and it is told to mark them uncertain - so throwing
    them away here would remove products nobody has established are unavailable.
    """
    unknown = make_candidate("Shirt", "40.00", availability=Availability.UNKNOWN)

    assert len(apply_hard_filters([unknown], mission()).accepted) == 1


def test_a_price_in_another_currency_is_rejected(mission, make_candidate):
    """This rule once emptied an entire mission, so it is worth pinning.

    Comparing 200 USD against a 400 CAD budget by the bare numbers would be
    worse than not checking at all.
    """
    outcome = apply_hard_filters([make_candidate("Shirt", "40.00")], mission(currency="USD"))

    assert outcome.tally() == {RejectionReason.CURRENCY_MISMATCH.value: 1}


def test_a_hard_brand_exclusion_removes_the_product(mission, make_candidate):
    constraints = {"items": [
        {"type": "brand_exclusion", "value": "Bowflex", "strength": "hard"}
    ]}

    outcome = apply_hard_filters(
        [make_candidate("Bowflex SelectTech", "100.00")], mission(constraints=constraints)
    )

    assert outcome.tally() == {RejectionReason.EXCLUDED_BRAND.value: 1}


def test_a_soft_brand_preference_does_not_remove_it(mission, make_candidate):
    """A preference is something they would rather avoid, not something that
    disqualifies. Throwing it away here would overrule the customer silently."""
    constraints = {"items": [
        {"type": "brand_exclusion", "value": "Bowflex", "strength": "soft"}
    ]}

    outcome = apply_hard_filters(
        [make_candidate("Bowflex SelectTech", "100.00")], mission(constraints=constraints)
    )

    assert len(outcome.accepted) == 1


# -- the scoring engine -----------------------------------------------------


def _confident(index, fit=FitLevel.HIGH):
    return CandidateAssessment(
        candidate_index=index,
        requirement_fit=fit,
        preference_fit=fit,
        confidence=Confidence.HIGH,
        reason="",
    )


def test_every_weight_set_sums_to_one():
    """Otherwise two products stop being comparable and scores drift out of 0-1."""
    for name, weights in WEIGHTS_BY_PRIORITY.items():
        assert round(sum(weights), 6) == 1.0, name


def test_an_unrated_product_scores_neutral_not_zero(make_candidate):
    """Nobody has reviewed it. That is unknown, not bad - and zero would bury
    every new or niche product beneath whatever happens to be popular."""
    ranked = score_candidates([make_candidate("New Thing", "40.00")], [_confident(1)])

    assert ranked[0].breakdown["quality"] == NEUTRAL


def test_a_thinly_rated_product_is_pulled_toward_neutral(make_candidate):
    """4.6 from 17 people and 4.9 from 705 are not the same claim."""
    thin = make_candidate("Thin", "40.00", rating=4.6, count=17)
    solid = make_candidate("Solid", "40.00", rating=4.9, count=705)

    ranked = score_candidates([thin, solid], [_confident(1), _confident(2)])
    by_title = {r.candidate.title: r.breakdown["quality"] for r in ranked}

    assert by_title["Thin"] < by_title["Solid"]
    # and the thin one sits much closer to neutral than its raw 4.6 suggests
    assert abs(by_title["Thin"] - NEUTRAL) < abs(by_title["Solid"] - NEUTRAL)


def test_priority_changes_which_product_wins(make_candidate):
    """The whole point of the priority field: it is not decoration."""
    premium = make_candidate("Premium", "180.00", rating=4.9, count=5000)
    budget = make_candidate("Budget", "150.00", rating=3.6, count=12)
    assessments = [_confident(1), _confident(2)]

    assert score_candidates([premium, budget], assessments, "quality")[0].candidate.title == "Premium"
    assert score_candidates([premium, budget], assessments, "value")[0].candidate.title == "Budget"


def test_no_assessments_still_produces_a_full_ranking(make_candidate):
    """The refusal path. One requirement the model would not judge costs its
    own rankings, never the whole mission."""
    products = [make_candidate("A", "40.00"), make_candidate("B", "20.00")]

    ranked = score_candidates(products, [])

    assert len(ranked) == 2
    assert all(r.breakdown["requirement_match"] == NEUTRAL for r in ranked)


def test_an_index_the_model_invented_is_dropped(make_candidate):
    """Guessing which product it meant would attach one product's verdict to
    another, which is worse than losing the verdict."""
    products = [make_candidate("A", "40.00")]

    ranked = score_candidates(products, [_confident(99)])

    assert len(ranked) == 1
    assert ranked[0].breakdown["requirement_match"] == NEUTRAL


def test_low_confidence_pulls_a_verdict_toward_neutral(make_candidate):
    """An unsure "high" must not outrank a confident one."""
    product = [make_candidate("A", "40.00")]

    sure = score_candidates(product, [_confident(1)])[0]
    unsure = score_candidates(product, [CandidateAssessment(
        candidate_index=1, requirement_fit=FitLevel.HIGH, preference_fit=FitLevel.HIGH,
        confidence=Confidence.LOW, reason="")])[0]

    assert sure.breakdown["requirement_match"] > unsure.breakdown["requirement_match"]
    assert unsure.breakdown["requirement_match"] > NEUTRAL
