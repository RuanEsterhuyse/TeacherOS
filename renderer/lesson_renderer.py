"""Shared contract for deterministic canonical-lesson renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from schemas.canonical_lesson_schema import CanonicalLesson


T = TypeVar("T")


class LessonRenderer(ABC, Generic[T]):
    """A renderer that receives one validated canonical lesson."""

    @abstractmethod
    def render(self, lesson: CanonicalLesson) -> T:
        raise NotImplementedError

    @abstractmethod
    def write(self, lesson: CanonicalLesson, directory: str | Path) -> Path:
        raise NotImplementedError


__all__ = ["LessonRenderer"]
