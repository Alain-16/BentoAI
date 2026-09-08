"""The option pool and the budget solver.

These cover the bug that actually happened: build_option_pool's pool.append was
one level too deep, so a requirement only reached the pool when its cheapest
product was not already one of the two best-scoring. On real data that was never
true, so the pool came back empty and /basket answered "no usable products" with
nothing in the logs to say why.
"""

from decimal import Decimal

from bentoai.modules.deterministicService.basket.optimizer import (
    BEST_SLOTS,
    POOL_SIZE,
    build_option_pool,
    solve,
)
from bentoai.modules.planner.models import RequirementPriority


# -- the pool ---------------------------------------------------------------


def test_every_requirement_reaches_the_pool(make_requirement, make_group):
    """Three requirements in, three groups out.

    This is the regression test for the indentation bug. It passed data where
    the cheapest product IS one of the two best-scoring in every category -
    exactly the shape that made the broken version return nothing.
    """
    groups = [
        make_group(make_requirement("tops", position=0),
                   [("Core Shirt", "47.00", 0.93), ("Gym King Tee", "37.00", 0.91),
                    ("Adapt Tee", "52.00", 0.90)]),
        make_group(make_requirement("bottoms", position=1),
                   [("Nike Form", "54.00", 0.88), ("WETSU", "74.00", 0.87)]),
        make_group(make_requirement("shoes", position=2),
                   [("Nano", "140.00", 0.89), ("Nano White", "119.99", 0.88)]),
    ]

    pool = build_option_pool(groups)

    assert len(pool) == 3, "a requirement disappeared from the pool"


def test_pool_gains_the_cheapest_when_it_is_not_already_there(make_requirement, make_group):
    """Two best by score, plus the cheapest, when the cheapest is distinct."""
    group = make_group(
        make_requirement("tops"),
        [("Expensive Best", "90.00", 0.95),
         ("Dear Second", "80.00", 0.90),
         ("Cheap Third", "20.00", 0.60)],
    )

    options = build_option_pool([group])[0].options

    assert len(options) == POOL_SIZE
    assert options[-1].included_as == "cheapest that passed"
    assert options[-1].price == Decimal("20.00")


def test_pool_stays_short_when_the_cheapest_is_already_best(make_requirement, make_group):
    """No padding. If the cheapest is already in the top two, two is the pool.

    The broken version dropped the whole requirement here instead.
    """
    group = make_group(
        make_requirement("tops"),
        [("Best And Cheapest", "20.00", 0.95),
         ("Second", "80.00", 0.90),
         ("Third", "90.00", 0.60)],
    )

    options = build_option_pool([group])[0].options

    assert len(options) == BEST_SLOTS
    assert all(o.included_as == "best score" for o in options)


def test_a_requirement_with_no_products_is_left_out(make_requirement, make_group):
    groups = [
        make_group(make_requirement("tops", position=0), [("Shirt", "40.00", 0.9)]),
        make_group(make_requirement("bottoms", position=1), []),
    ]

    pool = build_option_pool(groups)

    assert [r.requirement.category for r in pool] == ["tops"]


def test_quantity_reaches_the_options(make_requirement, make_group):
    """price is the unit figure; line_total is what the budget has to survive."""
    group = make_group(make_requirement("tops", quantity=3), [("Shirt", "40.00", 0.9)])

    option = build_option_pool([group])[0].options[0]

    assert option.price == Decimal("40.00")
    assert option.line_total == Decimal("120.00")


# -- the solver -------------------------------------------------------------


def _pool_of(make_requirement, make_group, *specs):
    """specs: (category, priority, [(title, price, score), ...])"""
    groups = [
        make_group(make_requirement(cat, priority=pri, position=i), products)
        for i, (cat, pri, products) in enumerate(specs)
    ]
    return build_option_pool(groups)


