"""Slide domain model."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Slide(BaseModel):
    """A renderer-independent presentation slide specification."""

    model_config = ConfigDict(extra="forbid")

    slide_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    student_content: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    speaker_notes: str = ""
    timing: Optional[int] = Field(
        default=None,
        gt=0,
        description="Estimated slide duration in minutes.",
    )
    interaction: Optional[str] = None
    layout_type: str = Field(min_length=1)
    visual_instructions: Optional[str] = None
    image_prompt: Optional[str] = None
    source_references: list[str] = Field(default_factory=list)
