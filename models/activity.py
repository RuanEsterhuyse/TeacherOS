"""Activity domain model."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Activity(BaseModel):
    """A student learning activity within a lesson."""

    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    interaction: Optional[str] = None
