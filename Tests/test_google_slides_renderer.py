"""Tests for deterministic Google Slides API rendering."""

from unittest.mock import MagicMock
from pathlib import Path

import pytest

from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.lesson_schema import Lesson, Slide
from schemas.presentation_design_schema import (PresentationDesignOutput, PresentationSlide, StudentView,
    TeacherNotes, SlideDesign, VisualPlan, InteractionPlan)
from renderer.presentation_theme import load_presentation_theme
from brain.presentation_expander import expand_presentation


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


def rich_slide(slide_id="windows", layout="question_focus", **kwargs) -> PresentationSlide:
    return PresentationSlide(slide_id=slide_id, sequence_number=kwargs.pop("sequence_number", 1),
        slide_type=kwargs.pop("slide_type", "discussion"),
        student_view=kwargs.pop("student_view", StudentView(title="Windows and Mirrors",
            prompt="How can a text be both a window and a mirror?", sentence_frames=["It is a mirror because …"],
            directions=["Discuss with a partner."], footer_text="Lección 1 · Perspectivas")),
        teacher_notes=kwargs.pop("teacher_notes", TeacherNotes(instructional_purpose="Connect identity and perspective.",
            teacher_script="Explain the metaphor.", anticipated_responses=["A reader recognizes an experience."],
            eld_supports=["Rehearse before sharing."])), design=SlideDesign(layout=layout),
        visuals=kwargs.pop("visuals", VisualPlan()), interaction=kwargs.pop("interaction", InteractionPlan(
            interaction_type="turn_and_talk", duration_minutes=2, grouping="partners", response_mode="oral")),
        source_references=["Teacher Guide p. 1"], fidelity_classification="source_adapted", **kwargs)


def rich_renderer(slides: list[PresentationSlide]) -> tuple[GoogleSlidesRenderer, MagicMock]:
    expanded = expand_presentation(PresentationDesignOutput(request_id="test", slides=slides)).slides
    service = MagicMock(); presentations = service.presentations.return_value
    presentations.create.return_value.execute.return_value = {"presentationId": "rich-1", "slides": [{"objectId": "default"}]}
    presentations.get.return_value.execute.return_value = {"slides": [{"objectId": GoogleSlidesRenderer._google_id("slide", s.slide_id),
        "slideProperties": {"notesPage": {"notesProperties": {"speakerNotesObjectId": f"notes-{s.slide_id}"}}}} for s in expanded]}
    return GoogleSlidesRenderer(slides_service=service, drive_service=MagicMock()), service


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


def test_theme_loading_defaults_and_partial_override(tmp_path) -> None:
    path = tmp_path / "theme.json"; path.write_text('{"colors":{"accent":"#000000"}}', encoding="utf-8")
    theme = load_presentation_theme(path)
    assert theme["colors"]["accent"] == "#000000"
    assert theme["typography"]["minimum_body_size"] == 18
    assert load_presentation_theme(tmp_path / "missing.json")["dimensions"]["aspect_ratio"] == "16:9"


@pytest.mark.parametrize("layout", sorted(GoogleSlidesRenderer.RICH_LAYOUTS))
def test_rich_layout_dispatch(layout) -> None:
    slide = rich_slide(layout=layout)
    renderer, service = rich_renderer([slide])
    result = renderer.create_presentation(PresentationDesignOutput(request_id="r1", lesson_title="Lesson", slides=[slide]))
    assert len(result["slideIds"]) >= 1
    assert any("createSlide" in request for request in all_requests(service))


def test_rich_visible_content_excludes_teacher_notes_and_preserves_spanish() -> None:
    slide = rich_slide()
    renderer, service = rich_renderer([slide])
    renderer.create_presentation(PresentationDesignOutput(request_id="r1", slides=[slide]))
    visible = "\n".join(request["insertText"]["text"] for request in all_requests(service)
        if "insertText" in request and not request["insertText"]["objectId"].startswith("notes-"))
    notes = next(request["insertText"]["text"] for request in all_requests(service)
        if request.get("insertText", {}).get("objectId") == "notes-windows")
    assert "Perspectivas" in visible
    assert "Explain the metaphor" not in visible
    assert "Teacher Script\nExplain the metaphor" in notes
    assert "Sources\n• Teacher Guide p. 1" in notes


