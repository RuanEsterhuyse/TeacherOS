"""Validation schemas exposed by TeacherOS."""

from schemas.lesson_schema import (
    Activity,
    Assessment,
    Homework,
    Lesson,
    Slide,
    Vocabulary,
)
from schemas.canonical_lesson_schema import CanonicalLesson

__all__ = [
    "Activity",
    "Assessment",
    "CanonicalLesson",
    "Homework",
    "Lesson",
    "Slide",
    "Vocabulary",
]
from schemas.presentation_design_schema import PresentationDesignOutput, PresentationSlide
