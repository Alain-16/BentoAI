from pydantic import Field, BaseModel


class OptionNote(BaseModel):
    option_index: int = Field(
        description="The number shown beside this option in the list"
    )
    note: str = Field(
        description="One short line on what sets this one apart from the others"
    )

class RequirementChoice(BaseModel):

    requirement_index: int = Field(description="The number shown beside the requirement")

    preferred_option_index: int = Field(
        description="The number of the option you would choose for this requirement"
    )
    notes: list[OptionNote] = Field(
        default_factory=list,
        description="One note per option, so a shopper can tell them apart",
    )
    summary: str = Field(
        description="One sentence on why the preferred one wins for this customer"
    )


class BasketComparison(BaseModel):

    choices: list[RequirementChoice] = Field(default_factory=list)
    