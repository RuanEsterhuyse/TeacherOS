"""Phase 3B pasted lesson intake, analysis, and persistence tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.teacheros import LessonPipelineInput
from curriculum.intelligence.pasted_lesson_analyzer import (
    analyze_pasted_lesson,
)
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
    create_pasted_lesson_source,
)
from schemas.canonical_lesson_schema import CanonicalLesson
from schemas.pasted_lesson_schema import (
    PastedLessonSource,
    PlaybookAnalysisResult,
    TeacherPlaybook,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "pasted_lesson_ckla_g8_u1_l1_sanitized.txt"
)


def _source(**updates) -> PastedLessonSource:
    values = {
        "grade": "8",
        "unit": "1",
        "lesson_number": 1,
        "lesson_title": "Identity and Evidence",
        "teacher_guide_page_start": 12,
        "teacher_guide_page_end": 18,
        "teacher_guide_text": FIXTURE.read_text(encoding="utf-8"),
        "student_reader_text": "Synthetic reader excerpt.\nKeep spacing.",
        "activity_book_text": "Activity Page 1.2: Evidence chart.",
        "source_notes": "Teacher-provided test fixture.",
    }
    values.update(updates)
    return create_pasted_lesson_source(**values)


def test_source_model_round_trip_preserves_exact_pasted_text():
    exact = "  First line.\r\nSecond  line.\n\n“Exact quotation.”  "
    source = _source(teacher_guide_text=exact)

    restored = PastedLessonSource.model_validate_json(
        source.model_dump_json()
    )

    assert restored == source
    assert restored.teacher_guide_text == exact
    assert restored.student_reader_text == (
        "Synthetic reader excerpt.\nKeep spacing."
    )


def test_source_optional_fields_and_page_validation():
    source = create_pasted_lesson_source(
        grade="8",
        unit="1",
        lesson_number=2,
        lesson_title="Optional Sources",
        teacher_guide_text="Objectives:\n- Read closely.",
    )

    assert source.student_reader_text is None
    assert source.activity_book_text is None
    assert source.teacher_guide_page_start is None
    with pytest.raises(ValidationError, match="supplied together"):
        source.model_copy(
            update={"teacher_guide_page_start": 4}
        ).model_dump()
        PastedLessonSource.model_validate({
            **source.model_dump(),
            "teacher_guide_page_start": 4,
        })
    with pytest.raises(ValidationError, match="cannot precede"):
        PastedLessonSource.model_validate({
            **source.model_dump(),
            "teacher_guide_page_start": 8,
            "teacher_guide_page_end": 4,
        })


def test_repository_save_load_list_and_source_association(tmp_path):
    repository = PastedLessonRepository(tmp_path / "runtime")
    source = repository.save_source(_source())
    analysis = analyze_pasted_lesson(source)
    repository.save_playbook(analysis.playbook)

    assert repository.load_source(source.source_id) == source
    assert repository.list_sources() == [source]
    assert repository.load_playbook(
        analysis.playbook.playbook_id
    ) == analysis.playbook
    assert repository.list_playbooks() == [analysis.playbook]
    assert analysis.playbook.source_id == source.source_id

    orphan = analysis.playbook.model_copy(
        update={"source_id": "missing-source"}
    )
    with pytest.raises(FileNotFoundError):
        repository.save_playbook(orphan)


def test_stable_source_and_playbook_ids_are_deterministic():
    first = _source()
    second = _source()
    assert first.source_id == second.source_id
    assert analyze_pasted_lesson(first) == analyze_pasted_lesson(first)
    assert (
        analyze_pasted_lesson(first).playbook.playbook_id
        == analyze_pasted_lesson(second).playbook.playbook_id
    )
    changed = _source(teacher_guide_text=first.teacher_guide_text + "\nChange")
    assert changed.source_id != first.source_id


def test_baseline_analysis_extracts_days_activities_timing_and_sections():
    result = analyze_pasted_lesson(_source())
    playbook = result.playbook

    assert playbook.instructional_days == [1, 2]
    assert [value.title for value in playbook.activities] == [
        "Launch the Identity Question",
        "Read and Notice",
        "Evidence Discussion",
        "Independent Response",
    ]
    assert [value.duration_minutes for value in playbook.activities] == [
        8,
        22,
        15,
        20,
    ]
    assert [value.instructional_day for value in playbook.activities] == [
        1,
        1,
        2,
        2,
    ]
    assert len(playbook.objectives) == 2
    assert len(playbook.success_criteria) == 2
    assert playbook.materials == [
        "short fictional excerpt",
        "identity chart",
        "discussion notebook",
    ]
    assert [value.term for value in playbook.vocabulary] == [
        "identity",
        "perspective",
        "inference",
    ]
    assert playbook.essential_question.startswith("How can identity")
    assert playbook.homework == [
        "Revise one explanation sentence for precision."
    ]
    assert playbook.assessment == [
        (
            "Collect the independent response and check claim, evidence, "
            "and reasoning."
        )
    ]


def test_analysis_extracts_references_and_optional_source_inputs():
    source = _source()
    result = analyze_pasted_lesson(source)
    references = result.playbook.source_references

    assert source.student_reader_text == (
        "Synthetic reader excerpt.\nKeep spacing."
    )
    assert source.activity_book_text == (
        "Activity Page 1.2: Evidence chart."
    )
    assert any(
        value.source_type == "teacher_guide"
        and value.page_start == 12
        and value.page_end == 18
        for value in references
    )
    assert any(
        value.source_type == "student_reader"
        and value.page_start == 3
        and value.page_end == 6
        for value in references
    )
    assert any(
        value.source_type == "activity_book"
        and value.activity_reference == "Activity Page 1.2"
        for value in references
    )


def test_unclassified_text_is_preserved_and_missing_fields_warn():
    result = analyze_pasted_lesson(_source())
    assert result.unclassified_sections == [
        "Unclassified Facilitation Note",
        "Keep the synthetic excerpt available for students who need to reread.",
    ]
    assert any(
        warning.code == "unclassified_source_text"
        for warning in result.warnings
    )

    sparse = create_pasted_lesson_source(
        grade="8",
        unit="1",
        lesson_number=3,
        lesson_title="Sparse Lesson",
        teacher_guide_text="A source paragraph with no labeled sections.",
    )
    sparse_result = analyze_pasted_lesson(sparse)
    codes = {value.code for value in sparse_result.warnings}
    assert {
        "instructional_days_not_found",
        "activities_not_found",
        "objectives_not_found",
        "materials_not_found",
        "vocabulary_not_found",
        "essential_question_not_found",
        "success_criteria_not_found",
        "unclassified_source_text",
    } <= codes
    assert sparse_result.unclassified_sections == [
        "A source paragraph with no labeled sections."
    ]


def test_playbook_analysis_serialization_is_strict():
    result = analyze_pasted_lesson(_source())
    restored = PlaybookAnalysisResult.model_validate_json(
        result.model_dump_json()
    )
    assert restored == result
    assert TeacherPlaybook.model_validate(
        restored.playbook.model_dump()
    ) == restored.playbook
    with pytest.raises(ValidationError):
        TeacherPlaybook.model_validate({
            **restored.playbook.model_dump(),
            "unknown_field": True,
        })


def test_repository_reports_malformed_and_unsafe_artifacts(tmp_path):
    repository = PastedLessonRepository(tmp_path / "runtime")
    malformed = repository.sources_directory / "broken.json"
    malformed.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed"):
        repository.load_source("broken")
    with pytest.raises(ValueError, match="Invalid artifact identifier"):
        repository.load_source("../token")


def test_phase3b_contracts_remain_parallel_to_existing_pipeline():
    assert "pasted_lesson_source" not in CanonicalLesson.model_fields
    assert (
        "pasted_lesson_source"
        not in PreparedCurriculumSourceBundle.model_fields
    )
    assert "pasted_lesson_source" not in LessonPipelineInput.model_fields
    assert "prepared_source_bundle_reference" in (
        LessonPipelineInput.model_fields
    )


def test_saved_json_is_human_inspectable(tmp_path):
    repository = PastedLessonRepository(tmp_path / "runtime")
    source = repository.save_source(_source())
    result = analyze_pasted_lesson(source)
    repository.save_playbook(result.playbook)

    source_payload = json.loads(
        (repository.sources_directory / f"{source.source_id}.json")
        .read_text(encoding="utf-8")
    )
    playbook_payload = json.loads(
        (
            repository.playbooks_directory
            / f"{result.playbook.playbook_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert source_payload["teacher_guide_text"] == source.teacher_guide_text
    assert playbook_payload["source_id"] == source.source_id
