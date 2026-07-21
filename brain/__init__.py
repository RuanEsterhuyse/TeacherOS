"""Deterministic transformations between TeacherOS pipeline stages."""

from brain.lesson_package_parser import LessonPackageError, LessonPackageParser, parse_lesson_package

__all__ = ["LessonPackageError", "LessonPackageParser", "parse_lesson_package"]
from brain.presentation_designer import PresentationDesigner
