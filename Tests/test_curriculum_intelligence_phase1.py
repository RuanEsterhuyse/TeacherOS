"""Offline tests for the Phase 1 Curriculum Source Manifest."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import fitz
from pydantic import BaseModel

import schemas.curriculum_intelligence_schema as intelligence_schema
from curriculum.intelligence.extractor import ResourceExtractor
from curriculum.intelligence.ids import file_checksum, stable_id
from curriculum.intelligence.mappings import coordinate_mapping_id
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
from curriculum.intelligence.service import CurriculumIntelligenceService
from schemas.curriculum_intelligence_schema import (
    MappingMethod,
    MappingReviewStatus,
    ResourceAssignment,
    SourceCoordinateMapping,
)
from schemas.curriculum_schema import (
    CurriculumIndex,
    CurriculumUnit,
    LessonIndexEntry,
)


def make_pdf(path: Path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_textbox(
                fitz.Rect(40, 40, 560, 760), text, fontsize=10
            )
    document.save(path)
    document.close()


def source_fixture(tmp_path: Path) -> dict[str, Path]:
    guide = tmp_path / "guide.pdf"
    book = tmp_path / "book.pdf"
    activities = tmp_path / "activities.pdf"
    online = tmp_path / "online.pdf"
    terms = tmp_path / "terms.pdf"
    index_path = tmp_path / "index.json"
    make_pdf(
        guide,
        [
            "LESSON 1\nRead-Aloud: The Attack\nLesson requirements\n28",
            "Lesson 1 continuation\nHomework: Read Guera pages 51-57\n29",
        ],
    )
    make_pdf(
        book,
        [
            "INTRODUCTION\nAuthor introduction text",
            "THE ATTACK\nThe complete first story source text",
            "SELFIE\nNext story",
            "GÜERA\nThe complete homework story source text",
            "BURRITO MAN\nFollowing story",
            "TRANSLATIONS OF THE REFRANES\nThe Attack\nAt night all cats are black.",
            "NOTES ON THE STORIES\nThe Attack\nSource note.",
            "ABOUT THE AUTHOR\nAuthor biography",
        ],
    )
    make_pdf(
        activities,
        [
            "NAME TAKE-HOME 1.1\nLetter to Family",
            "NAME 1.2\nVocabulary for The Attack",
            "NAME TAKE-HOME 1.3\nGuided Questions for Guera",
            "NAME 1.3 continued\nQuestion 6",
            "NAME RESOURCES SR.1\nGlossary",
            "NAME RESOURCES SR.1 continued\nGlossary continued",
        ],
    )
    make_pdf(
        online,
        [
            "Online Resources\nLesson 1\nMaps of North and South America\n"
            "Resources for Teachers: Teaching Identity"
        ],
    )
    make_pdf(terms, ["Curriculum Series\nTerms of Use"])
    unit = CurriculumUnit(
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        unit_title="Us, in Progress",
        teacher_guide_path=str(guide),
        student_reader_path=str(book),
        activity_book_path=str(activities),
    )
    index = CurriculumIndex(
        curriculum=unit,
        total_pdf_pages=2,
        lessons=[
            LessonIndexEntry(
                lesson_number=1,
                lesson_title="Read-Aloud: “The Attack”",
                lesson_objective=["Analyze theme."],
                standards=["RL.8.2"],
                materials=["Book", "Activity Pages"],
                homework=["Read Güera."],
                reader_pages=[
                    "viii–xi",
                    "1–15",
                    "51–57",
                    "228–230",
                    "231",
                ],
                activity_book_pages=["1.1", "1.2", "1.3", "SR.1"],
                start_pdf_page=0,
                end_pdf_page=1,
                start_printed_page=28,
                end_printed_page=29,
                detected_heading="Lesson 1",
                confidence=1,
                source_file=str(guide),
            )
        ],
    )
    index_path.write_text(index.model_dump_json(indent=2), encoding="utf-8")
    return {
        "index_path": index_path,
        "teacher_guide_path": guide,
        "instructional_text_path": book,
        "activity_resource_path": activities,
        "online_resources_path": online,
        "terms_of_use_path": terms,
    }


def build(tmp_path: Path):
    paths = source_fixture(tmp_path)
    service = CurriculumIntelligenceService(
        database_path=tmp_path / "library.sqlite3",
        output_directory=tmp_path / "output",
    )
    return service, service.build_lesson_one(**paths), paths


def test_generic_schema_has_no_publisher_specific_field_names() -> None:
    models = [
        value
        for value in vars(intelligence_schema).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == intelligence_schema.__name__
    ]
    for model in models:
        assert all(
            "ckla" not in field.casefold() for field in model.model_fields
        )


def test_stable_ids_and_checksum_versions_are_deterministic(tmp_path) -> None:
    path = tmp_path / "source.pdf"
    make_pdf(path, ["Source page"])

    first, _ = ResourceExtractor().extract(
        curriculum_id="curriculum-1",
        resource_type="instructional_text",
        title="A Text",
        source_path=path,
    )
    second, _ = ResourceExtractor().extract(
        curriculum_id="curriculum-1",
        resource_type="instructional_text",
        title="A Text",
        source_path=path,
    )

    assert first.id == second.id
    assert first.checksum == second.checksum == file_checksum(path)
    assert first.resource_version == first.checksum[:16]
    assert stable_id("resource", "a", "b") == stable_id(
        "resource", "a", "b"
    )


def test_page_extraction_preserves_distinct_coordinates(tmp_path) -> None:
    path = tmp_path / "pages.pdf"
    make_pdf(path, ["TITLE\nBody\n12", "Second page\n13"])

    _, pages = ResourceExtractor().extract(
        curriculum_id="curriculum-1",
        resource_type="teacher_guide",
        title="Guide",
        source_path=path,
    )

    assert pages[0].pdf_page_number == 0
    assert pages[0].display_page_number == 1
    assert pages[0].printed_page_label == "12"
    assert pages[0].normalized_text
    assert pages[0].raw_text
    assert pages[0].text_blocks
    assert pages[0].extraction_method == "pymupdf_text"


def test_offline_lesson_one_manifest_resolves_source_sections(tmp_path) -> None:
    _, result, _ = build(tmp_path)
    assignments = json.loads(
        (result.output_directory / "lesson_1_assignments.json").read_text(
            encoding="utf-8"
        )
    )
    by_title = {item["title"]: item for item in assignments}

    assert result.lesson.title == "Read-Aloud: “The Attack”"
    assert by_title["Teacher Guide Lesson 1 range"][
        "pdf_page_numbers"
    ] == [0, 1]
    assert by_title["Teacher Guide Lesson 1 range"][
        "printed_page_references"
    ] == ["28–29"]
    for title, label in (
        ("Activity Resource 1.1", "1.1"),
        ("Activity Resource 1.2", "1.2"),
        ("Activity Resource 1.3", "1.3"),
        ("Student Resource SR.1", "SR.1"),
    ):
        assert by_title[title]["resolution_status"] == "resolved"
        assert by_title[title]["document_labels"] == [label]
        assert by_title[title]["segment_ids"]
    assert by_title["The Attack"]["resolution_status"] == "partial"
    assert by_title["The Attack"]["pdf_page_numbers"] == [1]
    assert by_title["The Attack"][
        "story_relative_page_references"
    ] == ["1–15"]
    assert by_title["Güera homework reading"]["resolution_status"] == "partial"
    assert by_title["Güera homework reading"]["pdf_page_numbers"] == [3]
    assert by_title["Lesson 1 Online Resources"][
        "resolution_status"
    ] == "resolved"


def test_unmapped_story_page_coordinates_are_never_guessed(tmp_path) -> None:
    _, result, _ = build(tmp_path)
    assignments = [
        ResourceAssignment.model_validate(value)
        for value in json.loads(
            (
                result.output_directory / "lesson_1_assignments.json"
            ).read_text(encoding="utf-8")
        )
    ]
    attack = next(item for item in assignments if item.title == "The Attack")

    assert attack.resolution_status == "partial"
    assert attack.story_relative_page_references == ["1–15"]
    assert attack.printed_page_references == []
    assert attack.pdf_page_numbers == [1]
    assert any("cannot be mapped" in value for value in attack.warnings)


def test_every_resolved_assignment_has_valid_provenance(tmp_path) -> None:
    _, result, _ = build(tmp_path)
    assignments = [
        ResourceAssignment.model_validate(value)
        for value in json.loads(
            (
                result.output_directory / "lesson_1_assignments.json"
            ).read_text(encoding="utf-8")
        )
    ]
    for assignment in assignments:
        if assignment.resolution_status == "resolved":
            assert assignment.segment_ids
            assert assignment.source_provenance
            assert all(
                value.resource_checksum and value.resource_version
                for value in assignment.source_provenance
            )


def test_readiness_is_partial_until_required_mappings_resolve(
    tmp_path,
) -> None:
    _, result, _ = build(tmp_path)

    assert result.readiness.state == "partially_ready"
    assert result.readiness.blockers
    assert any(
        "The Attack is partial" in finding.message
        for finding in result.readiness.blockers
    )
    assert "source_ready" not in {
        value.value for value in result.readiness.achieved_states
    }


def test_lesson_one_is_source_ready_after_five_verified_mappings(
    tmp_path,
) -> None:
    service, baseline, paths = build(tmp_path)
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
    partial = [
        value
        for value in assignments
        if value.required_status == "required"
        and value.resolution_status == "partial"
    ]
    mappings = []
    for assignment in partial:
        resource = resources[assignment.resource_id]
        pdf_pages = [
            value.pdf_page_number
            for value in assignment.source_provenance
            if value.pdf_page_number is not None
        ]
        reference_system = (
            "story_relative_page"
            if assignment.story_relative_page_references
            else "printed_page"
        )
        reference_value = (
            assignment.story_relative_page_references
            or assignment.printed_page_references
        )[0]
        mappings.append(SourceCoordinateMapping(
            id=coordinate_mapping_id(
                assignment.id,
                reference_system,
                reference_value,
                "pdf_page_range",
            ),
            lesson_id=assignment.lesson_id,
            assignment_id=assignment.id,
            resource_id=assignment.resource_id,
            source_version=resource["resource_version"],
            resource_checksum=resource["checksum"],
            extraction_version=resource["extraction_version"],
            reference_system=reference_system,
            reference_value=reference_value,
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
            reviewer_note="Fixture mapping reviewed for the exact source range.",
            created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            mapping_version="1.0",
            warnings=[
                "Curriculum numbering is absent from this fixture edition."
            ],
        ))
    assert len(mappings) == 5
    mapping_path = tmp_path / "coordinate_mappings.json"
    mapping_path.write_text(
        json.dumps(
            [value.model_dump(mode="json") for value in mappings],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = service.build_lesson_one(
        **paths,
        coordinate_mappings_path=mapping_path,
    )

    assert result.readiness.required_assignment_count == 11
    assert result.readiness.resolved_required_assignment_count == 11
    assert result.readiness.state == "source_ready"
    inspector = (
        result.output_directory / "lesson_1_readiness.md"
    ).read_text(encoding="utf-8")
    assert "## Verified Coordinate Overrides" in inspector


def test_snapshot_rebuild_is_deterministic(tmp_path) -> None:
    service, first, paths = build(tmp_path)
    first_bytes = {
        path.name: path.read_bytes() for path in first.output_files
    }

    second = service.build_lesson_one(**paths)

    assert first.build_manifest.snapshot_digest == (
        second.build_manifest.snapshot_digest
    )
    assert first.build_manifest.build_id == second.build_manifest.build_id
    assert first_bytes == {
        path.name: path.read_bytes() for path in second.output_files
    }


def test_stale_resource_checksum_is_detected_and_rebuilt(tmp_path) -> None:
    service, first, paths = build(tmp_path)
    original_resource_ids = set(first.build_manifest.resource_checksums)
    make_pdf(tmp_path / "replacement.pdf", ["Changed terms"])
    (tmp_path / "replacement.pdf").replace(paths["terms_of_use_path"])

    second = service.build_lesson_one(**paths)

    assert set(second.build_manifest.stale_resource_ids) <= (
        original_resource_ids
    )
    assert len(second.build_manifest.stale_resource_ids) == 1
    assert (
        first.build_manifest.resource_checksums
        != second.build_manifest.resource_checksums
    )


def test_sqlite_tables_and_requested_snapshots_are_created(tmp_path) -> None:
    service, result, _ = build(tmp_path)
    expected = {
        "curriculum_manifest.json",
        "resources.json",
        "resource_pages_summary.json",
        "lesson_1_curriculum_lesson.json",
        "lesson_1_assignments.json",
        "lesson_1_coordinate_mappings.json",
        "lesson_1_text_segments.json",
        "lesson_1_readiness.json",
        "lesson_1_readiness.md",
        "build_manifest.json",
    }
    assert {path.name for path in result.output_files} == expected
    assert service.repository.count("ci_resources") == 5
    assert service.repository.count("ci_lessons") == 1
    with sqlite3.connect(service.repository.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "ci_resource_pages" in tables
    assert "ci_assignments" in tables
    assert "ci_coordinate_mappings" in tables
    assert "ci_text_segments" in tables
    assert "curriculum_units" not in tables


def test_summary_does_not_duplicate_full_page_text(tmp_path) -> None:
    _, result, _ = build(tmp_path)
    summary = json.loads(
        (
            result.output_directory / "resource_pages_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        "raw_text" not in page and "normalized_text" not in page
        for resource in summary
        for page in resource["pages"]
    )
