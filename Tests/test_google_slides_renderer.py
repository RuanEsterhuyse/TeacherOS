"""Tests for deterministic Google Slides API rendering."""

from unittest.mock import MagicMock

import pytest

from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.lesson_schema import Lesson, Slide


def make_slide(slide_id: str, layout: str, title: str) -> Slide:
    return Slide(slide_id=slide_id, title=title, student_content=f"Content for {title}",
                 bullet_points=["First point", "Second point"],
                 speaker_notes=f"Notes for {title}", timing=5,
                 interaction="Ask students to discuss.", layout_type=layout,
                 visual_instructions="Markers and chart paper")


def renderer_with_mocks(slides: list[Slide]) -> tuple[GoogleSlidesRenderer, MagicMock]:
    service = MagicMock()
    presentations = service.presentations.return_value
    presentations.create.return_value.execute.return_value = {
        "presentationId": "presentation-1", "slides": [{"objectId": "default-slide"}]}
    presentations.get.return_value.execute.return_value = {"slides": [
        {"objectId": GoogleSlidesRenderer._google_id("slide", slide.slide_id),
         "slideProperties": {"notesPage": {"notesProperties": {
             "speakerNotesObjectId": f"notes-{slide.slide_id}"}}}}
        for slide in slides
    ]}
    return GoogleSlidesRenderer(slides_service=service, drive_service=MagicMock()), service


def all_requests(service: MagicMock) -> list[dict]:
    return [request for call in service.presentations.return_value.batchUpdate.call_args_list
            for request in call.kwargs["body"]["requests"]]


def test_create_presentation_has_correct_slide_count_and_order() -> None:
    slides = [make_slide("opening", "title", "Welcome"),
              make_slide("concept", "title-and-content", "Core Concept"),
              make_slide("check", "assessment", "Exit Ticket")]
    renderer, service = renderer_with_mocks(slides)
    result = renderer.create_presentation(
        Lesson(grade="8", unit="Unit 1", lesson_number=2, slides=slides))
    creates = [item["createSlide"] for item in all_requests(service) if "createSlide" in item]
    assert len(creates) == 3
    assert [item["insertionIndex"] for item in creates] == [0, 1, 2]
    assert [item["objectId"] for item in creates] == result["slideIds"]


def test_speaker_notes_are_placed_in_each_notes_object() -> None:
    slides = [make_slide("discussion", "discussion", "Discuss")]
    renderer, service = renderer_with_mocks(slides)
    renderer.create_presentation(Lesson(grade="8", unit="Unit 1", lesson_number=1, slides=slides))
    inserts = [item["insertText"] for item in all_requests(service)
               if item.get("insertText", {}).get("objectId") == "notes-discussion"]
    assert inserts[0]["text"].startswith(
        "Teacher notes: Notes for Discuss\nTiming: 5 minutes\n"
        "Teacher directions: Ask students to discuss.\nMaterials: Markers and chart paper")
    assert "Layout type: discussion" in inserts[0]["text"]


def test_empty_slide_renders_title_without_empty_body_shape() -> None:
    slide = Slide(slide_id="empty", title="Pause", layout_type="content")
    renderer, service = renderer_with_mocks([slide])
    renderer.create_presentation(Lesson(grade="8", unit="Unit 1", lesson_number=1, slides=[slide]))
    shapes = [item["createShape"]["objectId"] for item in all_requests(service) if "createShape" in item]
    assert shapes == [GoogleSlidesRenderer._google_id("title", "empty")]


def test_invalid_layout_is_rejected_before_api_creation() -> None:
    slide = make_slide("bad", "three-dimensional-carousel", "Bad")
    renderer, service = renderer_with_mocks([slide])
    with pytest.raises(ValueError, match="Unsupported slide layout"):
        renderer.create_presentation(Lesson(grade="8", unit="1", lesson_number=1, slides=[slide]))
    service.presentations.return_value.create.assert_not_called()


def test_long_text_is_preserved_and_uses_smaller_font() -> None:
    slide = make_slide("long", "content", "Long Reading")
    slide.student_content = "A" * 1_300
    renderer, service = renderer_with_mocks([slide])
    renderer.create_presentation(Lesson(grade="8", unit="1", lesson_number=1, slides=[slide]))
    body_id = GoogleSlidesRenderer._google_id("body", "long")
    requests = all_requests(service)
    insert = next(item["insertText"] for item in requests
                  if item.get("insertText", {}).get("objectId") == body_id)
    style = next(item["updateTextStyle"] for item in requests
                 if item.get("updateTextStyle", {}).get("objectId") == body_id)
    assert insert["text"].startswith("A" * 1_300)
    assert style["style"]["fontSize"]["magnitude"] == 12
