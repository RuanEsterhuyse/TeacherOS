"""Atomic persistence for ignored Daily Lesson Generator packages."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from schemas.daily_lesson_schema import DailyLessonPackage, DailyLessonStatus


class DailyLessonRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def package_directory(self, package_id: str) -> Path:
        if not package_id or not all(
            character.isalnum() or character in "_-"
            for character in package_id
        ):
            raise ValueError("Invalid daily package identifier.")
        return self.root / package_id

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(
            prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(content)
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def save(self, package: DailyLessonPackage) -> Path:
        directory = self.package_directory(package.package_id)
        json_path = directory / "daily_lesson_package.json"
        if json_path.is_file():
            existing = self.load(package.package_id)
            if (
                existing.status == DailyLessonStatus.complete
                and package.status != DailyLessonStatus.complete
            ):
                return directory
        payload: dict[str, Any] = package.model_dump(mode="json")
        self._atomic_write(
            json_path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
        self._atomic_write(
            directory / "teacher_playbook.md",
            package.teacher_playbook_markdown,
        )
        if package.gemini_slide_prompts:
            from renderer.daily_lesson_markdown import render_slide_prompts

            self._atomic_write(
                directory / "gemini_slide_prompts.md",
                render_slide_prompts(package),
            )
        return directory

    def load(self, package_id: str) -> DailyLessonPackage:
        path = self.package_directory(package_id) / "daily_lesson_package.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            return DailyLessonPackage.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, ValueError) as error:
            raise ValueError("Malformed saved daily lesson package.") from error

    def list_packages(self) -> list[DailyLessonPackage]:
        output = []
        for path in sorted(self.root.glob("*/daily_lesson_package.json")):
            try:
                output.append(DailyLessonPackage.model_validate_json(
                    path.read_text(encoding="utf-8")
                ))
            except (OSError, ValidationError, ValueError):
                continue
        return output

    def read_markdown(self, package_id: str, artifact: str) -> str:
        allowed = {"teacher_playbook.md", "gemini_slide_prompts.md"}
        if artifact not in allowed:
            raise ValueError("Unsupported daily lesson artifact.")
        path = self.package_directory(package_id) / artifact
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8")


__all__ = ["DailyLessonRepository"]
