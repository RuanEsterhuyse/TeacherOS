"""Versioned, curriculum-grounded Teacher Companion and student-slide models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


TEACHING_PACKAGE_SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContentOrigin(str, Enum):
    EXACT_PUBLISHER = "exact_publisher_content"
    CLOSE_PARAPHRASE = "close_publisher_paraphrase"
    STUDENT_ADAPTATION = "student_friendly_adaptation"
    MODEL_ANALYSIS = "model_generated_analysis"
    TEACHER_ENTERED = "teacher_entered_content"
    UNAVAILABLE = "unavailable"


class ReviewStatus(str, Enum):
    VERIFIED = "verified"
    REVIEW_RECOMMENDED = "review_recommended"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class TeachingSourceReference(StrictModel):
    resource_id: str = Field(min_length=1)
    source_document: str = Field(min_length=1)
    stable_source_id: str = Field(min_length=1)
    pdf_page_number: Optional[int] = Field(default=None, ge=0)
    display_page_number: Optional[int] = Field(default=None, ge=1)
    printed_page: Optional[str] = None


class GroundedText(StrictModel):
    id: str = Field(min_length=1)
    text: str
    origin: ContentOrigin
    source_references: list[TeachingSourceReference] = Field(
        default_factory=list
    )
    transformation_type: str = Field(min_length=1)
    cognitive_demands: list[str] = Field(default_factory=list)
    required_conditions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus

    @model_validator(mode="after")
    def source_content_has_references(self) -> "GroundedText":
        if self.origin in {
            ContentOrigin.EXACT_PUBLISHER,
            ContentOrigin.CLOSE_PARAPHRASE,
            ContentOrigin.STUDENT_ADAPTATION,
        } and not self.source_references:
            raise ValueError("Source-derived content requires provenance.")
        return self


class TeachingPackageFinding(StrictModel):
    code: str = Field(min_length=1)
    severity: ValidationSeverity
    message: str = Field(min_length=1)
    reference_id: Optional[str] = None


class TeachingPackageValidationReport(StrictModel):
    status: str = Field(pattern="^(pass|pass_with_warnings|fail)$")
    findings: list[TeachingPackageFinding] = Field(default_factory=list)
    package_digest: str = Field(min_length=1)
    validator_version: str = Field(min_length=1)


class LessonDashboard(StrictModel):
    curriculum: str
    grade: str
    unit: str
    lesson_number: int = Field(ge=1)
    lesson_title: str
    estimated_duration_minutes: int = Field(ge=0)
    materials: list[str] = Field(default_factory=list)
    student_reader_pages: list[str] = Field(default_factory=list)
    activity_book_pages: list[str] = Field(default_factory=list)
    lesson_purpose: GroundedText
    big_idea: GroundedText
    why_it_matters: GroundedText
    previous_learning: Optional[GroundedText] = None
    upcoming_learning: Optional[GroundedText] = None
    teacher_reminders: list[GroundedText] = Field(default_factory=list)
    missing_resource_warnings: list[str] = Field(default_factory=list)


class TeachingObjective(StrictModel):
    objective_id: str
    official: GroundedText
    student_friendly: GroundedText
    evidence_of_mastery: GroundedText
    objective_type: str = Field(
        pattern="^(content|language|generated_language_support)$"
    )
    meaning_preserved: bool


class TeachingAgendaItem(StrictModel):
    agenda_item_id: str
    official_order: int = Field(ge=1)
    official_title: GroundedText
    student_friendly_title: GroundedText
    official_description: GroundedText
    student_friendly_description: GroundedText
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    materials: list[str] = Field(default_factory=list)
    teacher_guide_references: list[TeachingSourceReference] = Field(
        default_factory=list
    )
    student_reader_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    required: bool = True
    teacher_only: bool = False
    teaching_step_ids: list[str] = Field(default_factory=list)
    question_ids: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    adaptation_classification: ContentOrigin
    review_status: ReviewStatus


class TeachingQuestion(StrictModel):
    question_id: str
    sequence: int = Field(ge=1)
    agenda_item_id: str
    exact_question: GroundedText
    expected_answer: GroundedText
    publisher_answer_guidance: Optional[GroundedText] = None
    acceptable_alternatives: list[GroundedText] = Field(default_factory=list)
    text_evidence: Optional[GroundedText] = None
    follow_up: GroundedText
    misconception: GroundedText
    eld_sentence_frame: GroundedText
    answer_visibility: str = Field(
        pattern="^(teacher_only|unavailable)$"
    )
    slide_ids: list[str] = Field(default_factory=list)


class TeachingStep(StrictModel):
    teaching_step_id: str
    agenda_item_id: str
    official_title: str
    student_friendly_title: str
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    instructional_purpose: GroundedText
    teacher_preparation: list[GroundedText] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    teacher_actions: list[GroundedText] = Field(default_factory=list)
    student_actions: list[GroundedText] = Field(default_factory=list)
    suggested_teacher_wording: GroundedText
    question_ids: list[str] = Field(default_factory=list)
    checks_for_understanding: list[GroundedText] = Field(default_factory=list)
    misconceptions: list[GroundedText] = Field(default_factory=list)
    eld_supports: list[GroundedText] = Field(default_factory=list)
    differentiation: list[GroundedText] = Field(default_factory=list)
    transition: GroundedText
    student_reader_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    source_references: list[TeachingSourceReference] = Field(
        default_factory=list
    )


class TeachingVocabulary(StrictModel):
    vocabulary_id: str
    word: str
    official_definition: Optional[GroundedText] = None
    student_friendly_definition: GroundedText
    part_of_speech: Optional[str] = None
    pronunciation: Optional[str] = None
    context: Optional[GroundedText] = None
    teacher_explanation: GroundedText
    example: GroundedText
    visual_suggestion: GroundedText
    gesture_suggestion: GroundedText
    cognate: Optional[str] = None
    eld_support: GroundedText
    misconception: GroundedText


class StudentSlide(StrictModel):
    slide_id: str
    slide_number: int = Field(ge=1)
    agenda_item_id: Optional[str] = None
    slide_type: str
    title: str = Field(min_length=1)
    visible_student_content: list[str] = Field(default_factory=list)
    student_prompt: Optional[str] = None
    page_reference: Optional[str] = None
    activity_reference: Optional[str] = None
    visual_specification: str
    speaker_notes: list[str] = Field(default_factory=list)
    source_references: list[TeachingSourceReference] = Field(
        default_factory=list
    )
    adaptation_classification: ContentOrigin
    validation_results: list[TeachingPackageFinding] = Field(
        default_factory=list
    )
    question_ids: list[str] = Field(default_factory=list)


class StructuredTeachingPackage(StrictModel):
    schema_version: str
    builder_version: str
    adaptation_prompt_version: str
    deterministic_model_version: str
    package_digest: str
    source_bundle_digest: str
    lesson_intelligence_digest: str
    dashboard: LessonDashboard
    five_minute_summary: list[GroundedText]
    agenda: list[TeachingAgendaItem]
    objectives: list[TeachingObjective]
    essential_question: Optional[GroundedText] = None
    background_knowledge: list[GroundedText] = Field(default_factory=list)
    themes: list[GroundedText] = Field(default_factory=list)
    literary_analysis: list[GroundedText] = Field(default_factory=list)
    vocabulary: list[TeachingVocabulary] = Field(default_factory=list)
    teaching_steps: list[TeachingStep]
    questions: list[TeachingQuestion]
    student_reader_guidance: list[GroundedText] = Field(default_factory=list)
    activity_book_guidance: list[GroundedText] = Field(default_factory=list)
    assessment: list[GroundedText] = Field(default_factory=list)
    wrap_up: list[GroundedText] = Field(default_factory=list)
    homework: list[GroundedText] = Field(default_factory=list)
    eld_supports: list[GroundedText] = Field(default_factory=list)
    differentiation: list[GroundedText] = Field(default_factory=list)
    student_slides: list[StudentSlide]
    provenance: list[TeachingSourceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation: TeachingPackageValidationReport

    @model_validator(mode="after")
    def identities_and_order_are_unique(self) -> "StructuredTeachingPackage":
        groups = (
            [item.agenda_item_id for item in self.agenda],
            [item.teaching_step_id for item in self.teaching_steps],
            [item.question_id for item in self.questions],
            [item.slide_id for item in self.student_slides],
        )
        if any(len(values) != len(set(values)) for values in groups):
            raise ValueError("Stable IDs must be unique within each package group.")
        if [item.official_order for item in self.agenda] != list(
            range(1, len(self.agenda) + 1)
        ):
            raise ValueError("Agenda order must be continuous and unique.")
        if [item.slide_number for item in self.student_slides] != list(
            range(1, len(self.student_slides) + 1)
        ):
            raise ValueError("Slide numbers must be continuous and unique.")
        if self.schema_version != TEACHING_PACKAGE_SCHEMA_VERSION:
            raise ValueError("Unsupported teaching-package schema version.")
        return self


__all__ = [
    "ContentOrigin", "GroundedText", "LessonDashboard", "ReviewStatus",
    "StudentSlide", "StructuredTeachingPackage", "TeachingAgendaItem",
    "TeachingObjective", "TeachingPackageFinding",
    "TeachingPackageValidationReport", "TeachingQuestion",
    "TeachingSourceReference", "TeachingStep", "TeachingVocabulary",
    "TEACHING_PACKAGE_SCHEMA_VERSION", "ValidationSeverity",
]
