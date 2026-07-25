"""Contracts for isolated, AI-generated phase teacher support."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.curriculum_intelligence_schema import ValidationFinding
from schemas.instructional_relationship_graph_schema import GraphProvenance


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TeacherSupportType(str, Enum):
    TEACHER_EXPLANATION = "teacher_explanation"
    ANTICIPATED_MISCONCEPTIONS = "anticipated_misconceptions"
    FACILITATION_NOTES = "facilitation_notes"
    CHECKS_FOR_UNDERSTANDING = "checks_for_understanding"
    LANGUAGE_SUPPORTS = "language_supports"
    DIFFERENTIATION_SUPPORTS = "differentiation_supports"


class TeacherSupportOrigin(str, Enum):
    AI_GENERATED = "ai_generated_teacher_support"


class TeacherSupportReviewStatus(str, Enum):
    DRAFT_UNREVIEWED = "draft_unreviewed"


class TeacherSupportGenerationStatus(str, Enum):
    GENERATED_VALID = "generated_valid"
    CACHE_HIT_VALID = "cache_hit_valid"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    RESPONSE_INVALID = "response_invalid"
    VALIDATION_BLOCKED = "validation_blocked"


class TeacherSupportContextEntity(StrictModel):
    node_id: str = Field(min_length=1)
    source_identifier: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    exact_content: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: list[GraphProvenance] = Field(min_length=1)


class TeacherSupportQuestionContext(StrictModel):
    node_id: str = Field(min_length=1)
    source_identifier: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    question_type: Optional[str] = None
    prompt_form: str = Field(min_length=1)
    answer_node_ids: list[str] = Field(default_factory=list)
    source_answers: list[str] = Field(default_factory=list)
    provenance: list[GraphProvenance] = Field(min_length=1)


class PhaseTeacherSupportContext(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    phase_id: str = Field(min_length=1)
    phase_node_id: str = Field(min_length=1)
    phase_title: str = Field(min_length=1)
    phase_sequence: int = Field(ge=1)
    explicit_duration_minutes: Optional[int] = Field(default=None, ge=0)
    grouping: list[str] = Field(default_factory=list)
    prepared_bundle_digest: str = Field(min_length=1)
    instruction_plan_digest: str = Field(min_length=1)
    relationship_graph_digest: str = Field(min_length=1)
    teacher_actions: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    student_actions: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    objectives: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    standards: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    questions: list[TeacherSupportQuestionContext] = Field(
        default_factory=list
    )
    readings: list[TeacherSupportContextEntity] = Field(default_factory=list)
    activities: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    assignments: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    resources: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    source_segments: list[TeacherSupportContextEntity] = Field(
        default_factory=list
    )
    warnings: list[ValidationFinding] = Field(default_factory=list)
    excluded_relationships: list[str] = Field(default_factory=list)
    context_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


class GeneratedTeacherSupportItem(StrictModel):
    support_type: TeacherSupportType
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    intended_use: str = Field(min_length=1)
    linked_phase_ids: list[str] = Field(min_length=1)
    linked_objective_ids: list[str] = Field(default_factory=list)
    linked_question_ids: list[str] = Field(default_factory=list)
    linked_activity_ids: list[str] = Field(default_factory=list)
    linked_reading_ids: list[str] = Field(default_factory=list)
    linked_resource_ids: list[str] = Field(default_factory=list)
    linked_source_segment_ids: list[str] = Field(default_factory=list)
    evidence_summary: str = Field(min_length=1)
    origin: TeacherSupportOrigin
    review_status: TeacherSupportReviewStatus
    warnings: list[str] = Field(default_factory=list)


class GeneratedPhaseTeacherSupport(StrictModel):
    phase_id: str = Field(min_length=1)
    source_context_digest: str = Field(min_length=1)
    support_sections: list[GeneratedTeacherSupportItem] = Field(min_length=1)


class PhaseTeacherSupportItem(GeneratedTeacherSupportItem):
    support_id: str = Field(min_length=1)


class PhaseTeacherSupportContextReference(StrictModel):
    context_digest: str = Field(min_length=1)
    context_artifact: str = Field(min_length=1)
    phase_node_id: str = Field(min_length=1)
    included_node_ids: list[str] = Field(default_factory=list)


class TeacherSupportGenerationMetadata(StrictModel):
    cache_key: str = Field(min_length=1)
    input_context_digest: str = Field(min_length=1)
    prompt_contract_digest: str = Field(min_length=1)
    raw_response_digest: str = Field(min_length=1)
    parsed_response_digest: str = Field(min_length=1)
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(ge=0)
    validation_result: str = Field(min_length=1)
    provider_usage: dict[str, Any] = Field(default_factory=dict)


class PhaseTeacherSupportDraft(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    phase_id: str = Field(min_length=1)
    phase_title: str = Field(min_length=1)
    instruction_plan_digest: str = Field(min_length=1)
    relationship_graph_digest: str = Field(min_length=1)
    prepared_bundle_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"
    prompt_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    generated_at: datetime
    generation_status: TeacherSupportGenerationStatus
    review_status: TeacherSupportReviewStatus
    content_origin: TeacherSupportOrigin
    source_context: PhaseTeacherSupportContextReference
    support_sections: list[PhaseTeacherSupportItem] = Field(min_length=1)
    warnings: list[ValidationFinding] = Field(default_factory=list)
    blockers: list[ValidationFinding] = Field(default_factory=list)
    generation_metadata: TeacherSupportGenerationMetadata
    content_digest: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class PhaseTeacherSupportValidationReport(StrictModel):
    status: str = Field(pattern="^(pass|pass_with_warnings|fail)$")
    phase_id: str = Field(min_length=1)
    context_digest: str = Field(min_length=1)
    draft_digest: Optional[str] = None
    findings: list[ValidationFinding] = Field(default_factory=list)
    validated_support_types: list[TeacherSupportType] = Field(
        default_factory=list
    )
    validation_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    validator_version: str = "1.0"


__all__ = [
    "GeneratedPhaseTeacherSupport",
    "GeneratedTeacherSupportItem",
    "PhaseTeacherSupportContext",
    "PhaseTeacherSupportContextReference",
    "PhaseTeacherSupportDraft",
    "PhaseTeacherSupportItem",
    "PhaseTeacherSupportValidationReport",
    "TeacherSupportContextEntity",
    "TeacherSupportGenerationMetadata",
    "TeacherSupportGenerationStatus",
    "TeacherSupportOrigin",
    "TeacherSupportQuestionContext",
    "TeacherSupportReviewStatus",
    "TeacherSupportType",
]
