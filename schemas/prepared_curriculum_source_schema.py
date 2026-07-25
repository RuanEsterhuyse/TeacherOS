"""Curriculum-agnostic prepared source contracts.

The bundle is a deterministic retrieval artifact. It contains only source
material assigned to one lesson and does not perform instructional design.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.curriculum_intelligence_schema import (
    BuildManifest,
    CurriculumLesson,
    MappingMethod,
    MappingReviewStatus,
    ReadinessState,
    ResolutionStatus,
    SourceProvenance,
    ValidationFinding,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreparedSourceBundleReference(StrictModel):
    """Small optional link from an existing preparation artifact."""

    lesson_id: str = Field(min_length=1)
    bundle_digest: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)


class CurriculumReference(StrictModel):
    reference_system: str = Field(min_length=1)
    value: str = Field(min_length=1)


class VerifiedSourceCoordinate(StrictModel):
    coordinate_system: str = Field(min_length=1)
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)


class PreparedResourceSummary(StrictModel):
    resource_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    stored_checksum: str = Field(min_length=1)
    observed_checksum: Optional[str] = None
    source_version: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    source_available: bool
    current: bool
    warnings: list[str] = Field(default_factory=list)


class PreparedSourceSegment(StrictModel):
    segment_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    segment_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    exact_text: str = Field(min_length=1)
    resource_page_ids: list[str] = Field(min_length=1)
    provenance: list[SourceProvenance] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class CoordinateMappingProvenance(StrictModel):
    mapping_id: str = Field(min_length=1)
    reference_system: str = Field(min_length=1)
    reference_value: str = Field(min_length=1)
    target_coordinate_system: str = Field(min_length=1)
    target_pdf_start_page: int = Field(ge=0)
    target_pdf_end_page: int = Field(ge=0)
    target_display_start_page: int = Field(ge=1)
    target_display_end_page: int = Field(ge=1)
    target_segment_ids: list[str] = Field(min_length=1)
    mapping_method: MappingMethod
    review_status: MappingReviewStatus
    mapping_version: str = Field(min_length=1)
    resource_checksum: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    reviewer_type: str = Field(min_length=1)
    reviewer_note: str = Field(min_length=1)
    provenance: list[SourceProvenance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PreparedSourceAssignment(StrictModel):
    assignment_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    assignment_type: str = Field(min_length=1)
    instructional_purpose: str = Field(min_length=1)
    required_status: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_identity: str = Field(min_length=1)
    original_curriculum_references: list[CurriculumReference] = Field(
        default_factory=list
    )
    verified_coordinates: list[VerifiedSourceCoordinate] = Field(
        default_factory=list
    )
    text_segment_ids: list[str] = Field(default_factory=list)
    source_segments: list[PreparedSourceSegment] = Field(default_factory=list)
    provenance: list[SourceProvenance] = Field(default_factory=list)
    coordinate_mapping_provenance: list[
        CoordinateMappingProvenance
    ] = Field(default_factory=list)
    resolution_status: ResolutionStatus
    available: bool
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class PreparedBundleBuildInputs(StrictModel):
    curriculum_lesson_digest: str = Field(min_length=1)
    resource_digest: str = Field(min_length=1)
    assignment_digest: str = Field(min_length=1)
    segment_digest: str = Field(min_length=1)
    coordinate_mapping_digest: str = Field(min_length=1)
    source_build_manifest_digest: str = Field(min_length=1)
    intelligence_schema_version: str = Field(min_length=1)
    bundle_schema_version: str = Field(min_length=1)
    bundle_builder_version: str = Field(min_length=1)


class PreparedCurriculumSourceBundle(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    curriculum_lesson: CurriculumLesson
    resource_summaries: list[PreparedResourceSummary]
    required_assignments: list[PreparedSourceAssignment]
    optional_assignments: list[PreparedSourceAssignment]
    resolved_source_segments: list[PreparedSourceSegment]
    unresolved_assignments: list[str] = Field(default_factory=list)
    readiness_state: ReadinessState
    blockers: list[ValidationFinding] = Field(default_factory=list)
    warnings: list[ValidationFinding] = Field(default_factory=list)
    source_build_manifest: BuildManifest
    build_inputs: PreparedBundleBuildInputs
    bundle_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


__all__ = [
    "CoordinateMappingProvenance",
    "CurriculumReference",
    "PreparedBundleBuildInputs",
    "PreparedCurriculumSourceBundle",
    "PreparedResourceSummary",
    "PreparedSourceAssignment",
    "PreparedSourceBundleReference",
    "PreparedSourceSegment",
    "VerifiedSourceCoordinate",
]
