"""Instruction Designer structured output."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class InstructionSegment(BaseModel):
    segment_id: str
    day: int = Field(ge=1)
    sequence: int = Field(ge=1)
    title: str
    timing_minutes: int = Field(ge=0)
    teacher_moves: list[str] = Field(default_factory=list)
    student_actions: list[str] = Field(default_factory=list)
    checks_for_understanding: list[str] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)
    discussion_structures: list[str] = Field(default_factory=list)
    language_supports: list[str] = Field(default_factory=list)
    support_origin: Literal["source_required", "teacheros_added", "mixed"] = "source_required"
    materials: list[str] = Field(default_factory=list)
    reader_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)


class InstructionDesign(BaseModel):
    request_id: str
    lesson_title: Optional[str] = None
    objectives: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    segments: list[InstructionSegment] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    total_timing_minutes: int = Field(ge=0)
    timing_warnings: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
