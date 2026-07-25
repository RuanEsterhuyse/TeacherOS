"""Offline tests for the Phase 2 prepared curriculum source bundle."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.teacheros import LessonPipelineInput
from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.mappings import coordinate_mapping_id
from curriculum.intelligence.service import CurriculumIntelligenceService
from schemas.curriculum_intelligence_schema import (
    MappingMethod,
    MappingReviewStatus,
    ResourceAssignment,
    SourceCoordinateMapping,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)
from Tests.test_curriculum_intelligence_phase1 import source_fixture


def ready_service(tmp_path: Path):
    paths = source_fixture(tmp_path)
    service = CurriculumIntelligenceService(
        database_path=tmp_path / "library.sqlite3",
        output_directory=tmp_path / "intelligence",
    )
    baseline = service.build_lesson_one(**paths)
    assignments = [
        ResourceAssignment.model_validate(value)
        for value in json.loads(
            (
                baseline.output_directory / "lesson_1_assignments.json"
            ).read_text(encoding="utf-8")
        )
    ]
    resources = {
        value["id"]: value
        for value in json.loads(
            (baseline.output_directory / "resources.json").read_text(
                encoding="utf-8"
            )
        )
    }
    mappings = []
    for assignment in assignments:
        if assignment.resolution_status != "partial":
            continue
        resource = resources[assignment.resource_id]
        pdf_pages = [
            value.pdf_page_number
            for value in assignment.source_provenance
            if value.pdf_page_number is not None
        ]
        system = (
            "story_relative_page"
            if assignment.story_relative_page_references
            else "printed_page"
        )
        reference = (
            assignment.story_relative_page_references
            or assignment.printed_page_references
        )[0]
        mappings.append(SourceCoordinateMapping(
            id=coordinate_mapping_id(
                assignment.id, system, reference, "pdf_page_range"
            ),
            lesson_id=assignment.lesson_id,
            assignment_id=assignment.id,
            resource_id=assignment.resource_id,
            source_version=resource["resource_version"],
            resource_checksum=resource["checksum"],
            extraction_version=resource["extraction_version"],
            reference_system=system,
            reference_value=reference,
            target_coordinate_system="pdf_page_range",
            target_pdf_start_page=min(pdf_pages),
            target_pdf_end_page=max(pdf_pages),
            target_display_start_page=min(pdf_pages) + 1,
            target_display_end_page=max(pdf_pages) + 1,
            target_segment_ids=assignment.segment_ids,
            mapping_method=MappingMethod.HUMAN_REVIEWED_OVERRIDE,
            confidence=1,
            review_status=MappingReviewStatus.VERIFIED,
            reviewer_type="human",
            reviewer_note="Fixture source range reviewed.",
            created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            mapping_version="1.0",
            warnings=["Original numbering is absent from this edition."],
        ))
    mapping_path = tmp_path / "mappings.json"
    mapping_path.write_text(
        json.dumps(
            [value.model_dump(mode="json") for value in mappings],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    built = service.build_lesson_one(
        **paths,
        coordinate_mappings_path=mapping_path,
    )
    return service, built, paths


def prepared(tmp_path: Path):
    service, built, paths = ready_service(tmp_path)
    result = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=tmp_path / "prepared_source_bundle.json",
    )
    return service, built, paths, result


def test_bundle_schema_is_curriculum_agnostic() -> None:
    fields = PreparedCurriculumSourceBundle.model_fields
    assert all("ckla" not in value.casefold() for value in fields)
    schema = json.dumps(PreparedCurriculumSourceBundle.model_json_schema())
    assert "CKLA" not in schema


def test_lesson_one_inventory_and_source_distinctions(tmp_path) -> None:
    _, _, _, result = prepared(tmp_path)
    bundle = result.bundle
    required = {value.title: value for value in bundle.required_assignments}

    assert bundle.readiness_state == "source_ready"
    assert len(required) == 11
    assert [value.title for value in bundle.optional_assignments] == [
        "Curriculum terms of use"
    ]
    expected = {
        "Teacher Guide Lesson 1 range",
        "Trade-book introduction",
        "The Attack",
        "Activity Resource 1.1",
        "Activity Resource 1.2",
        "Activity Resource 1.3",
        "Student Resource SR.1",
        "Güera homework reading",
        "Relevant refrane reference",
        "Relevant story notes",
        "Lesson 1 Online Resources",
    }
    assert set(required) == expected
    assert required["The Attack"].assignment_type == "assigned_reading"
    assert required["Güera homework reading"].assignment_type == "homework"
    assert (
        required["The Attack"].text_segment_ids
        != required["Güera homework reading"].text_segment_ids
    )
    assert all(value.available for value in required.values())
    assert all(value.source_segments for value in required.values())


def test_exact_specialized_sources_and_mapping_provenance(tmp_path) -> None:
    _, _, _, result = prepared(tmp_path)
    by_title = {
        value.title: value
        for value in (
            result.bundle.required_assignments
            + result.bundle.optional_assignments
        )
    }
    assert "LESSON 1" in (
        by_title["Teacher Guide Lesson 1 range"]
        .source_segments[0]
        .exact_text
    )
    assert "INTRODUCTION" in (
        by_title["Trade-book introduction"].source_segments[0].exact_text
    )
    assert "TRANSLATIONS OF THE REFRANES" in (
        by_title["Relevant refrane reference"]
        .source_segments[0]
        .exact_text
    )
    assert "NOTES ON THE STORIES" in (
        by_title["Relevant story notes"].source_segments[0].exact_text
    )
    assert "Online Resources" in (
        by_title["Lesson 1 Online Resources"]
        .source_segments[0]
        .exact_text
    )
    for title in (
        "Trade-book introduction",
        "The Attack",
        "Güera homework reading",
        "Relevant refrane reference",
        "Relevant story notes",
    ):
        mapping = by_title[title].coordinate_mapping_provenance
        assert len(mapping) == 1
        assert mapping[0].review_status == "verified"
        assert mapping[0].provenance


def test_bundle_is_deterministic_and_cache_is_safe(tmp_path) -> None:
    service, built, _, first = prepared(tmp_path)
    second = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=first.output_path,
    )

    assert first.bundle.bundle_digest == second.bundle.bundle_digest
    assert second.reused is True
    payload = second.bundle.model_dump(
        mode="json", exclude={"bundle_digest"}
    )
    assert second.bundle.bundle_digest == content_digest(payload)


def test_stale_source_checksum_invalidates_required_assignment(
    tmp_path,
) -> None:
    service, built, paths, first = prepared(tmp_path)
    paths["teacher_guide_path"].write_bytes(
        paths["teacher_guide_path"].read_bytes() + b"changed"
    )
    second = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=first.output_path,
    )

    teacher_guide = next(
        value
        for value in second.bundle.required_assignments
        if value.title == "Teacher Guide Lesson 1 range"
    )
    assert second.reused is False
    assert second.bundle.readiness_state == "partially_ready"
    assert teacher_guide.available is False
    assert teacher_guide.source_segments == []


def test_stale_mapping_invalidates_bundle(tmp_path) -> None:
    service, built, _, first = prepared(tmp_path)
    mappings = service.repository.load_coordinate_mappings(built.lesson.id)
    mappings[0] = mappings[0].model_copy(
        update={"review_status": MappingReviewStatus.STALE}
    )
    service.repository.replace_coordinate_mappings(
        built.lesson.id, mappings
    )
    second = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=first.output_path,
    )

    assert second.bundle.readiness_state == "partially_ready"
    assert any(
        "coordinate mappings" in warning.casefold()
        for assignment in second.bundle.required_assignments
        for warning in assignment.warnings
    )


def test_mapping_version_change_invalidates_cached_digest(tmp_path) -> None:
    service, built, _, first = prepared(tmp_path)
    mappings = service.repository.load_coordinate_mappings(built.lesson.id)
    mappings[0] = mappings[0].model_copy(
        update={"mapping_version": "2.0"}
    )
    service.repository.replace_coordinate_mappings(
        built.lesson.id, mappings
    )
    second = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=first.output_path,
    )

    assert second.reused is False
    assert second.bundle.readiness_state == "source_ready"
    assert second.bundle.bundle_digest != first.bundle.bundle_digest


def test_missing_required_segment_is_never_available(tmp_path) -> None:
    service, built, _, first = prepared(tmp_path)
    assignment = service.repository.load_assignments(built.lesson.id)[0]
    with sqlite3.connect(service.repository.database_path) as connection:
        connection.execute(
            "DELETE FROM ci_text_segments WHERE id=?",
            (assignment.segment_ids[0],),
        )
    second = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=first.output_path,
    )
    affected = next(
        value
        for value in second.bundle.required_assignments
        if value.assignment_id == assignment.id
    )

    assert affected.available is False
    assert affected.source_segments == []
    assert second.bundle.readiness_state == "partially_ready"


def test_missing_optional_resource_is_only_a_warning(tmp_path) -> None:
    service, built, paths, first = prepared(tmp_path)
    paths["terms_of_use_path"].unlink()
    second = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=first.output_path,
    )

    assert second.bundle.readiness_state == "source_ready"
    assert second.bundle.optional_assignments[0].available is False
    assert any(
        value.code == "optional_assignment_unavailable"
        for value in second.bundle.warnings
    )


def test_old_pipeline_input_remains_compatible_and_unchanged() -> None:
    payload = {
        "request": {
            "request_id": "generic-grade-8-unit-1-lesson-1",
            "curriculum_name": "Generic",
            "grade": "8",
            "unit": "1",
            "lesson_number": 1,
        },
        "lesson_title": "Lesson 1",
        "teacher_guide_lesson_text": "Exact teacher guide text.",
        "objectives": [],
        "standards": [],
        "materials": [],
        "homework": [],
        "duration": 45,
        "reader_page_references": [],
        "activity_book_references": [],
        "assessment_references": [],
        "pdf_page_references": [],
        "source_references": [],
        "extraction_warnings": [],
    }
    prepared_input = LessonPipelineInput.model_validate(payload)

    assert prepared_input.model_dump(mode="json") == payload
    assert "prepared_source_bundle_reference" not in (
        prepared_input.model_dump(mode="json")
    )


def test_offline_bundle_construction_does_not_call_ai(
    tmp_path,
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("AI client must not be constructed")

    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__",
        forbidden,
    )
    _, _, _, result = prepared(tmp_path)

    assert result.bundle.readiness_state == "source_ready"
