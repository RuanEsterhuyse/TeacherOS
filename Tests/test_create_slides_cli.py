"""Tests for the validated-lesson to Google Slides CLI handoff."""

import json

from app import cli


def validated_lesson() -> dict:
    return {
        "grade": "8",
        "unit": "1",
        "lesson_number": 1,
        "slides": [{
            "slide_id": "opening",
            "title": "Opening",
            "student_content": "Welcome",
            "speaker_notes": "Introduce the lesson.",
            "timing": 2,
            "interaction": "Greet students.",
            "layout_type": "title",
        }],
    }


def test_create_slides_loads_validated_file_and_calls_renderer(tmp_path, monkeypatch, capsys) -> None:
    run = tmp_path / "ckla-grade-8-unit-1-lesson-1"
    run.mkdir()
    (run / "07_validated_lesson.json").write_text(json.dumps(validated_lesson()), encoding="utf-8")
    received = []

    class FakeRenderer:
        def __init__(self, **kwargs):
            pass

        def create_presentation(self, lesson):
            received.append(lesson)
            return {"presentationId": "deck-1", "url": "https://example.test/deck-1",
                    "slideIds": ["slide-1"]}

    monkeypatch.setattr(cli, "GoogleSlidesRenderer", FakeRenderer)
    result = cli.main(["create-slides", "--curriculum", "CKLA", "--grade", "8", "--unit", "1",
                       "--lesson", "1", "--generation-output-directory", str(tmp_path)])

    assert result == 0
    assert len(received) == 1
    assert received[0].slides[0].title == "Opening"
    output = capsys.readouterr().out
    assert "Presentation ID: deck-1" in output
    assert "Slides created: 1" in output


def test_create_slides_rejects_mismatched_lesson_identity(tmp_path, monkeypatch, capsys) -> None:
    run = tmp_path / "ckla-grade-8-unit-1-lesson-1"
    run.mkdir()
    payload = validated_lesson()
    payload["lesson_number"] = 2
    (run / "07_validated_lesson.json").write_text(json.dumps(payload), encoding="utf-8")

    result = cli.main(["create-slides", "--grade", "8", "--unit", "1", "--lesson", "1",
                       "--generation-output-directory", str(tmp_path)])

    assert result == 2
    assert "identity does not match" in capsys.readouterr().err
