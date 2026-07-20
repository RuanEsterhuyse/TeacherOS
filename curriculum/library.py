"""Public curriculum metadata library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from curriculum.repository import CurriculumRepository
from schemas.curriculum_schema import CurriculumUnit, utc_now


class CurriculumLibrary:
    """Register and retrieve local curriculum file references."""

    def __init__(self, database_path: str | Path = "data/curriculum/library.sqlite3", project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        db_path = Path(database_path)
        if not db_path.is_absolute():
            db_path = self.project_root / db_path
        self.repository = CurriculumRepository(db_path)

    def _stored_path(self, value: str | Path | None) -> str | None:
        if value is None:
            return None
        path = Path(value).expanduser()
        absolute = path.resolve() if path.is_absolute() else (self.project_root / path).resolve()
        try:
            return str(absolute.relative_to(self.project_root))
        except ValueError:
            return str(absolute)

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.project_root / path

    def register_unit(self, *, curriculum_name: str, grade: str | int, unit: str | int,
                      teacher_guide_path: str | Path, unit_title: str | None = None,
                      student_reader_path: str | Path | None = None,
                      activity_book_path: str | Path | None = None) -> CurriculumUnit:
        key = (curriculum_name.strip(), str(grade), str(unit))
        if self.repository.get(*key):
            raise ValueError(f"Curriculum unit already registered: {key[0]} grade {key[1]} unit {key[2]}")
        record = CurriculumUnit(
            curriculum_name=key[0], grade=key[1], unit=key[2], unit_title=unit_title,
            teacher_guide_path=self._stored_path(teacher_guide_path),
            student_reader_path=self._stored_path(student_reader_path),
            activity_book_path=self._stored_path(activity_book_path),
        )
        self.repository.save(record)
        return record

    def get_unit(self, curriculum_name: str, grade: str | int, unit: str | int) -> CurriculumUnit:
        record = self.repository.get(curriculum_name, str(grade), str(unit))
        if record is None:
            raise KeyError(f"No registered unit: {curriculum_name} grade {grade} unit {unit}")
        return record

    def list_units(self, curriculum_name: str | None = None) -> list[CurriculumUnit]:
        return self.repository.list(curriculum_name)

    def update_unit(self, curriculum_name: str, grade: str | int, unit: str | int, **changes: Any) -> CurriculumUnit:
        record = self.get_unit(curriculum_name, grade, unit)
        allowed = {"unit_title", "teacher_guide_path", "student_reader_path", "activity_book_path"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported update fields: {', '.join(sorted(unknown))}")
        for field in allowed & changes.keys():
            if field.endswith("_path"):
                changes[field] = self._stored_path(changes[field])
        updated = record.model_copy(update={**changes, "updated_at": utc_now()})
        self.repository.save(updated)
        return updated

    def remove_unit(self, curriculum_name: str, grade: str | int, unit: str | int) -> bool:
        return self.repository.remove(curriculum_name, str(grade), str(unit))

    def verify_files_exist(self, unit: CurriculumUnit) -> dict[str, bool]:
        fields = ("teacher_guide_path", "student_reader_path", "activity_book_path")
        return {field: bool(getattr(unit, field) and self.resolve_path(getattr(unit, field)).is_file()) for field in fields}
