"""Slide Designer structured output."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

SlideType = Literal["title", "objective", "agenda", "background knowledge", "vocabulary", "instructions", "reading", "discussion", "activity", "check for understanding", "writing", "homework", "closure", "assessment", "day divider"]


class SlideSpecificationItem(BaseModel):
    slide_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=1)
    slide_type: SlideType
    title: str = Field(min_length=1)
    student_facing_content: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    speaker_notes: str = ""
    timing: Optional[int] = Field(default=None, ge=0)
    interaction: Optional[str] = None
    teacher_directions: str = ""
    materials: Optional[str] = None
    visual_direction: Optional[str] = None
    image_prompt: Optional[str] = None
    source_references: list[str] = Field(default_factory=list)
    fidelity_classification: Literal["source_required", "source_derived", "teacheros_added"]

    @model_validator(mode="after")
    def validate_semantic_timing(self):
        if self.slide_type != "day divider" and self.timing == 0:
            raise ValueError("instructional slide timing must be positive when provided")
        return self


class SlideSpecification(BaseModel):
    request_id: str
    slides: list[SlideSpecificationItem]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_and_continuous(self):
        ids = [s.slide_id for s in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("slide IDs must be unique")
        if [s.sequence_number for s in self.slides] != list(range(1, len(self.slides) + 1)):
            raise ValueError("slide sequence numbers must be continuous and ordered")
        return self
