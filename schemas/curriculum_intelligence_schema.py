"""Curriculum-agnostic source intelligence contracts.

These models describe source documents and their relationships before any
instructional design or canonical lesson generation occurs.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadinessState(str, Enum):
    REGISTERED = "registered"
    EXTRACTED = "extracted"
    INDEXED = "indexed"
    MAPPED = "mapped"
    PARTIALLY_READY = "partially_ready"
    SOURCE_READY = "source_ready"


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    PARTIAL = "partial"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class IndexingStatus(str, Enum):
    PENDING = "pending"
    INDEXED = "indexed"
    PARTIAL = "partial"
    FAILED = "failed"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"
    NOT_REQUIRED = "not_required"


class MappingReviewStatus(str, Enum):
    PROPOSED = "proposed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    STALE = "stale"


class MappingMethod(str, Enum):
    EXPLICIT_DOCUMENT_LABEL = "explicit_document_label"
    VERIFIED_OFFSET = "verified_offset"
    SECTION_HEADING_MATCH = "section_heading_match"
    HUMAN_REVIEWED_OVERRIDE = "human_reviewed_override"
    ADAPTER_RULE = "adapter_rule"
    IMPORTED_PAGE_MAP = "imported_page_map"


class FindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationFinding(StrictModel):
    code: str = Field(min_length=1)
    severity: FindingSeverity
    message: str = Field(min_length=1)
    reference_id: Optional[str] = None


class SourceCoordinate(StrictModel):
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


class SourceProvenance(StrictModel):
    resource_id: str = Field(min_length=1)
    resource_version: str = Field(min_length=1)
    resource_checksum: str = Field(min_length=1)
    pdf_page_number: Optional[int] = Field(default=None, ge=0)
    display_page_number: Optional[int] = Field(default=None, ge=1)
    printed_page_label: Optional[str] = None
    document_page_label: Optional[str] = None
    segment_id: Optional[str] = None
    section_path: list[str] = Field(default_factory=list)
    start_character_offset: Optional[int] = Field(default=None, ge=0)
    end_character_offset: Optional[int] = Field(default=None, ge=0)
    extraction_method: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Curriculum(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: Optional[str] = None
    edition: Optional[str] = None
    grade_or_course: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    unit_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    adapter_id: str = Field(min_length=1)
    schema_version: str = "1.0"


class InstructionalResource(StrictModel):
    id: str = Field(min_length=1)
    curriculum_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    file_size: int = Field(ge=0)
    page_count: int = Field(ge=0)
    resource_version: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    extraction_status: ExtractionStatus
    indexing_status: IndexingStatus
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourcePage(StrictModel):
    id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    pdf_page_number: int = Field(ge=0)
    display_page_number: int = Field(ge=1)
    printed_page_label: Optional[str] = None
    document_page_label: Optional[str] = None
    raw_text: str
    normalized_text: str
    headings: list[str] = Field(default_factory=list)
    text_blocks: list[SourceCoordinate] = Field(default_factory=list)
    extraction_method: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    extraction_confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coordinates_are_distinct(self) -> "ResourcePage":
        if self.display_page_number != self.pdf_page_number + 1:
            raise ValueError(
                "display page must be one greater than zero-based PDF page"
            )
        return self


class CurriculumUnit(StrictModel):
    id: str = Field(min_length=1)
    curriculum_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    lesson_ids: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    essential_questions: list[str] = Field(default_factory=list)
    linked_resource_ids: list[str] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class CurriculumConcept(StrictModel):
    id: str = Field(min_length=1)
    curriculum_id: str = Field(min_length=1)
    concept_type: Literal[
        "standard",
        "objective",
        "essential_question",
        "vocabulary",
        "skill",
        "theme",
        "character",
        "setting",
        "assessment_focus",
    ]
    label: str = Field(min_length=1)
    description: Optional[str] = None
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class TextSegment(StrictModel):
    id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_page_ids: list[str] = Field(min_length=1)
    segment_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    exact_text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    section_path: list[str] = Field(default_factory=list)
    paragraph_reference: Optional[str] = None
    start_character_offset: Optional[int] = Field(default=None, ge=0)
    end_character_offset: Optional[int] = Field(default=None, ge=0)
    source_provenance: list[SourceProvenance] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class SourceCoordinateMapping(StrictModel):
    id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    assignment_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    resource_checksum: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    reference_system: str = Field(min_length=1)
    reference_value: str = Field(min_length=1)
    target_coordinate_system: str = Field(min_length=1)
    target_pdf_start_page: int = Field(ge=0)
    target_pdf_end_page: int = Field(ge=0)
    target_display_start_page: int = Field(ge=1)
    target_display_end_page: int = Field(ge=1)
    target_segment_ids: list[str] = Field(min_length=1)
    mapping_method: MappingMethod
    confidence: float = Field(ge=0, le=1)
    review_status: MappingReviewStatus
    reviewer_type: Literal["human", "system", "import"]
    reviewer_note: str = Field(min_length=1)
    created_at: datetime
    mapping_version: str = Field(min_length=1)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def target_coordinates_are_consistent(self) -> "SourceCoordinateMapping":
        if self.target_pdf_end_page < self.target_pdf_start_page:
            raise ValueError("mapping PDF range ends before it starts")
        if self.target_display_end_page < self.target_display_start_page:
            raise ValueError("mapping display range ends before it starts")
        if self.target_display_start_page != self.target_pdf_start_page + 1:
            raise ValueError("mapping start coordinate systems disagree")
        if self.target_display_end_page != self.target_pdf_end_page + 1:
            raise ValueError("mapping end coordinate systems disagree")
        return self


class ResourceAssignment(StrictModel):
    id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    assignment_type: Literal[
        "defines_lesson",
        "assigned_reading",
        "background_reading",
        "activity",
        "assessment",
        "exit_ticket",
        "homework",
        "vocabulary_reference",
        "teacher_reference",
        "visual_resource",
        "license_reference",
    ]
    title: str = Field(min_length=1)
    instructional_purpose: str = Field(min_length=1)
    printed_page_references: list[str] = Field(default_factory=list)
    pdf_page_numbers: list[int] = Field(default_factory=list)
    display_page_numbers: list[int] = Field(default_factory=list)
    section_references: list[str] = Field(default_factory=list)
    document_labels: list[str] = Field(default_factory=list)
    story_relative_page_references: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)
    coordinate_mapping_ids: list[str] = Field(default_factory=list)
    required_status: Literal["required", "optional"]
    resolution_status: ResolutionStatus
    extraction_status: ExtractionStatus
    confidence: float = Field(ge=0, le=1)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def resolved_assignments_require_provenance(
        self,
    ) -> "ResourceAssignment":
        if self.resolution_status == ResolutionStatus.RESOLVED:
            if not self.source_provenance or not self.segment_ids:
                raise ValueError(
                    "resolved assignments require segments and provenance"
                )
        return self


class CurriculumLesson(StrictModel):
    id: str = Field(min_length=1)
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    grade_or_course: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    title: str = Field(min_length=1)
    assignment_ids: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    assessment_references: list[str] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    readiness_state: ReadinessState
    warnings: list[str] = Field(default_factory=list)


class ReadinessReport(StrictModel):
    lesson_id: str = Field(min_length=1)
    state: ReadinessState
    achieved_states: list[ReadinessState] = Field(default_factory=list)
    required_assignment_count: int = Field(ge=0)
    resolved_required_assignment_count: int = Field(ge=0)
    blockers: list[ValidationFinding] = Field(default_factory=list)
    warnings: list[ValidationFinding] = Field(default_factory=list)


class BuildManifest(StrictModel):
    build_id: str = Field(min_length=1)
    schema_version: str = "1.0"
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    curriculum_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    resource_checksums: dict[str, str] = Field(default_factory=dict)
    stale_resource_ids: list[str] = Field(default_factory=list)
    snapshot_digest: str = Field(min_length=1)


__all__ = [
    "BuildManifest",
    "Curriculum",
    "CurriculumConcept",
    "CurriculumLesson",
    "CurriculumUnit",
    "ExtractionStatus",
    "FindingSeverity",
    "IndexingStatus",
    "InstructionalResource",
    "MappingMethod",
    "MappingReviewStatus",
    "ReadinessReport",
    "ReadinessState",
    "ResolutionStatus",
    "ResourceAssignment",
    "ResourcePage",
    "SourceCoordinate",
    "SourceCoordinateMapping",
    "SourceProvenance",
    "TextSegment",
    "ValidationFinding",
]
