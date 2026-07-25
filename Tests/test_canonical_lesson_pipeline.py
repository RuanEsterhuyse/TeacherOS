"""End-to-end tests for canonical lesson artifact generation."""

import json

from app.teacheros import TeacherOS
from schemas.canonical_lesson_schema import CanonicalLesson
from Tests.test_generation_pipeline import PipelineClient
from Tests.test_teacheros import prepared_fixture


def test_generation_adds_canonical_artifacts_without_removing_legacy_files(
    tmp_path,
) -> None:
    prepared, _ = prepared_fixture(tmp_path)
    service = TeacherOS(
        project_root=tmp_path,
        library=prepared.library,
        curriculum_adapter=prepared.curriculum_adapter("CKLA"),
        output_directory=tmp_path / "inputs",
        generation_output_directory=tmp_path / "runs",
        openai_client=PipelineClient(),
    )

    result = service.generate_lesson(grade=8, unit=1, lesson_number=1)

    assert result.status in {"completed", "completed_with_warnings"}
    run = tmp_path / "runs" / result.request_id
    required = {
        "lesson.json",
        "teacher_companion.md",
        "teacher_companion.pdf",
        "slides.json",
        "speaker_notes.json",
        "lesson_metadata.json",
    }
    assert required <= {path.name for path in run.iterdir()}
    assert (run / "04_presentation_design.json").is_file()
    assert (run / "07_validated_lesson.json").is_file()
    assert (run / "RendererPromptBundle.json").is_file()
    assert (run / "GammaDeckPrompt.md").is_file()
    assert {
        "canonical_lesson_builder",
        "canonical_lesson_validator",
        "canonical_lesson_renderers",
    } <= set(result.completed_stages)

    lesson = CanonicalLesson.model_validate_json(
        (run / "lesson.json").read_text(encoding="utf-8")
    )
    assert lesson.agenda.selected_duration_minutes == 10
    assert lesson.lesson_information.duration_minutes == 10
    assert lesson.lesson_information.curriculum == "CKLA"
    assert lesson.lesson_blocks[0].slide_mappings[0].slide_id == "S01"
    assert (
        lesson.instructional_resources[1].availability.value
        == "unavailable"
    )


def test_canonical_artifacts_are_deterministic_and_resumable(tmp_path) -> None:
    service, _ = prepared_fixture(tmp_path)
    service.generation_output_directory = tmp_path / "runs"
    client = PipelineClient()
    service.openai_client = client
    first = service.generate_lesson(grade=8, unit=1, lesson_number=1)
    path = tmp_path / "runs" / first.request_id / "lesson.json"
    first_json = path.read_text(encoding="utf-8")
    client.calls.clear()

    second = service.generate_lesson(grade=8, unit=1, lesson_number=1)

    assert second.status in {"completed", "completed_with_warnings"}
    assert client.calls == []
    assert path.read_text(encoding="utf-8") == first_json
    slides = json.loads(
        (path.parent / "slides.json").read_text(encoding="utf-8")
    )
    assert slides["source_digest"] == json.loads(first_json)["source_digest"]
