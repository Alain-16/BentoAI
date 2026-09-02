"""What the API accepts and returns.

Deliberately separate from the database models. A model describes what is
stored; these describe what a customer may send and is allowed to see. Merging
the two is how internal columns end up published by accident (§10.1).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from bentoai.modules.planner.models import (
    MissionStatus,
    RequirementPriority,
    RequirementStatus,
)


class ActivityEventRead(BaseModel):
    """One line in the activity log."""

    id: uuid.UUID
    at: datetime


    event_type: str

    title: str
    detail: str = ""

    
    notes: list[str] = Field(default_factory=list)


class AnswerSubmission(BaseModel):

    location: str | None = Field(default=None, max_length=255)
    budget_amount: Decimal | None = Field(default=None, gt=0)
    budget_currency: str | None = Field(default=None, min_length=3, max_length=3)


class MissionCreate(BaseModel):
    """What a customer sends to start a mission."""

    goal: str = Field(min_length=3, max_length=2000)
    budget_amount: Decimal | None = Field(default=None, gt=0)
    budget_currency: str = Field(default="CAD", min_length=3, max_length=3)
    location: str | None = Field(default=None, max_length=255)


class RequirementRead(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    description: str | None
    priority: RequirementPriority
    status: RequirementStatus
    position: int
    budget_allocation: Decimal | None


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: MissionStatus
    goal: str
    budget_amount: Decimal | None
    budget_currency: str
    location: str | None
    constraints: dict
    preferences: dict
    created_at: datetime
    updated_at: datetime
    

class MissionRunRead(BaseModel):
    """The answer to "please run this mission"."""

    mission_id: uuid.UUID
    status: MissionStatus

    started: bool

    pending_questions: list[dict] = Field(default_factory=list)


class MissionWithPlan(MissionRead):
   

    requirements: list[RequirementRead] = Field(default_factory=list)
    # Surfaced so the workspace can put the question to the customer, rather than
    # silently planning around a gap.
    planning_metadata: dict = Field(default_factory=dict, exclude=True)

    pending_questions: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def missing_information(self) -> list[str]:

        return self.planning_metadata.get("missing_information",[])