"""Vocabulary domain model."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Vocabulary(BaseModel):
    """A lesson-specific vocabulary term."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    context: Optional[str] = None
