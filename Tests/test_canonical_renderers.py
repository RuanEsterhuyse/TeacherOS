"""Tests proving all canonical renderers use the same instructional objects."""

import fitz

from renderer.canonical_slides import (
    CanonicalSlidesRenderer,
    canonical_to_presentation_design,
    speaker_notes_for,
)
from renderer.canonical_teacher_companion import (
    CanonicalTeacherCompanionRenderer,
)
from renderer.lesson_metadata import LessonMetadataRenderer
from renderer.teacher_companion_pdf import TeacherCompanionPdfRenderer
from renderer.google_slides_renderer import GoogleSlidesRenderer
from Tests.test_canonical_lesson_schema import canonical_lesson


def test_companion_slides_notes_and_metadata_share_canonical_content(
    tmp_path,
) -> None:
    lesson = canonical_lesson()
    block = lesson.lesson_blocks[0]
    block.teacher_guidance.directions = []
    companion = CanonicalTeacherCompanionRenderer().render(lesson)
    slides = CanonicalSlidesRenderer().render(lesson)
    notes = speaker_notes_for(lesson)
    metadata = LessonMetadataRenderer().render(lesson)

    assert block.title in companion
    assert slides["slides"][0]["lesson_block_id"] == block.id
    assert notes["speaker_notes"][0]["lesson_block_id"] == block.id
    assert metadata["source_digest"] == lesson.source_digest
    assert slides["source_digest"] == lesson.source_digest
    assert notes["source_digest"] == lesson.source_digest


def test_slide_projection_preserves_declared_order_and_content() -> None:
    lesson = canonical_lesson()

    presentation = canonical_to_presentation_design(lesson)

    assert [item.slide_id for item in presentation.slides] == ["slide-1"]
    assert presentation.slides[0].student_view.title == "Discuss the text"
    assert (
        presentation.slides[0].student_view.body_text
        == "What do you notice?"
    )


def test_companion_pdf_is_valid_and_contains_pages(tmp_path) -> None:
    lesson = canonical_lesson()
    path = TeacherCompanionPdfRenderer().write(lesson, tmp_path)

    with fitz.open(path) as document:
        assert document.page_count >= 1
        text = "\n".join(page.get_text() for page in document)
    assert lesson.lesson_information.lesson_title in text


def test_google_slides_accepts_canonical_lesson_without_new_structure(
    monkeypatch,
) -> None:
    lesson = canonical_lesson()
    renderer = GoogleSlidesRenderer()
    captured = {}

    def render(presentation):
        captured["presentation"] = presentation
        return {"presentationId": "p1", "slideIds": ["slide-1"]}

    monkeypatch.setattr(renderer, "create_rich_presentation", render)

    result = renderer.create_presentation(lesson)

    assert result["slideIds"] == ["slide-1"]
    assert [
        item.slide_id for item in captured["presentation"].slides
    ] == ["slide-1"]
