from enum import Enum
from pydantic import BaseModel, Field


class FitLevel(str, Enum):

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CandidateAssessment(BaseModel):

    candidate_index: int = Field(description="The number shown beside this product in the list")

    requirement_fit: FitLevel = Field(description="Does this actually do the job the requirement describes")

    preference_fit: FitLevel = Field(description="Does it match what the customer said they like")

    confidence: Confidence = Field(description="How sure you are, given how much the listing actually tells you")

    trade_offs: list[str] = Field(
        default_factory=list,
        description="Short plain phrases - what the customer gives up by picking this"
    )
    reason: str = Field(
        description="One sentence a shopper would understand, for showing on the card"
    )

class RequirementEvaluation(BaseModel):
    assessments: list[CandidateAssessment] = Field(default_factory=list)

