"""Curriculum-agnostic contracts for deterministic lesson rendering plans."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.curriculum_intelligence_schema import ValidationFinding
from schemas.instructional_relationship_graph_schema import GraphProvenance


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContentOrigin(str, Enum):
    PUBLISHER_SOURCE = "publisher_source"
    DETERMINISTIC_STRUCTURE = "deterministic_structure"
    AI_GENERATED_TEACHER_SUPPORT = "ai_generated_teacher_support"


class RenderingReadinessStatus(str, Enum):
    SOURCE_READY = "source_ready"
    SOURCE_READY_WITH_SUPPORT = "source_ready_with_support"
    BLOCKED = "blocked"


class SlideType(str, Enum):
    TITLE = "title"
    OBJECTIVES = "objectives"
    AGENDA = "agenda"
    MATERIALS = "materials"
    DAY_DIVIDER = "day_divider"
    CONTEXT = "context"
    BOOK_OR_TEXT_INTRODUCTION = "book_or_text_introduction"
    VOCABULARY = "vocabulary"
    READING_DIRECTIONS = "reading_directions"
    READING_CHUNK = "reading_chunk"
    TEXT_DEPENDENT_QUESTION = "text_dependent_question"
    DISCUSSION = "discussion"
    CHECK_FOR_UNDERSTANDING = "check_for_understanding"
    ACTIVITY_BOOK = "activity_book"
    WRITING = "writing"
    SYNTHESIS = "synthesis"
    ASSESSMENT = "assessment"
    HOMEWORK = "homework"
    TRANSITION = "transition"


class TimingBasis(str, Enum):
    PUBLISHER_EXPLICIT = "publisher_explicit"
    SHARED_PHASE_TIME = "shared_phase_time"
    NOT_SEPARATELY_SPECIFIED = "not_separately_specified"


class TimingScope(str, Enum):
    SLIDE = "slide"
    PHASE = "phase"
    NONE = "none"


class AnswerRevealBehavior(str, Enum):
    SPEAKER_NOTES_ONLY = "speaker_notes_only"
    NOT_AVAILABLE = "not_available"
    SOURCE_ACTIVITY_RESOURCE = "source_activity_resource"
    SEPARATE_FOLLOW_UP_SLIDE = "separate_follow_up_slide"


class RequiredStatus(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class SlideScope(str, Enum):
    LESSON_STRUCTURE = "lesson_structure"
    PHASE = "phase"


class SupportRequirement(str, Enum):
    SKIP = "skip"
    CURRICULUM_ONLY = "curriculum_only"
    GENERATE_OR_REUSE = "generate_or_reuse"
    REUSE_VALID_CACHE = "reuse_valid_cache"


class SupportStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    CURRICULUM_ONLY = "curriculum_only"
    VALID_CACHE = "valid_cache"
    OPTIONAL_UNAVAILABLE = "optional_unavailable"
    INVALID_REJECTED = "invalid_rejected"


class QuestionDisposition(str, Enum):
    STUDENT_VISIBLE = "student_visible"
    TEACHER_NOTES = "teacher_notes"
    OPTIONAL_TEACHER_NOTES = "optional_teacher_notes"
    SOURCE_ACTIVITY_RESOURCE = "source_activity_resource"
    CHECKPOINT = "checkpoint"


class OriginText(StrictModel):
    text: str = Field(min_length=1)
    origin: ContentOrigin
    source_node_ids: list[str] = Field(default_factory=list)
    support_item_ids: list[str] = Field(default_factory=list)


class StudentVisibleContent(StrictModel):
    title: OriginText
    subtitle: Optional[OriginText] = None
    directions: list[OriginText] = Field(default_factory=list)
    statements: list[OriginText] = Field(default_factory=list)
    visible_question_ids: list[str] = Field(default_factory=list)
    reading_cue: Optional[OriginText] = None
    response_format: Optional[OriginText] = None
    footer: Optional[OriginText] = None


class TeacherNotesContent(StrictModel):
    publisher_directions: list[OriginText] = Field(default_factory=list)
    source_answer_ids: list[str] = Field(default_factory=list)
    source_answers: list[OriginText] = Field(default_factory=list)
    facilitation_notes: list[OriginText] = Field(default_factory=list)
    checks_for_understanding: list[OriginText] = Field(default_factory=list)
    language_supports: list[OriginText] = Field(default_factory=list)
    differentiation_supports: list[OriginText] = Field(default_factory=list)
    transition: Optional[OriginText] = None
    support_references: list[str] = Field(default_factory=list)
    provenance_references: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReadingPageReference(StrictModel):
    reference_system: str = Field(min_length=1)
    value: str = Field(min_length=1)
    assignment_id: str = Field(min_length=1)
    verified: bool = True


class VisualAssetRequirement(StrictModel):
    resource_id: Optional[str] = None
    assignment_id: Optional[str] = None
    description: str = Field(min_length=1)
    required: bool = False
    approved_source_only: bool = True
    neutral_placeholder_allowed: bool = True
    warnings: list[str] = Field(default_factory=list)


class SlideSpecification(StrictModel):
    slide_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    phase_id: Optional[str] = None
    scope: SlideScope
    slide_number: int = Field(ge=1)
    slide_type: SlideType
    student_visible_content: StudentVisibleContent
    teacher_notes: TeacherNotesContent = Field(default_factory=TeacherNotesContent)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    timing_basis: TimingBasis
    timing_scope: TimingScope
    reading_pages: list[ReadingPageReference] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    question_ids: list[str] = Field(default_factory=list)
    answer_ids: list[str] = Field(default_factory=list)
    support_item_ids: list[str] = Field(default_factory=list)
    source_node_ids: list[str] = Field(default_factory=list)
    required_or_optional: RequiredStatus = RequiredStatus.REQUIRED
    question_display_behavior: Optional[QuestionDisposition] = None
    answer_reveal_behavior: AnswerRevealBehavior
    layout_hint: str = Field(min_length=1)
    visual_asset_requirements: list[VisualAssetRequirement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class SourceSnapshot(StrictModel):
    prepared_bundle_digest: str = Field(min_length=1)
    instruction_plan_digest: str = Field(min_length=1)
    relationship_graph_digest: str = Field(min_length=1)
    graph_audit_digest: str = Field(min_length=1)
    ordered_support_digests: list[str] = Field(default_factory=list)


class PhaseSupportManifestEntry(StrictModel):
    phase_id: str = Field(min_length=1)
    phase_sequence: int = Field(ge=1)
    requirement: SupportRequirement
    status: SupportStatus
    reason: str = Field(min_length=1)
    cache_key: Optional[str] = None
    draft_digest: Optional[str] = None
    content_digest: Optional[str] = None
    support_item_ids: list[str] = Field(default_factory=list)
    artifact_path: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class PhaseRenderingRecord(StrictModel):
    phase_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    title: str = Field(min_length=1)
    phase_type: str = Field(min_length=1)
    day_label: Optional[str] = None
    source_duration_minutes: Optional[int] = Field(default=None, ge=0)
    required_status: RequiredStatus
    support_requirement: SupportRequirement
    support_status: SupportStatus
    support_draft_digest: Optional[str] = None
    assignment_ids: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    question_ids: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    source_node_ids: list[str] = Field(default_factory=list)
    provenance: list[GraphProvenance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class PhaseCoverageEntry(StrictModel):
    phase_id: str = Field(min_length=1)
    phase_sequence: int = Field(ge=1)
    slide_ids: list[str] = Field(default_factory=list)
    disposition: str = Field(min_length=1)
    covered: bool


class SlideCoverageEntry(StrictModel):
    slide_id: str = Field(min_length=1)
    slide_number: int = Field(ge=1)
    scope: SlideScope
    phase_id: Optional[str] = None
    coverage_reference: str = Field(min_length=1)


class QuestionCoverageEntry(StrictModel):
    question_id: str = Field(min_length=1)
    phase_id: str = Field(min_length=1)
    source_order: int = Field(ge=1)
    source_answer_ids: list[str] = Field(default_factory=list)
    primary_disposition: QuestionDisposition
    slide_ids: list[str] = Field(min_length=1)
    answer_disposition: AnswerRevealBehavior
    reading_boundary: Optional[str] = None
    source_node_ids: list[str] = Field(default_factory=list)
    provenance: list[GraphProvenance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AssignmentCoverageEntry(StrictModel):
    assignment_id: str = Field(min_length=1)
    required_status: RequiredStatus
    phase_ids: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    disposition: str = Field(min_length=1)
    covered: bool


class ResourceCoverageEntry(StrictModel):
    resource_id: str = Field(min_length=1)
    required: bool
    assignment_ids: list[str] = Field(default_factory=list)
    phase_ids: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    disposition: str = Field(min_length=1)
    covered: bool


class LessonRenderingModel(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    lesson_title: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    planner_version: str = Field(min_length=1)
    splitting_policy_version: str = Field(min_length=1)
    support_policy_version: str = Field(min_length=1)
    source_snapshot: SourceSnapshot
    declared_duration_minutes: Optional[int] = Field(default=None, ge=0)
    explicit_phase_duration_minutes: int = Field(ge=0)
    timing_warnings: list[ValidationFinding] = Field(default_factory=list)
    phases: list[PhaseRenderingRecord]
    slides: list[SlideSpecification]
    phase_support_manifest: list[PhaseSupportManifestEntry]
    slide_coverage: list[SlideCoverageEntry]
    phase_coverage: list[PhaseCoverageEntry]
    question_coverage: list[QuestionCoverageEntry]
    assignment_coverage: list[AssignmentCoverageEntry]
    resource_coverage: list[ResourceCoverageEntry]
    provenance: list[GraphProvenance] = Field(default_factory=list)
    warnings: list[ValidationFinding] = Field(default_factory=list)
    blockers: list[ValidationFinding] = Field(default_factory=list)
    readiness_status: RenderingReadinessStatus
    content_digest: str = Field(min_length=1)
    artifact_digest: str = Field(min_length=1)


class LessonRenderingValidationReport(StrictModel):
    status: str = Field(pattern="^(pass|pass_with_warnings|fail)$")
    lesson_id: str = Field(min_length=1)
    model_digest: str = Field(min_length=1)
    findings: list[ValidationFinding] = Field(default_factory=list)
    phase_count: int = Field(ge=0)
    slide_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    validation_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    validator_version: str = "1.0"


__all__ = [
    "AnswerRevealBehavior", "AssignmentCoverageEntry", "ContentOrigin",
    "LessonRenderingModel", "LessonRenderingValidationReport", "OriginText",
    "PhaseCoverageEntry", "PhaseRenderingRecord", "PhaseSupportManifestEntry",
    "QuestionCoverageEntry", "QuestionDisposition", "ReadingPageReference",
    "RenderingReadinessStatus", "RequiredStatus", "ResourceCoverageEntry",
    "SlideCoverageEntry", "SlideScope", "SlideSpecification", "SlideType",
    "SourceSnapshot", "StudentVisibleContent",
    "SupportRequirement", "SupportStatus", "TeacherNotesContent", "TimingBasis",
    "TimingScope", "VisualAssetRequirement",
]
