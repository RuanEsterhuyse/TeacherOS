"""Tests for provider-neutral curriculum adapter selection and delegation."""

from __future__ import annotations

import json

import pytest

from app.teacheros import TeacherOS
from curriculum.adapters import (
    CKLAAdapter,
    CurriculumAdapter,
    default_adapter_registry,
)
from curriculum.cli import main as curriculum_main
from curriculum.lesson_locator import CKLALessonLocator
from schemas.lesson_package_schema import CKLA_ATTRIBUTION
from Tests.test_generation_pipeline import PipelineClient
from Tests.test_teacheros import make_pdf, prepared_fixture


def test_default_registry_selects_ckla_case_insensitively(tmp_path) -> None:
    registry = default_adapter_registry()

    adapter = registry.create(
        "ckla",
        index_directory=tmp_path / "indexes",
    )

    assert isinstance(adapter, CurriculumAdapter)
    assert isinstance(adapter, CKLAAdapter)
    assert adapter.supports("CKLA")
    assert adapter.locator.index_directory == tmp_path / "indexes"


def test_registry_rejects_unregistered_curriculum(tmp_path) -> None:
    with pytest.raises(KeyError, match="No curriculum adapter registered"):
        default_adapter_registry().create(
            "Wit & Wisdom",
            index_directory=tmp_path / "indexes",
        )


def test_ckla_adapter_exposes_provider_policy_and_existing_behavior(
    tmp_path,
) -> None:
    guide = tmp_path / "guide.pdf"
    make_pdf(
        guide,
        [
            "LESSON 1\nAT A GLANCE CHART\nLesson Time Activity Materials\n"
            "DAY 1: Reading 45 min Close Reading: \"First Story\" "
            "Reader Book Activity Page 1.1\n"
            "Primary Focus Objectives\n"
            "By the end of this lesson, students will be able to:\nReading\n"
            "Cite textual evidence. (RL.8.1)\nADVANCE PREPARATION\n"
            "Lesson one exact text",
            "Lesson one continuation",
        ],
    )
    service, _ = prepared_fixture(tmp_path / "registered")
    curriculum = service.library.get_unit("CKLA", 8, 1)
    curriculum.teacher_guide_path = str(guide)
    locator = CKLALessonLocator(index_directory=tmp_path / "indexes")
    adapter = CKLAAdapter(locator=locator)

    index = adapter.detect_lesson_boundaries(curriculum, guide)
    source = adapter.prepare_lesson(index, 1, guide)
    pages = locator.extractor.extract_pages(guide)
    metadata = adapter.extract_lesson_metadata(pages)

    assert adapter.attribution == CKLA_ATTRIBUTION
    assert adapter.terminology.teacher_guide == "Teacher Guide"
    assert adapter.terminology.student_reader == "Student Reader"
    assert adapter.terminology.activity_book == "Activity Book"
    assert adapter.validate_required_resources(
        curriculum,
        service.library.resolve_path,
    ) == []
    assert index.lessons[0].lesson_title == 'Close Reading: "First Story"'
    assert metadata.standards == ["RL.8.1"]
    assert "Lesson one exact text" in source.extracted_text


def test_ckla_adapter_reports_missing_required_teacher_guide(tmp_path) -> None:
    service, _ = prepared_fixture(tmp_path / "registered")
    curriculum = service.library.get_unit("CKLA", 8, 1)
    curriculum.teacher_guide_path = "missing-guide.pdf"

    errors = CKLAAdapter(
        index_directory=tmp_path / "indexes"
    ).validate_required_resources(
        curriculum,
        service.library.resolve_path,
    )

    assert len(errors) == 1
    assert errors[0].startswith("Teacher Guide PDF not found:")


def test_teacheros_legacy_locator_is_wrapped_for_backwards_compatibility(
    tmp_path,
) -> None:
    service, _ = prepared_fixture(tmp_path)

    adapter = service.curriculum_adapter("CKLA")

    assert isinstance(adapter, CKLAAdapter)
    assert adapter.locator is service.locator


def test_adapter_preparation_preserves_existing_pipeline_input(tmp_path) -> None:
    legacy_service, _ = prepared_fixture(tmp_path)
    legacy_service.output_directory = tmp_path / "legacy-output"
    expected = legacy_service.prepare_lesson(
        grade=8,
        unit=1,
        lesson_number=1,
    )
    expected_payload = json.loads(
        open(expected.output_files[0], encoding="utf-8").read()
    )

    adapter_service = TeacherOS(
        project_root=tmp_path,
        library=legacy_service.library,
        curriculum_adapter=CKLAAdapter(locator=legacy_service.locator),
        output_directory=tmp_path / "adapter-output",
    )
    actual = adapter_service.prepare_lesson(
        grade=8,
        unit=1,
        lesson_number=1,
    )
    actual_payload = json.loads(
        open(actual.output_files[0], encoding="utf-8").read()
    )

    assert actual.status == expected.status
    assert actual.lesson_metadata == expected.lesson_metadata
    assert actual.lesson_source == expected.lesson_source
    assert actual_payload == expected_payload


def test_curriculum_cli_uses_registered_ckla_adapter(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    _, index_path = prepared_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = curriculum_main(
        [
            "--database",
            "library.sqlite3",
            "list-lessons",
            "--grade",
            "8",
            "--unit",
            "1",
            "--index-file",
            str(index_path),
        ]
    )

    assert result == 0
    assert "Lesson 1" in capsys.readouterr().out


def test_lesson_generation_regression_runs_through_ckla_adapter(
    tmp_path,
) -> None:
    prepared_service, _ = prepared_fixture(tmp_path)
    service = TeacherOS(
        project_root=tmp_path,
        library=prepared_service.library,
        curriculum_adapter=CKLAAdapter(locator=prepared_service.locator),
        output_directory=tmp_path / "pipeline-inputs",
        generation_output_directory=tmp_path / "runs",
        openai_client=PipelineClient(),
    )

    result = service.generate_lesson(
        grade=8,
        unit=1,
        lesson_number=1,
    )

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.validation_result in {"pass", "pass_with_warnings"}
    assert result.slide_count == 1
    run = tmp_path / "runs" / result.request_id
    assert (run / "RendererPromptBundle.json").is_file()
    assert (run / "RendererPromptBundle.md").is_file()
    assert (run / "GammaDeckPrompt.md").is_file()
    assert (run / "07_validated_lesson.json").is_file()
