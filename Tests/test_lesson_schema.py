"""Tests for the renderer-ready lesson schema."""

import json

import pytest
from pydantic import ValidationError

from schemas.lesson_schema import Lesson, Slide


def valid_slide_data() -> dict[str, object]:
    return {
        "slide_id": "slide-01",
        "title": "Opening Question",
        "student_content": "What do you notice?",
        "bullet_points": ["Observe", "Discuss with a partner"],
        "speaker_notes": "Allow two minutes for partner discussion.",
        "timing": 3,
        "interaction": "think-pair-share",
        "layout_type": "title-and-content",
        "visual_instructions": "Use one relevant, uncluttered image.",
        "image_prompt": "A classroom-safe historical landscape",
        "source_references": ["Teacher Guide, p. 12"],
    }


def test_slide_schema_accepts_all_required_fields() -> None:
    slide = Slide.model_validate(valid_slide_data())

    assert slide.slide_id == "slide-01"
    assert slide.timing == 3
    assert slide.source_references == ["Teacher Guide, p. 12"]


def test_slide_schema_rejects_missing_layout() -> None:
    data = valid_slide_data()
    del data["layout_type"]

    with pytest.raises(ValidationError):
        Slide.model_validate(data)


def test_lesson_schema_validates_nested_content() -> None:
    lesson = Lesson.model_validate(
        {
            "grade": "8",
            "unit": "1",
            "lesson_number": 1,
            "slides": [valid_slide_data()],
            "activities": [
                {
                    "activity_id": "activity-01",
                    "title": "Partner discussion",
                    "instructions": "Discuss the opening question.",
                    "duration_minutes": 5,
                    "interaction": "pairs",
                }
            ],
            "homework": [],
            "vocabulary": [{"term": "evidence", "definition": "Information supporting a claim."}],
            "assessments": [],
        }
    )

    assert lesson.lesson_number == 1
    assert lesson.slides[0].title == "Opening Question"
    assert lesson.vocabulary[0].term == "evidence"


def test_lesson_rejects_duplicate_slide_ids() -> None:
    duplicate = valid_slide_data()

    with pytest.raises(ValidationError, match="slide_id values must be unique"):
        Lesson.model_validate(
            {
                "grade": "8",
                "unit": "1",
                "lesson_number": 1,
                "slides": [duplicate, duplicate],
            }
        )


def test_lesson_validates_from_json() -> None:
    payload = json.dumps(
        {
            "grade": "8",
            "unit": "1",
            "lesson_number": 1,
            "slides": [valid_slide_data()],
        }
    )

    lesson = Lesson.model_validate_json(payload)

    assert lesson.model_dump(mode="json")["slides"][0]["slide_id"] == "slide-01"


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Lesson.model_validate_json('{"grade": "8",')
