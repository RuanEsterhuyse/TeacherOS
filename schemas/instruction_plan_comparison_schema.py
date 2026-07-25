"""Deterministic comparison contract for Phase 3B."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstructionComparisonStatus(str, Enum):
    EXACT_MATCH = "exact_match"
    SOURCE_SUPPORTED = "source_supported_content"
    CURRENT_GENERATED = "current_generated_content"
    NOT_REPRODUCIBLE = "not_reproducible_from_verified_curriculum_sources"


class InstructionComparisonItem(StrictModel):
    field: str = Field(min_length=1)
    status: InstructionComparisonStatus
    source_plan_value: Any = None
    current_canonical_value: Any = None
    notes: list[str] = Field(default_factory=list)


class InstructionPlanComparison(StrictModel):
    lesson_id: str = Field(min_length=1)
    plan_digest: str = Field(min_length=1)
    current_source_digest: str = Field(min_length=1)
    comparisons: list[InstructionComparisonItem]
    not_reproducible_current_paths: list[str] = Field(default_factory=list)
    comparison_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


__all__ = [
    "InstructionComparisonItem",
    "InstructionComparisonStatus",
    "InstructionPlanComparison",
]
