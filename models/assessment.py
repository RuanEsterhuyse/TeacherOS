"""Assessment domain model."""

from pydantic import BaseModel, ConfigDict, Field


class Assessment(BaseModel):
    """A formative or summative measure of student learning."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    assessment_type: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    success_criteria: list[str] = Field(default_factory=list)
