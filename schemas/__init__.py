"""Validation schemas exposed by TeacherOS."""

from schemas.lesson_schema import (
    Activity,
    Assessment,
    Homework,
    Lesson,
    Slide,
    Vocabulary,
)

__all__ = ["Activity", "Assessment", "Homework", "Lesson", "Slide", "Vocabulary"]
from schemas.presentation_design_schema import PresentationDesignOutput, PresentationSlide
