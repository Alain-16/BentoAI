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


class PlanningResult(BaseModel):
    """Everything the Planning Agent returns"""

    goal: str = Field(description="The customer's objective, restated clearly")
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