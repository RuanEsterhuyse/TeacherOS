"""Contracts for isolated teacher-pasted lesson intake and review."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


PASTED_LESSON_SCHEMA_VERSION = "1.0"
TEACHER_PLAYBOOK_SCHEMA_VERSION = "1.0"
BASELINE_ANALYZER_VERSION = "1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PastedLessonSource(StrictModel):
    """Teacher-provided source text preserved without normalization."""

    source_id: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    teacher_guide_page_start: Optional[int] = Field(default=None, ge=1)
    teacher_guide_page_end: Optional[int] = Field(default=None, ge=1)
    teacher_guide_text: str = Field(min_length=1)
    student_reader_text: Optional[str] = None
    activity_book_text: Optional[str] = None
    source_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    schema_version: str = PASTED_LESSON_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_page_range(self) -> "PastedLessonSource":
        values = (
            self.teacher_guide_page_start,
            self.teacher_guide_page_end,
        )
        if (values[0] is None) != (values[1] is None):
            raise ValueError(
                "Teacher Guide page start and end must be supplied together."
            )
        if values[0] is not None and values[1] < values[0]:
            raise ValueError(
                "Teacher Guide page end cannot precede page start."
            )
        return self


class SourceReference(StrictModel):
    source_type: str = Field(min_length=1)
    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)
    section: Optional[str] = None
    activity_reference: Optional[str] = None

    @model_validator(mode="after")
    def validate_page_range(self) -> "SourceReference":
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("Source-reference page range is reversed.")
        return self


class DiscussionQuestion(StrictModel):
    prompt: str = Field(min_length=1)
    why_ask: Optional[str] = None
    strong_responses: list[str] = Field(default_factory=list)
    typical_responses: list[str] = Field(default_factory=list)
    weak_responses: list[str] = Field(default_factory=list)
    teacher_response: Optional[str] = None
    support_if_students_struggle: Optional[str] = None


class VocabularyEntry(StrictModel):
    term: str = Field(min_length=1)
    student_friendly_definition: Optional[str] = None
    teacher_notes: Optional[str] = None
    examples: list[str] = Field(default_factory=list)
    misconception_support: Optional[str] = None


class PlaybookActivity(StrictModel):
    activity_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    instructional_day: Optional[int] = Field(default=None, ge=1)
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    purpose: Optional[str] = None
    teacher_goal: Optional[str] = None
    teacher_script: list[str] = Field(default_factory=list)
    questions: list[DiscussionQuestion] = Field(default_factory=list)
    possible_student_responses: list[str] = Field(default_factory=list)
    teacher_responses: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    eld_supports: list[str] = Field(default_factory=list)
    checks_for_understanding: list[str] = Field(default_factory=list)
    look_fors: list[str] = Field(default_factory=list)
    ready_to_move_on_criteria: list[str] = Field(default_factory=list)
    transition: Optional[str] = None
    source_references: list[SourceReference] = Field(default_factory=list)


class PlaybookLessonMetadata(StrictModel):
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    teacher_guide_page_start: Optional[int] = Field(default=None, ge=1)
    teacher_guide_page_end: Optional[int] = Field(default=None, ge=1)


class PlaybookGenerationMetadata(StrictModel):
    analyzer_name: str = Field(min_length=1)
    analyzer_version: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=utc_now)
    deterministic: bool = True
    source_schema_version: str = Field(min_length=1)


class TeacherPlaybook(StrictModel):
    playbook_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    lesson_metadata: PlaybookLessonMetadata
    lesson_summary: Optional[str] = None
    instructional_days: list[int] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    essential_question: Optional[str] = None
    success_criteria: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    vocabulary: list[VocabularyEntry] = Field(default_factory=list)
    teacher_survival_guide: list[str] = Field(default_factory=list)
    activities: list[PlaybookActivity] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    assessment: list[str] = Field(default_factory=list)
    end_of_day_reflection: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    generation_metadata: PlaybookGenerationMetadata
    schema_version: str = TEACHER_PLAYBOOK_SCHEMA_VERSION


class AnalysisWarning(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    field: Optional[str] = None


class ExtractionSummary(StrictModel):
    detected_activity_count: int = Field(ge=0)
    detected_day_count: int = Field(ge=0)
    detected_reference_count: int = Field(ge=0)
    classified_line_count: int = Field(ge=0)
    unclassified_line_count: int = Field(ge=0)
    confidence_by_field: dict[str, float] = Field(default_factory=dict)


class PlaybookAnalysisResult(StrictModel):
    playbook: TeacherPlaybook
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    unclassified_sections: list[str] = Field(default_factory=list)
    extraction_summary: ExtractionSummary
    analyzer_version: str = BASELINE_ANALYZER_VERSION


__all__ = [
    "AnalysisWarning",
    "BASELINE_ANALYZER_VERSION",
    "DiscussionQuestion",
    "ExtractionSummary",
    "PASTED_LESSON_SCHEMA_VERSION",
    "PastedLessonSource",
    "PlaybookActivity",
    "PlaybookAnalysisResult",
    "PlaybookGenerationMetadata",
    "PlaybookLessonMetadata",
    "SourceReference",
    "TEACHER_PLAYBOOK_SCHEMA_VERSION",
    "TeacherPlaybook",
    "VocabularyEntry",
    "utc_now",
]
