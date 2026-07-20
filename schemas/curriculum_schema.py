"""Validated contracts for curriculum registration and lesson extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    """Return a timezone-aware timestamp suitable for persisted metadata."""
    return datetime.now(timezone.utc)


class CurriculumUnit(BaseModel):
    curriculum_name: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    unit_title: Optional[str] = None
    teacher_guide_path: str = Field(min_length=1)
    student_reader_path: Optional[str] = None
    activity_book_path: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("curriculum_name", "grade", "unit", "unit_title")
    @classmethod
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else value


class PdfPage(BaseModel):
    pdf_page_number: int = Field(ge=0)
    display_page_number: int = Field(ge=1)
    printed_page_number: Optional[int] = Field(default=None, ge=1)
    raw_text: str
    normalized_text: str
    character_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LessonIndexEntry(BaseModel):
    lesson_number: int = Field(ge=1)
    lesson_title: Optional[str] = None
    lesson_objective: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    reader_pages: list[str] = Field(default_factory=list)
    activity_book_pages: list[str] = Field(default_factory=list)
    assessment_references: list[str] = Field(default_factory=list)
    lesson_duration: Optional[int] = Field(default=None, ge=0, description="Total scheduled minutes")
    source_page_numbers: list[int] = Field(default_factory=list, description="Printed Teacher Guide pages")
    start_pdf_page: int = Field(ge=0)
    end_pdf_page: int = Field(ge=0)
    start_printed_page: Optional[int] = Field(default=None, ge=1)
    end_printed_page: Optional[int] = Field(default=None, ge=1)
    text_start_offset: Optional[int] = Field(default=None, ge=0)
    text_end_offset: Optional[int] = Field(default=None, ge=0)
    detected_heading: str
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    source_file: str


class CurriculumIndex(BaseModel):
    curriculum: CurriculumUnit
    total_pdf_pages: int = Field(ge=0)
    lessons: list[LessonIndexEntry]
    extraction_warnings: list[str] = Field(default_factory=list)
    index_version: str = "2.0"


class LessonSource(BaseModel):
    curriculum: CurriculumUnit
    lesson_number: int = Field(ge=1)
    lesson_title: Optional[str] = None
    start_page: int = Field(ge=0)
    end_page: int = Field(ge=0)
    extracted_text: str
    source_references: list[str]
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "CurriculumIndex", "CurriculumUnit", "LessonIndexEntry", "LessonSource", "PdfPage"
]
