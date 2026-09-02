from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

class ConstraintStrength(str, Enum):

    HARD = "hard"
    SOFT = "soft"


class RequirementPriority(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class PlannedConstraint(BaseModel):
    type: str = Field(
        description="What kind of limit this is — space, destination, brand_exclusion"
    )
    value: str = Field(description="The limit itself — 'small', 'Vancouver, BC'")
    strength: ConstraintStrength


class PlannedPreference(BaseModel):
    type: str = Field(
        description="What kind of preference — training_style, quality_level"
    )
    value: str


class PlannedRequirement(BaseModel):
    category: str = Field(
        description="The product category needed, e.g. 'adjustable dumbbells'"
    )
    priority: RequirementPriority
    description: str | None = Field(
        default=None, description="Why this is needed and what would satisfy it"
    )
    
    suggested_budget_allocation: float | None = Field(
        default=None, ge=0, description="Rough share of the budget for this item"
    )

    # How many of this item the customer wants.
    #
    # ge/le are not decoration. A model asked for a number will occasionally
    # return 0, or 500, and pydantic refusing the answer here is cheaper than
    # the basket quietly pricing five hundred t-shirts.
    quantity: int = Field(
        default=1,
        ge=1,
        le=50,
        description="How many of this item to buy. 1 unless the customer said otherwise.",
    )

class ExtractedBudget(BaseModel):

    amount: float = Field(ge=0, description="The number they mentioned")
    currency: str = Field(description="currency code")


class PlanningResult(BaseModel):
    """Everything the Planning Agent returns"""

    goal: str = Field(description="The customer's objective, restated clearly")

    budget: ExtractedBudget | None = Field(default=None,description="only if the customer stated a budget")
    location: str | None = Field(default=None, description="only if the customer said the location")

    constraints: list[PlannedConstraint] = Field(default_factory=list)
    preferences: list[PlannedPreference] = Field(default_factory=list)
    requirements: list[PlannedRequirement] = Field(default_factory=list)

 
    missing_information: list[str] = Field(
        default_factory=list,
        description="Questions worth asking the customer before searching",
    )
    rationale: str | None = Field(
        default=None, description="Brief note on how the plan was arrived at"
    )


class PlanningRequest(BaseModel):
    """What the step hands to the agent."""

    goal: str
    budget_amount: Decimal | None = None
    budget_currency: str = "CAD"
    location: str | None = None