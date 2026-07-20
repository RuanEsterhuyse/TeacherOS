"""Lesson domain model."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.activity import Activity
from models.assessment import Assessment
from models.homework import Homework
from models.slide import Slide
from models.vocabulary import Vocabulary


class Lesson(BaseModel):
    """A complete, validated lesson package ready for a renderer."""

    model_config = ConfigDict(extra="forbid")

    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(gt=0)
    slides: list[Slide] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    homework: list[Homework] = Field(default_factory=list)
    vocabulary: list[Vocabulary] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def slide_ids_are_unique(self) -> "Lesson":
        """Reject ambiguous packages that contain duplicate slide identifiers."""
        slide_ids = [slide.slide_id for slide in self.slides]
        if len(slide_ids) != len(set(slide_ids)):
            raise ValueError("slide_id values must be unique within a lesson")
        return self
