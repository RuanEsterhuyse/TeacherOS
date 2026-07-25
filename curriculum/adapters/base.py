"""Provider-neutral curriculum adapter contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from schemas.curriculum_schema import (
    CurriculumIndex,
    CurriculumUnit,
    LessonIndexEntry,
    LessonSource,
    PdfPage,
)
from schemas.student_reader_source_schema import StudentReaderSource


@dataclass(frozen=True)
class CurriculumTerminology:
    """Provider-specific labels used around otherwise generic source roles."""

    teacher_guide: str
    student_reader: str
    activity_book: str
    activity_page: str
    lesson: str = "Lesson"
    unit: str = "Unit"


class CurriculumAdapter(ABC):
    """Boundary between TeacherOS and provider-specific curriculum structure."""

    curriculum_names: tuple[str, ...]
    attribution: str
    terminology: CurriculumTerminology

    def supports(self, curriculum_name: str) -> bool:
        normalized = curriculum_name.strip().casefold()
        return any(name.casefold() == normalized for name in self.curriculum_names)

    @abstractmethod
    def detect_lesson_boundaries(
        self,
        curriculum: CurriculumUnit,
        teacher_guide_path: str | Path | None = None,
        override_file: str | Path | None = None,
    ) -> CurriculumIndex:
        """Build a provider-specific lesson index from the Teacher Guide."""

    @abstractmethod
    def extract_lesson_metadata(self, pages: list[PdfPage]) -> Any:
        """Extract provider-specific lesson metadata without rewriting content."""

    @abstractmethod
    def validate_required_resources(
        self,
        curriculum: CurriculumUnit,
        resolve_path: Callable[[str | Path], Path],
    ) -> list[str]:
        """Return blocking resource errors using provider terminology."""

    @abstractmethod
    def prepare_lesson(
        self,
        index: CurriculumIndex,
        lesson_number: int,
        teacher_guide_path: str | Path | None = None,
    ) -> LessonSource:
        """Prepare one indexed lesson source for the shared TeacherOS pipeline."""

    @abstractmethod
    def retrieve_student_reader(
        self,
        curriculum: CurriculumUnit,
        lesson: LessonIndexEntry,
        student_reader_path: str | Path | None,
    ) -> StudentReaderSource:
        """Retrieve only indexed Student Reader pages for one lesson."""

    @abstractmethod
    def default_index_path(self, curriculum: CurriculumUnit) -> Path:
        """Return the provider's deterministic saved-index path."""

    @abstractmethod
    def save_index(
        self,
        index: CurriculumIndex,
        path: str | Path | None = None,
    ) -> Path:
        """Persist an index without changing provider-specific contents."""

    @abstractmethod
    def load_index(self, path: str | Path) -> CurriculumIndex:
        """Load and validate a previously saved index."""

    @abstractmethod
    def get_lesson_entry(
        self,
        index: CurriculumIndex,
        lesson_number: int,
    ) -> LessonIndexEntry:
        """Select one lesson entry from a provider index."""


__all__ = ["CurriculumAdapter", "CurriculumTerminology"]
