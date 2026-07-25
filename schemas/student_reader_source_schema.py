"""Structured source material retrieved from a registered Student Reader."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


StudentReaderExtractionStatus = Literal[
    "completed",
    "completed_with_warnings",
    "partial",
    "failed",
    "unavailable",
]


class StudentReaderPageSource(BaseModel):
    """One unambiguous printed Reader page and its source PDF page."""

    printed_page: str = Field(min_length=1)
    pdf_page_number: int = Field(ge=0)
    display_pdf_page_number: int = Field(ge=1)
    extracted_text: str
    requested_by: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StudentReaderSource(BaseModel):
    """Exact Reader pages associated with one indexed curriculum lesson."""

    curriculum_name: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    source_document: Optional[str] = None
    requested_printed_page_references: list[str] = Field(default_factory=list)
    matched_pdf_page_numbers: list[int] = Field(default_factory=list)
    pages: list[StudentReaderPageSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extraction_status: StudentReaderExtractionStatus
    source_available: bool


__all__ = [
    "StudentReaderExtractionStatus",
    "StudentReaderPageSource",
    "StudentReaderSource",
]
