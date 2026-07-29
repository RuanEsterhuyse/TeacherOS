"""Tests for opt-in Daily Lesson Google Slides publishing."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app import interface_server
from curriculum.intelligence.daily_lesson_generator import (
    generate_daily_lesson_package,
)
from curriculum.intelligence.daily_lesson_repository import (
    DailyLessonRepository,
)
from curriculum.intelligence.daily_lesson_google_slides import (
    DailyLessonGoogleSlidesPublisher,
)
from renderer.daily_lesson_google_slides import (
    DAILY_SLIDES_COLORS,
    DAILY_SLIDES_LAYOUTS,
    DailyLessonGoogleSlidesRenderer,
)
from schemas.daily_lesson_schema import DailyGoogleSlidesArtifact
from Tests.test_daily_lesson_generator import FakeProvider, _source


def package():
    source = _source()
    return generate_daily_lesson_package(
        source, provider=FakeProvider(source)
    )


def renderer_with_mocks(daily_package, *, folder=None):
    slides = MagicMock()
    presentations = slides.presentations.return_value
    presentations.create.return_value.execute.return_value = {
        "presentationId": "daily-deck-1",
        "slides": [{"objectId": "default-slide"}],
    }
    presentations.batchUpdate.return_value.execute.return_value = {}
    presentations.get.return_value.execute.return_value = {
        "slides": [
            {
                "objectId": DailyLessonGoogleSlidesRenderer._google_id(
                    "daily_slide", str(slide.slide_number)
                ),
                "slideProperties": {
                    "notesPage": {
                        "notesProperties": {
                            "speakerNotesObjectId": (
                                f"notes-{slide.slide_number}"
                            )
                        }
                    }
                },
            }
            for slide in daily_package.slide_outline
        ]
    }
    drive = MagicMock()
    drive.files.return_value.get.return_value.execute.return_value = {
        "parents": ["root"]
    }
    drive.files.return_value.update.return_value.execute.return_value = {
        "id": "daily-deck-1",
        "parents": [folder] if folder else ["root"],
    }
    drive.files.return_value.delete.return_value.execute.return_value = {}
    renderer = DailyLessonGoogleSlidesRenderer(
        slides_service=slides,
        drive_service=drive,
        drive_folder_id=folder,
    )
    return renderer, slides, drive


def requests(slides):
    return [
        value
        for call in (
            slides.presentations.return_value.batchUpdate.call_args_list
        )
        for value in call.kwargs["body"]["requests"]
    ]


def test_valid_presentation_creation_uses_one_slide_per_outline_item():
    daily_package = package()
    renderer, slides, _ = renderer_with_mocks(daily_package)

    result = renderer.create_daily_presentation(daily_package)

    creates = [
        value["createSlide"] for value in requests(slides)
        if "createSlide" in value
    ]
    assert result == {
        "status": "created",
        "presentation_id": "daily-deck-1",
        "presentation_url": (
            "https://docs.google.com/presentation/d/daily-deck-1/edit"
        ),
        "title": "Evidence Lesson 1 — Lesson 1",
        "slide_count": 2,
        "warnings": [],
    }
    assert len(creates) == len(daily_package.slide_outline)
    assert [value["insertionIndex"] for value in creates] == [0, 1]


@pytest.mark.parametrize("layout", sorted(DAILY_SLIDES_LAYOUTS))
def test_all_supported_layouts_render(layout):
    daily_package = package()
    slide = daily_package.slide_outline[0].model_copy(update={
        "suggested_layout": layout,
        "slide_number": 1,
    })
    candidate = daily_package.model_copy(update={"slide_outline": [slide]})
    renderer, slides, _ = renderer_with_mocks(candidate)

    result = renderer.create_daily_presentation(candidate)

    assert result["warnings"] == []
    assert len([
        value for value in requests(slides) if "createSlide" in value
    ]) == 1


def test_unknown_layout_falls_back_with_warning():
    daily_package = package()
    first = daily_package.slide_outline[0].model_copy(update={
        "suggested_layout": "floating holographic carousel",
    })
    candidate = daily_package.model_copy(update={
        "slide_outline": [first, daily_package.slide_outline[1]]
    })
    renderer, _, _ = renderer_with_mocks(candidate)

    result = renderer.create_daily_presentation(candidate)

    assert "used title_and_bullets" in result["warnings"][0]


def test_editable_text_and_design_system_values_are_api_shapes():
    daily_package = package()
    renderer, slides, _ = renderer_with_mocks(daily_package)

    renderer.create_daily_presentation(daily_package)
    output = requests(slides)

    assert any("createShape" in value for value in output)
    assert any("insertText" in value for value in output)
    background = next(
        value["updatePageProperties"]["pageProperties"][
            "pageBackgroundFill"
        ]["solidFill"]["color"]["rgbColor"]
        for value in output if "updatePageProperties" in value
    )
    assert background == renderer._rgb(DAILY_SLIDES_COLORS["background"])
    assert any(
        value.get("createShape", {}).get("shapeType") == "ROUND_RECTANGLE"
        for value in output
    )
    assert all(
        "shapeProperties" not in value.get("createShape", {})
        for value in output
    )
    assert any("updateShapeProperties" in value for value in output)


def test_teacher_guidance_is_inserted_only_in_speaker_notes():
    daily_package = package()
    renderer, slides, _ = renderer_with_mocks(daily_package)

    renderer.create_daily_presentation(daily_package)
    output = requests(slides)
    visible = "\n".join(
        value["insertText"]["text"]
        for value in output
        if "insertText" in value
        and not value["insertText"]["objectId"].startswith("notes-")
    )
    notes = "\n".join(
        value["insertText"]["text"]
        for value in output
        if value.get("insertText", {}).get("objectId", "").startswith(
            "notes-"
        )
    )

    assert "Name the claim first." not in visible
    assert "Name the claim first." in notes
    assert "Instructional purpose" in notes
    assert "Supported source references" in notes


def test_optional_drive_folder_moves_created_deck():
    daily_package = package()
    renderer, _, drive = renderer_with_mocks(
        daily_package, folder="folder-123"
    )

    renderer.create_daily_presentation(daily_package)

    drive.files.return_value.update.assert_called_once_with(
        fileId="daily-deck-1",
        addParents="folder-123",
        removeParents="root",
        fields="id,parents",
    )


def test_no_drive_folder_leaves_deck_in_default_location():
    daily_package = package()
    renderer, _, drive = renderer_with_mocks(daily_package)

    renderer.create_daily_presentation(daily_package)

    drive.files.return_value.get.assert_not_called()
    drive.files.return_value.update.assert_not_called()


def test_empty_outline_is_rejected_before_google_calls():
    daily_package = package().model_copy(update={"slide_outline": []})
    renderer, slides, _ = renderer_with_mocks(daily_package)

    with pytest.raises(ValueError, match="no slide outline"):
        renderer.create_daily_presentation(daily_package)

    slides.presentations.return_value.create.assert_not_called()


def test_missing_and_revoked_google_credentials_are_clear(tmp_path):
    repository = DailyLessonRepository(tmp_path / "daily")
    daily_package = package()
    repository.save(daily_package)
    missing = DailyLessonGoogleSlidesRenderer(
        credentials_path=tmp_path / "missing-credentials.json",
        token_path=tmp_path / "missing-token.json",
    )
    with pytest.raises(ValueError, match="credentials are missing"):
        DailyLessonGoogleSlidesPublisher(
            repository, renderer=missing
        ).publish(daily_package.package_id)

    revoked = MagicMock()
    revoked.create_daily_presentation.side_effect = RefreshError(
        "revoked"
    )
    with pytest.raises(ValueError, match="missing or revoked"):
        DailyLessonGoogleSlidesPublisher(
            repository, renderer=revoked
        ).publish(daily_package.package_id)


def test_google_api_failure_cleans_partial_deck():
    daily_package = package()
    renderer, slides, drive = renderer_with_mocks(daily_package)
    response = SimpleNamespace(status=500, reason="failure")
    slides.presentations.return_value.batchUpdate.return_value.execute.side_effect = (
        HttpError(response, b"failure")
    )

    with pytest.raises(ValueError, match="Google Slides API failed"):
        renderer.create_daily_presentation(daily_package)

    drive.files.return_value.delete.assert_called_once_with(
        fileId="daily-deck-1"
    )


def test_drive_api_failure_is_clear_and_cleans_partial_deck():
    daily_package = package()
    renderer, _, drive = renderer_with_mocks(
        daily_package, folder="folder-123"
    )
    response = SimpleNamespace(status=403, reason="forbidden")
    drive.files.return_value.update.return_value.execute.side_effect = (
        HttpError(response, b"forbidden")
    )

    with pytest.raises(ValueError, match="Google Drive API failed"):
        renderer.create_daily_presentation(daily_package)

    drive.files.return_value.delete.assert_called_once_with(
        fileId="daily-deck-1"
    )


def test_missing_notes_object_is_an_individual_render_failure_with_cleanup():
    daily_package = package()
    renderer, slides, drive = renderer_with_mocks(daily_package)
    slides.presentations.return_value.get.return_value.execute.return_value = {
        "slides": []
    }

    with pytest.raises(ValueError, match="speaker notes for slide 1"):
        renderer.create_daily_presentation(daily_package)

    drive.files.return_value.delete.assert_called_once_with(
        fileId="daily-deck-1"
    )


def test_backward_compatible_package_load_and_saved_metadata(tmp_path):
    repository = DailyLessonRepository(tmp_path / "daily")
    daily_package = package()
    repository.save(daily_package)
    path = (
        repository.package_directory(daily_package.package_id)
        / "daily_lesson_package.json"
    )
    legacy = json.loads(path.read_text(encoding="utf-8"))
    legacy.pop("google_slides", None)
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert repository.load(daily_package.package_id).google_slides is None

    renderer, _, _ = renderer_with_mocks(daily_package)
    result = DailyLessonGoogleSlidesPublisher(
        repository, renderer=renderer
    ).publish(daily_package.package_id)
    saved = repository.load(daily_package.package_id)

    assert result["presentation_id"] == "daily-deck-1"
    assert saved.google_slides.presentation_id == "daily-deck-1"
    assert saved.google_slides.slide_count == len(
        daily_package.slide_outline
    )


def test_failed_regeneration_preserves_previous_success(tmp_path):
    repository = DailyLessonRepository(tmp_path / "daily")
    daily_package = package().model_copy(update={
        "google_slides": DailyGoogleSlidesArtifact(
            presentation_id="previous-deck",
            presentation_url=(
                "https://docs.google.com/presentation/d/"
                "previous-deck/edit"
            ),
            slide_count=2,
            title="Previous deck",
        )
    })
    repository.save(daily_package)
    failed = MagicMock()
    failed.create_daily_presentation.side_effect = ValueError(
        "Google Slides API failed while creating the deck."
    )

    with pytest.raises(ValueError, match="Google Slides API failed"):
        DailyLessonGoogleSlidesPublisher(
            repository, renderer=failed
        ).publish(daily_package.package_id)

    assert (
        repository.load(daily_package.package_id)
        .google_slides.presentation_id
        == "previous-deck"
    )


def test_malformed_saved_slide_data_is_rejected(tmp_path):
    repository = DailyLessonRepository(tmp_path / "daily")
    daily_package = package()
    repository.save(daily_package)
    path = (
        repository.package_directory(daily_package.package_id)
        / "daily_lesson_package.json"
    )
    malformed = json.loads(path.read_text(encoding="utf-8"))
    malformed["slide_outline"][0]["exact_student_facing_text"] = []
    path.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed saved"):
        DailyLessonGoogleSlidesPublisher(
            repository, renderer=MagicMock()
        ).publish(daily_package.package_id)


def test_backend_endpoint_contract(monkeypatch):
    result = {
        "status": "created",
        "presentation_id": "deck-1",
        "presentation_url": (
            "https://docs.google.com/presentation/d/deck-1/edit"
        ),
        "title": "Lesson",
        "slide_count": 2,
        "warnings": [],
    }
    monkeypatch.setattr(
        interface_server,
        "INTERFACE",
        SimpleNamespace(
            create_daily_lesson_google_slides=lambda package_id: (
                result if package_id == "package-1" else None
            )
        ),
    )
    handler = object.__new__(interface_server.InterfaceRequestHandler)
    handler.path = "/api/daily-lessons/package-1/google-slides"
    handler.headers = {
        "Origin": "http://localhost:3000",
        interface_server.SESSION_HEADER:
            interface_server.LOCAL_SESSION_TOKEN,
    }
    handler._body = lambda: {}
    observed = {}
    handler._json = lambda payload, status=200: observed.update(
        payload=payload, status=status
    )

    handler.do_POST()

    assert observed == {"payload": result, "status": 201}


def test_renderer_does_not_parse_gemini_prompts():
    path = (
        Path(__file__).parents[1]
        / "renderer"
        / "daily_lesson_google_slides.py"
    )
    assert "gemini_slide_prompts" not in path.read_text(encoding="utf-8")
