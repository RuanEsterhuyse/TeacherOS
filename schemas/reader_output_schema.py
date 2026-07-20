"""Curriculum Reader structured output."""

from typing import Optional
from pydantic import BaseModel, Field
from schemas.generation_common import Finding


class LessonSection(BaseModel):
    section_id: str
    day: int = Field(ge=1)
    sequence: int = Field(ge=1)
    title: str
    timing_minutes: Optional[int] = Field(default=None, ge=0)
    teacher_directions: list[str] = Field(default_factory=list)
    student_tasks: list[str] = Field(default_factory=list)
    discussion_questions: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)


class CurriculumReaderOutput(BaseModel):
    request_id: str
    lesson_title: Optional[str] = None
    lesson_days: int = Field(default=1, ge=1)
    lesson_sequence: list[str] = Field(default_factory=list)
    sections: list[LessonSection] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    reader_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    assessment_references: list[str] = Field(default_factory=list)
    differentiation: list[Finding] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    timing_conflicts: list[str] = Field(default_factory=list)
