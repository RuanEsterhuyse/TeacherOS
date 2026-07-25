"""Structured contracts for optional Teacher Companion Guide generation."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.generation_common import ValidationFinding


SOURCE_EVIDENCE_MARKER = "[REQUIRES SOURCE EVIDENCE]"


class CompanionSourceBasis(BaseModel):
    """Exact source boundary supplied to the companion generator."""

    curriculum_name: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    objectives: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    reader_page_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(min_length=1)
    student_reader_text_available: bool = False


class GroundedCurriculumFact(BaseModel):
    """A curriculum claim tied directly to prepared source references."""

    fact: str = Field(min_length=1)
    source_references: list[str] = Field(min_length=1)


class CompanionConcept(BaseModel):
    name: str = Field(min_length=1)
    what_to_teach: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    how_to_teach: str = Field(min_length=1)
    educational_terminology: list[str] = Field(min_length=1)


class VocabularyGuidance(BaseModel):
    term: str = Field(min_length=1)
    meaning_for_teacher: str = Field(min_length=1)
    student_friendly_explanation: str = Field(min_length=1)
    how_to_teach: str = Field(min_length=1)
    what_to_listen_for: str = Field(min_length=1)


class MisconceptionGuidance(BaseModel):
    misconception: str = Field(min_length=1)
    why_students_may_have_it: str = Field(min_length=1)
    exact_teacher_correction: str = Field(min_length=1)


class StudentQuestionGuide(BaseModel):
    """A student question with every mandatory answer and coaching field."""

    exact_question: str = Field(min_length=1)
    why_the_question_is_asked: str = Field(min_length=1)
    possible_student_answers: list[str] = Field(min_length=3, max_length=8)
    excellent_model_answer: str = Field(min_length=1)
    why_the_model_answer_is_correct: str = Field(min_length=1)
    what_the_teacher_should_listen_for: list[str] = Field(min_length=1)
    likely_misconceptions: list[MisconceptionGuidance] = Field(min_length=1)
    scaffolded_follow_up_questions: list[str] = Field(min_length=1)
    extension_question: str = Field(min_length=1)
    answer_basis: Literal[
        "teacher_guide",
        "generated_instructional_guidance",
        "requires_student_reader_evidence",
    ]
    source_references: list[str] = Field(default_factory=list)

    @field_validator("possible_student_answers", "scaffolded_follow_up_questions")
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("question response lists may not contain blank items")
        return values

    @model_validator(mode="after")
    def require_evidence_marker_for_unavailable_reader_answer(
        self,
    ) -> "StudentQuestionGuide":
        if self.answer_basis == "requires_student_reader_evidence":
            if SOURCE_EVIDENCE_MARKER not in self.excellent_model_answer:
                raise ValueError(
                    "source-dependent model answers must use "
                    f"{SOURCE_EVIDENCE_MARKER}"
                )
        return self


class MasteryDescription(BaseModel):
    mastery_statement: str = Field(min_length=1)
    observable_indicators: list[str] = Field(min_length=1)
    evidence_to_collect: list[str] = Field(min_length=1)


class TeacherCompanionGuide(BaseModel):
    """Teacher-facing instructional preparation for one prepared lesson."""

    request_id: str = Field(min_length=1)
    guide_version: str = "1.0"
    source_basis: CompanionSourceBasis
    teaching_overview: str = Field(min_length=1)
    why_this_lesson_matters: str = Field(min_length=1)
    curriculum_facts: list[GroundedCurriculumFact] = Field(min_length=1)
    generated_instructional_guidance: list[str] = Field(min_length=1)
    required_concepts: list[CompanionConcept] = Field(min_length=1)
    background_knowledge: list[str] = Field(min_length=1)
    vocabulary_guidance: list[VocabularyGuidance] = Field(min_length=1)
    teacher_coaching: list[str] = Field(min_length=1)
    misconceptions_and_corrections: list[MisconceptionGuidance] = Field(
        min_length=1
    )
    student_supports: list[str] = Field(min_length=1)
    student_questions: list[StudentQuestionGuide] = Field(min_length=1)
    mastery: MasteryDescription
    grounding_notes: list[str] = Field(default_factory=list)


class TeacherCompanionValidationReport(BaseModel):
    status: Literal["pass", "pass_with_warnings", "fail"]
    findings: list[ValidationFinding] = Field(default_factory=list)
    question_count: int = Field(ge=0)


class TeacherCompanionGenerationResult(BaseModel):
    request_id: str
    status: Literal["completed", "completed_with_warnings", "failed"]
    output_directory: str
    completed_stages: list[str] = Field(default_factory=list)
    failed_stage: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    validation_result: Optional[
        Literal["pass", "pass_with_warnings", "fail"]
    ] = None
    resumed: bool = False
    usage: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "SOURCE_EVIDENCE_MARKER",
    "CompanionConcept",
    "CompanionSourceBasis",
    "GroundedCurriculumFact",
    "MasteryDescription",
    "MisconceptionGuidance",
    "StudentQuestionGuide",
    "TeacherCompanionGenerationResult",
    "TeacherCompanionGuide",
    "TeacherCompanionValidationReport",
    "VocabularyGuidance",
]
