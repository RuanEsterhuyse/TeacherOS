"""Render compact metadata from the canonical lesson."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from renderer.lesson_renderer import LessonRenderer
from schemas.canonical_lesson_schema import CanonicalLesson


class LessonMetadataRenderer(LessonRenderer[dict[str, Any]]):
    def render(self, lesson: CanonicalLesson) -> dict[str, Any]:
        info = lesson.lesson_information
        mappings = [
            mapping
            for block in lesson.lesson_blocks
            for mapping in (
                block.slide_mappings
                + [
                    mapping
                    for chunk in block.reading_chunks
                    for mapping in chunk.slide_mappings
                ]
            )
        ]
        return {
            "schema_version": lesson.schema_version,
            "curriculum": info.curriculum,
            "grade": info.grade,
            "unit": info.unit,
            "lesson_number": info.lesson_number,
            "lesson_title": info.lesson_title,
            "duration_minutes": info.duration_minutes,
            "standards": lesson.standards,
            "block_count": len(lesson.lesson_blocks),
            "reading_chunk_count": sum(
                len(block.reading_chunks) for block in lesson.lesson_blocks
            ),
            "slide_count": len(mappings),
            "resource_availability": {
                resource.id: resource.availability.value
                for resource in lesson.instructional_resources
            },
            "source_digest": lesson.source_digest,
        }

    def write(self, lesson: CanonicalLesson, directory: str | Path) -> Path:
        path = Path(directory) / "lesson_metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.render(lesson), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path


__all__ = ["LessonMetadataRenderer"]
