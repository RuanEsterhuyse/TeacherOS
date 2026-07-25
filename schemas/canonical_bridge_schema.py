"""Inspection contracts for the read-only canonical bridge."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComparisonStatus(str, Enum):
    EXACT_MATCH = "exact_match"
    EQUIVALENT_SOURCE_CONTENT = "equivalent_source_content"
    CURRENT_ONLY_CONTENT = "current_only_content"
    BUNDLE_ONLY_CONTENT = "bundle_only_content"
    UNSUPPORTED_BY_VERIFIED_SOURCES = "unsupported_by_verified_sources"
    POSSIBLE_UNPROVEN_CONTENT = "possible_hallucination_or_unproven_content"


class CanonicalFieldComparison(StrictModel):
    field: str = Field(min_length=1)
    status: ComparisonStatus
    current_value: Any = None
    bundle_derived_value: Any = None
    notes: list[str] = Field(default_factory=list)


class CanonicalBridgeComparison(StrictModel):
    lesson_id: str = Field(min_length=1)
    bundle_digest: str = Field(min_length=1)
    current_source_digest: str = Field(min_length=1)
    bundle_derived_source_digest: str = Field(min_length=1)
    comparisons: list[CanonicalFieldComparison]
    bundle_fields_populated: list[str]
    bundle_fields_missing: list[str]
    unsupported_instructional_fields: list[str]
    possible_unproven_current_fields: list[str]
    structural_differences: list[str]
    comparison_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


__all__ = [
    "CanonicalBridgeComparison",
    "CanonicalFieldComparison",
    "ComparisonStatus",
]
