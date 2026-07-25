"""Curriculum-agnostic contracts for source-grounded instruction."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.curriculum_intelligence_schema import ValidationFinding


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceFindingCategory(str, Enum):
    EXPLICIT_SOURCE_INSTRUCTION = "explicit_source_instruction"
    EXPLICIT_SOURCE_QUESTION = "explicit_source_question"
    EXPLICIT_SOURCE_OBJECTIVE = "explicit_source_objective"
    EXPLICIT_SOURCE_TIMING = "explicit_source_timing"
    DETERMINISTIC_STRUCTURE = "deterministic_structure"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    LEGACY_GENERATED = "legacy_generated"


class InstructionSourceProvenance(StrictModel):
    assignment_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    segment_ids: list[str] = Field(min_length=1)
    pdf_page_numbers: list[int] = Field(default_factory=list)
    display_page_numbers: list[int] = Field(default_factory=list)
    curriculum_references: list[str] = Field(default_factory=list)
    coordinate_mapping_ids: list[str] = Field(default_factory=list)
    resource_checksum: str = Field(min_length=1)
    resource_version: str = Field(min_length=1)
    extraction_version: str = Field(min_length=1)
    bundle_digest: str = Field(min_length=1)
    start_character_offset: Optional[int] = Field(default=None, ge=0)
    end_character_offset: Optional[int] = Field(default=None, ge=0)
    exact_text_digest: str = Field(min_length=1)


class SourceAuditFinding(StrictModel):
    id: str = Field(min_length=1)
    category: SourceFindingCategory
    label: str = Field(min_length=1)
    exact_text: Optional[str] = None
    provenance: list[InstructionSourceProvenance] = Field(default_factory=list)
    included_in_plan: bool
    notes: list[str] = Field(default_factory=list)


class SourceAction(StrictModel):
    id: str = Field(min_length=1)
    actor: Literal["teacher", "student"]
    exact_text: str = Field(min_length=1)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)


class SourceAnswer(StrictModel):
    id: str = Field(min_length=1)
    exact_text: str = Field(min_length=1)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)


class SourceQuestion(StrictModel):
    id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    question_type: Optional[str] = None
    answers: list[SourceAnswer] = Field(default_factory=list)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class SourceObjective(StrictModel):
    id: str = Field(min_length=1)
    exact_text: str = Field(min_length=1)
    standard_references: list[str] = Field(default_factory=list)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)


class SourceMaterial(StrictModel):
    id: str = Field(min_length=1)
    exact_text: str = Field(min_length=1)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)


class InstructionSequenceReference(StrictModel):
    sequence: int = Field(ge=1)
    phase_id: str = Field(min_length=1)
    assignment_ids: list[str] = Field(default_factory=list)


class SourceGroundedInstructionPhase(StrictModel):
    id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    phase_title: str = Field(min_length=1)
    phase_type: str = Field(min_length=1)
    day_label: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    exact_source_text: str = Field(min_length=1)
    teacher_actions: list[SourceAction] = Field(default_factory=list)
    student_actions: list[SourceAction] = Field(default_factory=list)
    grouping: list[str] = Field(default_factory=list)
    questions: list[SourceQuestion] = Field(default_factory=list)
    activity_assignment_ids: list[str] = Field(default_factory=list)
    homework_assignment_ids: list[str] = Field(default_factory=list)
    referenced_assignment_ids: list[str] = Field(default_factory=list)
    referenced_resource_ids: list[str] = Field(default_factory=list)
    segment_ids: list[str] = Field(min_length=1)
    pdf_page_numbers: list[int] = Field(default_factory=list)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class SourceGroundedInstructionPlan(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    lesson_title: str = Field(min_length=1)
    teacher_guide_digest: str = Field(min_length=1)
    bundle_digest: str = Field(min_length=1)
    total_duration_minutes: Optional[int] = Field(default=None, ge=0)
    instructional_phases: list[SourceGroundedInstructionPhase]
    teacher_preparation: list[SourceAction] = Field(default_factory=list)
    materials: list[SourceMaterial] = Field(default_factory=list)
    objectives: list[SourceObjective] = Field(default_factory=list)
    vocabulary_sequence: list[InstructionSequenceReference] = Field(
        default_factory=list
    )
    reading_sequence: list[InstructionSequenceReference] = Field(
        default_factory=list
    )
    activity_sequence: list[InstructionSequenceReference] = Field(
        default_factory=list
    )
    assessment_sequence: list[InstructionSequenceReference] = Field(
        default_factory=list
    )
    homework_sequence: list[InstructionSequenceReference] = Field(
        default_factory=list
    )
    audit_findings: list[SourceAuditFinding] = Field(default_factory=list)
    warnings: list[ValidationFinding] = Field(default_factory=list)
    blockers: list[ValidationFinding] = Field(default_factory=list)
    provenance: list[InstructionSourceProvenance] = Field(min_length=1)
    digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


__all__ = [
    "InstructionSequenceReference",
    "InstructionSourceProvenance",
    "SourceAction",
    "SourceAnswer",
    "SourceAuditFinding",
    "SourceFindingCategory",
    "SourceGroundedInstructionPhase",
    "SourceGroundedInstructionPlan",
    "SourceMaterial",
    "SourceObjective",
    "SourceQuestion",
]
