"""Convert structured Lesson Packages into validated renderer-ready lessons.

This module deliberately contains no curriculum interpretation or generation.
It only validates package structure, renames package fields to their existing
domain-model equivalents, and delegates final validation to Pydantic.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from schemas.lesson_schema import Lesson


class LessonPackageError(ValueError):
    """Raised when a Lesson Package cannot be transformed without guessing."""


class LessonPackageParser:
    """Parse a JSON-compatible Lesson Package into the existing Lesson schema."""

    _MINUTES = re.compile(r"^\s*(\d+)\s*(?:min(?:ute)?s?\.?)?\s*$", re.IGNORECASE)

    def parse(self, package: Mapping[str, Any] | str | Path) -> Lesson:
        """Return a validated ``Lesson`` while preserving the declared slide order."""
        data = self._read(package)
        metadata = self._metadata(data)
        slides = self._slides(data)

        lesson_data = {
            "grade": metadata["grade"],
            "unit": metadata["unit"],
            "lesson_number": metadata["lesson_number"],
            "slides": slides,
            "activities": data.get("activities", []),
            "homework": data.get("homework", []),
            "vocabulary": data.get("vocabulary", []),
            "assessments": data.get("assessments", []),
        }
        try:
            return Lesson.model_validate(lesson_data)
        except ValidationError as exc:
            raise LessonPackageError(f"Lesson Package does not match the Lesson schema: {exc}") from exc

    @staticmethod
    def _read(package: Mapping[str, Any] | str | Path) -> dict[str, Any]:
        if isinstance(package, Mapping):
            return dict(package)
        path = Path(package)
        if path.suffix.lower() != ".json":
            raise LessonPackageError("Lesson Packages must be structured JSON files")
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LessonPackageError(f"Unable to read Lesson Package {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise LessonPackageError("Lesson Package root must be an object")
        return loaded

    @staticmethod
    def _metadata(data: Mapping[str, Any]) -> Mapping[str, Any]:
        metadata = data.get("lesson_metadata")
        required = ("title", "grade", "unit", "lesson_number")
        if not isinstance(metadata, Mapping):
            raise LessonPackageError("Missing lesson metadata: lesson_metadata")
        missing = [name for name in required if metadata.get(name) in (None, "")]
        if missing:
            raise LessonPackageError(f"Missing lesson metadata: {', '.join(missing)}")
        return metadata

    def _slides(self, data: Mapping[str, Any]) -> list[dict[str, Any]]:
        order = data.get("slide_order")
        raw_slides = data.get("slides")
        if not isinstance(order, list) or not order:
            raise LessonPackageError("slide_order must be a non-empty list")
        if len(order) != len(set(order)):
            raise LessonPackageError("Duplicate slide IDs in slide_order")
        if not isinstance(raw_slides, (list, Mapping)):
            raise LessonPackageError("slides must be a list or object")

        by_id: dict[str, Mapping[str, Any]] = {}
        source = raw_slides.values() if isinstance(raw_slides, Mapping) else raw_slides
        for position, slide in enumerate(source, start=1):
            if not isinstance(slide, Mapping):
                raise LessonPackageError(f"Slide {position} must be an object")
            slide_id = slide.get("slide_id")
            if not isinstance(slide_id, str) or not slide_id.strip():
                raise LessonPackageError(f"Slide {position} is missing slide_id")
            if slide_id in by_id:
                raise LessonPackageError(f"Duplicate slide ID: {slide_id}")
            by_id[slide_id] = slide

        order_set = set(order)
        missing = [slide_id for slide_id in order if slide_id not in by_id]
        unlisted = [slide_id for slide_id in by_id if slide_id not in order_set]
        if missing or unlisted:
            details = []
            if missing:
                details.append(f"missing slides: {', '.join(map(str, missing))}")
            if unlisted:
                details.append(f"slides absent from slide_order: {', '.join(unlisted)}")
            raise LessonPackageError("slide_order does not match slides (" + "; ".join(details) + ")")
        return [self._transform_slide(by_id[slide_id]) for slide_id in order]

    def _transform_slide(self, slide: Mapping[str, Any]) -> dict[str, Any]:
        slide_id = str(slide["slide_id"])
        if not isinstance(slide.get("title"), str) or not slide["title"].strip():
            raise LessonPackageError(f"Missing slide title: {slide_id}")
        if not isinstance(slide.get("speaker_notes"), str) or not slide["speaker_notes"].strip():
            raise LessonPackageError(f"Missing speaker notes: {slide_id}")

        return {
            "slide_id": slide_id,
            "title": slide["title"],
            "student_content": slide.get("student_facing_content", slide.get("student_content", "")),
            "bullet_points": slide.get("bullet_points", []),
            "speaker_notes": slide["speaker_notes"],
            "timing": self._timing(slide.get("timing"), slide_id),
            "interaction": slide.get("teacher_directions", slide.get("interaction")),
            "layout_type": slide.get("layout_type", slide.get("type", slide.get("slide_type"))),
            "visual_instructions": slide.get("visual_direction", slide.get("materials", slide.get("visual_instructions"))),
            "image_prompt": slide.get("image_prompt"),
            "source_references": slide.get("source_references", []),
        }

    def _timing(self, value: Any, slide_id: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise LessonPackageError(f"Invalid timing for slide {slide_id}: {value!r}")
        if isinstance(value, int):
            minutes = value
        elif isinstance(value, str) and (match := self._MINUTES.fullmatch(value)):
            minutes = int(match.group(1))
        else:
            raise LessonPackageError(f"Invalid timing for slide {slide_id}: {value!r}")
        if minutes <= 0:
            raise LessonPackageError(f"Invalid timing for slide {slide_id}: must be positive")
        return minutes


def parse_lesson_package(package: Mapping[str, Any] | str | Path) -> Lesson:
    """Convenience entry point for parsing one Lesson Package."""
    return LessonPackageParser().parse(package)
