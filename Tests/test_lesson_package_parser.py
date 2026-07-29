"""Tests for deterministic Lesson Package parsing and renderer handoff."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from brain.lesson_package_parser import LessonPackageError, parse_lesson_package
from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.lesson_schema import Lesson


FIXTURE = Path(__file__).parent / "fixtures" / "realistic_lesson_package.json"


def package_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_realistic_package_has_correct_count_order_and_validates() -> None:
    lesson = parse_lesson_package(FIXTURE)

    assert isinstance(lesson, Lesson)
    assert len(lesson.slides) == 4
    assert [slide.slide_id for slide in lesson.slides] == ["S01", "S02", "S03", "S04"]
    assert lesson.slides[0].student_content.startswith("Stories of Belonging")
    assert lesson.slides[0].interaction == "Preview the title in students' books."
    assert lesson.slides[0].visual_instructions == "Student reader"
    assert lesson.slides[2].timing == 3
    assert lesson.activities[0].title == "Concept web"
    assert lesson.vocabulary[0].term == "identity"
    assert lesson.assessments[0].assessment_type == "exit ticket"
    assert lesson.homework[0].title == "Read The Crossing"


def test_declared_slide_order_controls_output() -> None:
    package = package_data()
    package["slide_order"] = ["S04", "S02", "S01", "S03"]

    lesson = parse_lesson_package(package)

    assert [slide.slide_id for slide in lesson.slides] == package["slide_order"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda package: package["slides"][0].update(title=""), "Missing slide title"),
        (lambda package: package["slides"][0].update(speaker_notes=""), "Missing speaker notes"),
        (lambda package: package["lesson_metadata"].pop("grade"), "Missing lesson metadata"),
        (lambda package: package["slides"][0].update(timing="about five minutes"), "Invalid timing"),
    ],
)
def test_required_package_validation(mutation, message: str) -> None:
    package = package_data()
    mutation(package)

    with pytest.raises(LessonPackageError, match=message):
        parse_lesson_package(package)


def test_duplicate_slide_ids_are_rejected() -> None:
    package = package_data()
    package["slides"][1]["slide_id"] = "S01"

    with pytest.raises(LessonPackageError, match="Duplicate slide ID"):
        parse_lesson_package(package)


def test_legacy_day_divider_zero_timing_becomes_absent_renderer_timing() -> None:
    package = package_data()
    package["slides"][0].pop("layout_type", None)
    package["slides"][0]["slide_type"] = "day divider"
    package["slides"][0]["timing"] = 0
    lesson = parse_lesson_package(package)
    assert lesson.slides[0].layout_type == "day divider"
    assert lesson.slides[0].timing is None


def test_legacy_normal_slide_zero_and_negative_timing_are_rejected() -> None:
    for invalid in (0, -1):
        package = package_data()
        package["slides"][0]["timing"] = invalid
        with pytest.raises(LessonPackageError, match="must be positive"):
            parse_lesson_package(package)


def test_parsed_lesson_passes_directly_to_unchanged_renderer() -> None:
    lesson = parse_lesson_package(FIXTURE)
    slides_service = MagicMock()
    presentations = slides_service.presentations.return_value
    presentations.create.return_value.execute.return_value = {
        "presentationId": "parsed-lesson", "slides": []
    }
    presentations.get.return_value.execute.return_value = {
        "slides": [
            {
                "objectId": GoogleSlidesRenderer._google_id("slide", slide.slide_id),
                "slideProperties": {"notesPage": {"notesProperties": {
                    "speakerNotesObjectId": f"notes-{slide.slide_id}"
                }}},
            }
            for slide in lesson.slides
        ]
    }
    renderer = GoogleSlidesRenderer(
        slides_service=slides_service, drive_service=MagicMock()
    )

    result = renderer.create_presentation(lesson)

    assert len(result["slideIds"]) == len(lesson.slides)
    assert len(presentations.batchUpdate.call_args_list) == len(lesson.slides) * 2
