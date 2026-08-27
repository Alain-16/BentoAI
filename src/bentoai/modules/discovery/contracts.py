from pydantic import Field, BaseModel


class RequirementQueries(BaseModel):

    requirement_index: int = Field(description="The number shown beside the requirement in the list")

    queries: list[str] = Field(description="One to three search phrases for this requirement")


class DiscoveryPlan(BaseModel):

    searches: list[RequirementQueries] = Field(default_factory=list)

    ships_to_country: str | None = Field(default=None, description="Two-letter country code for the customer's location, if known")