"""CKLA curriculum adapter backed by the existing deterministic logic."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from curriculum.adapters.base import CurriculumAdapter, CurriculumTerminology
from curriculum.ckla_lesson_metadata import (
    CKLALessonMetadata,
    extract_ckla_lesson_metadata,
)
from curriculum.lesson_locator import CKLALessonLocator
from curriculum.student_reader_locator import StudentReaderLocator
from schemas.curriculum_schema import (
    CurriculumIndex,
    CurriculumUnit,
    LessonIndexEntry,
    LessonSource,
    PdfPage,
)
from schemas.lesson_package_schema import CKLA_ATTRIBUTION
from schemas.student_reader_source_schema import StudentReaderSource


class CKLAAdapter(CurriculumAdapter):
    """Expose existing CKLA extraction through the shared adapter contract."""

    curriculum_names = ("CKLA",)
    attribution = CKLA_ATTRIBUTION
    terminology = CurriculumTerminology(
        teacher_guide="Teacher Guide",
        student_reader="Student Reader",
        activity_book="Activity Book",
        activity_page="Activity Page",
    )

    def __init__(
        self,
        *,
        locator: CKLALessonLocator | None = None,
        index_directory: str | Path = "data/indexes",
        student_reader_locator: StudentReaderLocator | None = None,
    ) -> None:
        self.locator = locator or CKLALessonLocator(
            index_directory=index_directory
        )
        self.student_reader_locator = (
            student_reader_locator or StudentReaderLocator()
        )

    def detect_lesson_boundaries(
        self,
        curriculum: CurriculumUnit,
        teacher_guide_path: str | Path | None = None,
        override_file: str | Path | None = None,
    ) -> CurriculumIndex:
        return self.locator.build_index(
            curriculum,
            teacher_guide_path,
            override_file,
        )

    def extract_lesson_metadata(
        self,
        pages: list[PdfPage],
    ) -> CKLALessonMetadata:
        return extract_ckla_lesson_metadata(pages)

    def validate_required_resources(
        self,
        curriculum: CurriculumUnit,
        resolve_path: Callable[[str | Path], Path],
    ) -> list[str]:
        teacher_guide = resolve_path(curriculum.teacher_guide_path)
        if not teacher_guide.is_file():
            return [
                f"{self.terminology.teacher_guide} PDF not found: "
                f"{teacher_guide}"
            ]
        return []

    def prepare_lesson(
        self,
        index: CurriculumIndex,
        lesson_number: int,
        teacher_guide_path: str | Path | None = None,
    ) -> LessonSource:
        return self.locator.extract_lesson_source(
            index,
            lesson_number,
            teacher_guide_path,
        )

    def retrieve_student_reader(
        self,
        curriculum: CurriculumUnit,
        lesson: LessonIndexEntry,
        student_reader_path: str | Path | None,
    ) -> StudentReaderSource:
        return self.student_reader_locator.retrieve(
            curriculum,
            lesson,
            student_reader_path,
        )

    def default_index_path(self, curriculum: CurriculumUnit) -> Path:
        return self.locator.default_index_path(curriculum)

    def save_index(
        self,
        index: CurriculumIndex,
        path: str | Path | None = None,
    ) -> Path:
        return self.locator.save_index(index, path)

    def load_index(self, path: str | Path) -> CurriculumIndex:
        return self.locator.load_index(path)

    def get_lesson_entry(
        self,
        index: CurriculumIndex,
        lesson_number: int,
    ) -> LessonIndexEntry:
        return self.locator.get_lesson_entry(index, lesson_number)


__all__ = ["CKLAAdapter"]
