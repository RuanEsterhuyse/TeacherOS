"""Create a readable PDF from the canonical Teacher Companion rendering."""

from __future__ import annotations

from pathlib import Path
import textwrap

import fitz

from renderer.canonical_teacher_companion import (
    CanonicalTeacherCompanionRenderer,
)
from renderer.lesson_renderer import LessonRenderer
from schemas.canonical_lesson_schema import CanonicalLesson


class TeacherCompanionPdfRenderer(LessonRenderer[bytes]):
    def render(self, lesson: CanonicalLesson) -> bytes:
        markdown = CanonicalTeacherCompanionRenderer().render(lesson)
        document = fitz.open()
        page = document.new_page()
        y = 54.0
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                y += 7
                continue
            heading = line.startswith("#")
            text = line.lstrip("#").strip() if heading else line
            size = 16 if line.startswith("# ") else 12 if heading else 9
            fragments = textwrap.wrap(
                text,
                width=55 if heading else 90,
                replace_whitespace=False,
                drop_whitespace=True,
            ) or [""]
            for fragment in fragments:
                height = 24 if heading else 14
                if y + height > page.rect.height - 54:
                    page = document.new_page()
                    y = 54.0
                page.insert_textbox(
                    fitz.Rect(54, y, page.rect.width - 54, y + height),
                    fragment,
                    fontsize=size,
                    fontname="helv",
                    lineheight=1.2,
                )
                y += height
        payload = document.tobytes()
        document.close()
        return payload

    def write(self, lesson: CanonicalLesson, directory: str | Path) -> Path:
        path = Path(directory) / "teacher_companion.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.render(lesson))
        return path


__all__ = ["TeacherCompanionPdfRenderer"]
