"""Contracts for the opt-in Daily Lesson Generator workflow."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field, model_validator

from schemas.pasted_lesson_schema import (
    PastedLessonSource,
    SourceReference,
    StrictModel,
    utc_now,
)


DAILY_LESSON_SCHEMA_VERSION = "1.0"
DAILY_LESSON_GENERATOR_VERSION = "daily-lesson-generator-v1"
DAILY_GUIDANCE_LABEL = "[Generated teacher guidance — review]"


class DailyLessonStatus(str, Enum):
    playbook_ready = "playbook_ready"
    complete = "complete"


class DailyLessonGenerationOptions(StrictModel):
    include_speaker_notes_in_prompts: bool = True
    maximum_student_text_characters: int = Field(default=520, ge=80)


class DailySourceIdentity(StrictModel):
    source_id: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    teacher_guide_page_start: Optional[int] = Field(default=None, ge=1)
    teacher_guide_page_end: Optional[int] = Field(default=None, ge=1)


class DailyAgendaItem(StrictModel):
    title: str = Field(min_length=1)
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    purpose: Optional[str] = None


class DailyVocabularyEntry(StrictModel):
    term: str = Field(min_length=1)
    student_friendly_definition: Optional[str] = None
    teacher_guidance: Optional[str] = None


class DailyQuestionSupport(StrictModel):
    question: str = Field(min_length=1)
    why_ask: str = Field(min_length=1)
    strong_responses: list[str] = Field(default_factory=list)
    typical_responses: list[str] = Field(default_factory=list)
    weak_responses: list[str] = Field(default_factory=list)
    teacher_response: str = Field(min_length=1)
    misconceptions: list[str] = Field(default_factory=list)


class DailyActivityCoaching(StrictModel):
    activity_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    purpose: str = Field(min_length=1)
    teacher_goal: str = Field(min_length=1)
    what_to_say: list[str] = Field(default_factory=list)
    questions: list[DailyQuestionSupport] = Field(default_factory=list)
    examples_and_analogies: list[str] = Field(default_factory=list)
    eld_supports: list[str] = Field(default_factory=list)
    sentence_frames: list[str] = Field(default_factory=list)
    checks_for_understanding: list[str] = Field(default_factory=list)
    look_fors: list[str] = Field(default_factory=list)
    ready_to_move_on_criteria: list[str] = Field(default_factory=list)
    transition: Optional[str] = None
    source_references: list[SourceReference] = Field(default_factory=list)


class DailyTeacherPlaybook(StrictModel):
    lesson_information: DailySourceIdentity
    lesson_meaning: str = Field(min_length=1)
    leave_understanding: list[str] = Field(default_factory=list)
    essential_question: Optional[str] = None
    content_objective: Optional[str] = None
    language_objective: Optional[str] = None
    success_criteria: list[str] = Field(default_factory=list)
    agenda: list[DailyAgendaItem] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    vocabulary: list[DailyVocabularyEntry] = Field(default_factory=list)
    teacher_survival_guide: list[str] = Field(default_factory=list)
    activities: list[DailyActivityCoaching] = Field(default_factory=list)
    exit_ticket: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    teacher_reflection: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    unavailable_information: list[str] = Field(default_factory=list)


class DailySpeakerNotes(StrictModel):
    teacher_says: list[str] = Field(default_factory=list)
    teacher_does: list[str] = Field(default_factory=list)
    discussion_prompts: list[str] = Field(default_factory=list)
    anticipated_responses: list[str] = Field(default_factory=list)
    misconception_support: list[str] = Field(default_factory=list)
    checks_for_understanding: list[str] = Field(default_factory=list)
    transition: Optional[str] = None
    timing_minutes: Optional[int] = Field(default=None, ge=0)
    source_references: list[SourceReference] = Field(default_factory=list)


class DailySlideOutlineItem(StrictModel):
    slide_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    instructional_purpose: str = Field(min_length=1)
    related_activity_id: Optional[str] = None
    related_activity: Optional[str] = None
    suggested_layout: str = Field(min_length=1)
    student_facing_content_summary: str = Field(min_length=1)
    exact_student_facing_text: list[str] = Field(min_length=1)
    suggested_visual: Optional[str] = None
    speaker_notes: DailySpeakerNotes
    source_references: list[SourceReference] = Field(default_factory=list)


class GeminiSlidePrompt(StrictModel):
    slide_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    speaker_notes_markdown: str


class DailyGenerationMetadata(StrictModel):
    provider_name: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=utc_now)
    playbook_usage: dict[str, Any] = Field(default_factory=dict)
    slide_usage: dict[str, Any] = Field(default_factory=dict)
    generator_version: str = DAILY_LESSON_GENERATOR_VERSION


class DailyGoogleSlidesArtifact(StrictModel):
    presentation_id: str = Field(min_length=1)
    presentation_url: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    slide_count: int = Field(ge=1)
    title: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class DailyLessonPackage(StrictModel):
    package_id: str = Field(min_length=1)
    source_identity: DailySourceIdentity
    status: DailyLessonStatus
    teacher_playbook: DailyTeacherPlaybook
    teacher_playbook_markdown: str = Field(min_length=1)
    slide_outline: list[DailySlideOutlineItem] = Field(default_factory=list)
    gemini_slide_prompts: list[GeminiSlidePrompt] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    generation_metadata: DailyGenerationMetadata
    google_slides: Optional[DailyGoogleSlidesArtifact] = None
    schema_version: str = DAILY_LESSON_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_complete_package(self) -> "DailyLessonPackage":
        if self.status == DailyLessonStatus.complete:
            if not self.slide_outline or not self.gemini_slide_prompts:
                raise ValueError("A complete daily package requires slide prompts.")
            if len(self.slide_outline) != len(self.gemini_slide_prompts):
                raise ValueError("Slide outline and prompt counts must match.")
        numbers = [item.slide_number for item in self.slide_outline]
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Daily slide numbers must be contiguous and ordered.")
        return self


class DailyPlaybookContext(StrictModel):
    source: PastedLessonSource
    deterministic_baseline: dict[str, Any]
    options: DailyLessonGenerationOptions


class DailySlideContext(StrictModel):
    source: PastedLessonSource
    playbook: DailyTeacherPlaybook
    options: DailyLessonGenerationOptions


class GeneratedDailyPlaybook(StrictModel):
    playbook: DailyTeacherPlaybook
    warnings: list[str] = Field(default_factory=list)


class GeneratedDailySlideOutline(StrictModel):
    slides: list[DailySlideOutlineItem] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "DAILY_GUIDANCE_LABEL",
    "DAILY_LESSON_GENERATOR_VERSION",
    "DAILY_LESSON_SCHEMA_VERSION",
    "DailyActivityCoaching",
    "DailyAgendaItem",
    "DailyGenerationMetadata",
    "DailyGoogleSlidesArtifact",
    "DailyLessonGenerationOptions",
    "DailyLessonPackage",
    "DailyLessonStatus",
    "DailyPlaybookContext",
    "DailyQuestionSupport",
    "DailySlideContext",
    "DailySlideOutlineItem",
    "DailySourceIdentity",
    "DailySpeakerNotes",
    "DailyTeacherPlaybook",
    "DailyVocabularyEntry",
    "GeminiSlidePrompt",
    "GeneratedDailyPlaybook",
    "GeneratedDailySlideOutline",
]