def test_overflow_paths_and_missing_visual_create_warnings_without_leaking_prompt() -> None:
    view = StudentView(title="Evidence", body_text=" ".join(["palabra"] * 70) + " /private/book.pdf")
    visual = VisualPlan(visual_required=True, visual_type="illustration", image_prompt="Secret detailed prompt",
                        visual_description="Window and mirror", alt_text="A window and mirror")
    slide = rich_slide(layout="split_visual", student_view=view, visuals=visual)
    renderer, service = rich_renderer([slide])
    result = renderer.create_presentation(PresentationDesignOutput(request_id="r1", slides=[slide]))
    codes = {warning["code"] for warning in result["warnings"]}
    visible = " ".join(request["insertText"]["text"] for request in all_requests(service)
        if "insertText" in request and not request["insertText"]["objectId"].startswith("notes-"))
    assert {"visible_file_path", "missing_visual_asset"} <= codes
    assert len(result["slideIds"]) > 1
    assert "/private" not in visible and "Secret detailed prompt" not in visible


def test_ckla_attribution_is_preserved_in_final_speaker_notes_not_visible_slide() -> None:
    slide = rich_slide()
    renderer, service = rich_renderer([slide])
    renderer.create_presentation(PresentationDesignOutput(request_id="ckla-grade-8-unit-1-lesson-1", slides=[slide]))
    requests = all_requests(service)
    notes = next(r["insertText"]["text"] for r in requests if r.get("insertText", {}).get("objectId") == "notes-windows")
    visible = " ".join(r["insertText"]["text"] for r in requests if "insertText" in r and r["insertText"]["objectId"] != "notes-windows")
    assert "Creative Commons Attribution-NonCommercial-ShareAlike 4.0" in notes
    assert "Creative Commons Attribution-NonCommercial" not in visible


def test_offline_lesson_1_sample_renders_seven_semantic_layouts() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_lesson_1_presentation_design.json"
    presentation = PresentationDesignOutput.model_validate_json(fixture.read_text(encoding="utf-8"))
    renderer, service = rich_renderer(presentation.slides)
    result = renderer.create_presentation(presentation)
    creates = [request for request in all_requests(service) if "createSlide" in request]
    assert len(creates) == len(result["slideIds"])
    assert len(result["slideIds"]) >= 7
    assert {slide.design.layout.value for slide in presentation.slides} == {
        "title_hero", "split_visual", "question_focus", "vocabulary_cards",
        "discussion_prompt", "evidence_chart", "exit_ticket"}


def test_semantic_layout_regions_do_not_overlap_or_leave_slide_bounds() -> None:
    renderer = GoogleSlidesRenderer(slides_service=MagicMock(), drive_service=MagicMock())
    kind_by_layout = {"title_hero":"hero", "day_divider":"divider", "split_visual":"split",
        "question_focus":"question", "quote_focus":"quote", "map_focus":"visual_primary",
        "vocabulary_cards":"cards", "three_card":"cards", "reading_checkpoint":"checkpoint",
        "discussion_prompt":"question", "activity_steps":"steps", "comparison":"columns",
        "evidence_chart":"columns", "exit_ticket":"exit", "minimal_text":"minimal", "no_visual":"text"}
    for layout, kind in kind_by_layout.items():
        slide = rich_slide(layout=layout)
        renderer._validate_boxes(slide, renderer._rich_geometry(kind, slide))


def test_rich_font_sizes_never_fall_below_classroom_minimums() -> None:
    slide = rich_slide(student_view=StudentView(title="A long but readable classroom title",
        body_text="Students analyze evidence and explain how it supports an interpretation."))
    renderer, service = rich_renderer([slide])
    renderer.create_presentation(PresentationDesignOutput(request_id="r1", slides=[slide]))
    styles = [r["updateTextStyle"]["style"]["fontSize"]["magnitude"] for r in all_requests(service)
              if "updateTextStyle" in r]
    assert min(styles) >= 14
    title_id = GoogleSlidesRenderer._google_id("title", slide.slide_id)
    title_size = next(r["updateTextStyle"]["style"]["fontSize"]["magnitude"] for r in all_requests(service)
        if r.get("updateTextStyle", {}).get("objectId") == title_id)
    assert title_size >= 28