def test_a_roomy_budget_takes_the_best(make_requirement, make_group):
    pool = _pool_of(
        make_requirement, make_group,
        ("tops", RequirementPriority.REQUIRED,
         [("Best", "90.00", 0.95), ("Cheap", "20.00", 0.60)]),
    )

    solution = solve(pool, Decimal("500"), {})

    assert solution.feasible
    assert solution.selected[0].option.title == "Best"
    assert solution.total == Decimal("90.00")
    assert solution.remaining == Decimal("410.00")


def test_a_tight_budget_swaps_down_and_stays_under(make_requirement, make_group):
    pool = _pool_of(
        make_requirement, make_group,
        ("tops", RequirementPriority.REQUIRED,
         [("Best", "90.00", 0.95), ("Cheap", "20.00", 0.60)]),
        ("shoes", RequirementPriority.REQUIRED,
         [("Nice", "150.00", 0.95), ("Plain", "60.00", 0.60)]),
    )

    solution = solve(pool, Decimal("100"), {})

    assert solution.feasible
    assert solution.total <= Decimal("100")
    assert len(solution.selected) == 2, "both required items must still be covered"


def test_an_optional_item_is_dropped_before_a_required_one(make_requirement, make_group):
    pool = _pool_of(
        make_requirement, make_group,
        ("shoes", RequirementPriority.REQUIRED, [("Shoes", "80.00", 0.95)]),
        ("socks", RequirementPriority.OPTIONAL, [("Socks", "40.00", 0.95)]),
    )

    solution = solve(pool, Decimal("100"), {})

    chosen = {c.requirement.category for c in solution.selected}
    assert "shoes" in chosen, "a required item must never be dropped for an optional one"
    assert "socks" not in chosen
    assert solution.total <= Decimal("100")


def test_an_unaffordable_plan_is_reported_rather_than_faked(make_requirement, make_group):
    """The customer is told the real number instead of shown an empty page."""
    pool = _pool_of(
        make_requirement, make_group,
        ("shoes", RequirementPriority.REQUIRED, [("Shoes", "120.00", 0.9)]),
        ("tops", RequirementPriority.REQUIRED, [("Shirt", "100.00", 0.9)]),
    )

    solution = solve(pool, Decimal("200"), {})

    assert solution.feasible is False
    assert solution.total == Decimal("220.00")
    assert solution.shortfall == Decimal("20.00")
    assert len(solution.selected) == 2, "the cheapest possible basket is still returned"
    assert any("over the budget" in note for note in solution.notes)


def test_no_budget_means_no_ceiling(make_requirement, make_group):
    pool = _pool_of(
        make_requirement, make_group,
        ("tops", RequirementPriority.REQUIRED,
         [("Expensive", "9000.00", 0.95), ("Cheap", "10.00", 0.50)]),
    )

    solution = solve(pool, None, {})

    assert solution.feasible
    assert solution.selected[0].option.title == "Expensive"
    assert solution.remaining is None


def test_the_models_preference_wins_a_close_call(make_requirement, make_group):
    """A preferred option beats a rival it is within a whisker of."""
    requirement = make_requirement("tops")
    pool = build_option_pool([
        make_group(requirement, [("A", "50.00", 0.90), ("B", "50.00", 0.88)])
    ])

    without = solve(pool, Decimal("500"), {})
    assert without.selected[0].option.title == "A"

    preferred_b = {str(requirement.id): pool[0].options[1].product_id}
    with_preference = solve(pool, Decimal("500"), preferred_b)
    assert with_preference.selected[0].option.title == "B"


def test_quantity_is_counted_against_the_budget(make_requirement, make_group):
    """Three shirts at 80 break a 200 budget even though one shirt does not."""
    pool = _pool_of(
        make_requirement, make_group,
        ("tops", RequirementPriority.REQUIRED, [("Shirt", "80.00", 0.9)]),
    )
    pool[0].requirement.quantity = 3
    for option in pool[0].options:
        object.__setattr__(option, "quantity", 3)

    solution = solve(pool, Decimal("200"), {})

    assert solution.total == Decimal("240.00")
    assert solution.feasible is False
