"""Homework domain model."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Homework(BaseModel):
    """Work assigned for completion outside the lesson."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    due_date: Optional[date] = None
