"""Tests for exact, adapter-backed Student Reader page retrieval."""

from __future__ import annotations

import json

from app.teacheros import LessonPipelineInput, TeacherOS
from curriculum.adapters import CKLAAdapter
from curriculum.student_reader_locator import StudentReaderLocator
from schemas.curriculum_schema import CurriculumUnit, LessonIndexEntry, PdfPage
from schemas.student_reader_source_schema import StudentReaderSource
from schemas.teacher_companion_schema import TeacherCompanionGuide
from Tests.test_generation_pipeline import PipelineClient
from Tests.test_teacher_companion import guide, pipeline_input, teacheros
from Tests.test_teacheros import make_pdf, prepared_fixture


class PageExtractor:
    def __init__(self, pages: list[PdfPage]) -> None:
        self.pages = pages

    def extract_pages(self, path) -> list[PdfPage]:
        return self.pages


def page(
    pdf_page_number: int,
    label: str | None,
    text: str,
) -> PdfPage:
    full_text = f"{text}\n{label}" if label else text
    return PdfPage(
        pdf_page_number=pdf_page_number,
        display_page_number=pdf_page_number + 1,
        printed_page_number=int(label) if label and label.isdigit() else None,
        raw_text=full_text,
        normalized_text=full_text,
        character_count=len(full_text),
    )


def curriculum(reader_path: str = "reader.pdf") -> CurriculumUnit:
    return CurriculumUnit(
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        teacher_guide_path="guide.pdf",
        student_reader_path=reader_path,
    )


def entry(references: list[str]) -> LessonIndexEntry:
    return LessonIndexEntry(
        lesson_number=1,
        reader_pages=references,
        start_pdf_page=0,
        end_pdf_page=0,
        detected_heading="Lesson 1",
        confidence=1,
        source_file="guide.pdf",
    )


def retrieve(tmp_path, references, pages) -> StudentReaderSource:
    reader = tmp_path / "reader.pdf"
    reader.touch()
    locator = StudentReaderLocator(PageExtractor(pages))
    return locator.retrieve(curriculum(str(reader)), entry(references), reader)


def test_ckla_adapter_resolves_exact_indexed_reader_references(
    tmp_path,
) -> None:
    reader = tmp_path / "reader.pdf"
    reader.touch()
    adapter = CKLAAdapter(
        student_reader_locator=StudentReaderLocator(
            PageExtractor([page(0, "12", "Assigned text")])
        )
    )

    source = adapter.retrieve_student_reader(
        curriculum(str(reader)),
        entry(["12", "12", "13–14"]),
        reader,
    )

    assert source.requested_printed_page_references == ["12", "13–14"]
    assert source.pages[0].printed_page == "12"


def test_printed_pages_map_to_pdf_pages_and_extract_only_assigned_pages(
    tmp_path,
) -> None:
    source = retrieve(
        tmp_path,
        ["12–13"],
        [
            page(0, "11", "Unassigned text"),
            page(1, "12", "Assigned page twelve"),
            page(2, "13", "Assigned page thirteen"),
            page(3, "14", "Other unassigned text"),
        ],
    )

    assert source.extraction_status == "completed"
    assert source.matched_pdf_page_numbers == [1, 2]
    assert [item.display_pdf_page_number for item in source.pages] == [2, 3]
    assert [item.printed_page for item in source.pages] == ["12", "13"]
    assert [item.extracted_text for item in source.pages] == [
        "Assigned page twelve\n12",
        "Assigned page thirteen\n13",
    ]
    assert all(
        "Unassigned text" not in item.extracted_text
        for item in source.pages
    )


def test_consistent_front_matter_offset_maps_an_unlabeled_page(
    tmp_path,
) -> None:
    source = retrieve(
        tmp_path,
        ["1–3"],
        [
            page(0, None, "Front matter"),
            page(1, None, "More front matter"),
            page(2, "1", "Reader page one"),
            page(3, "2", "Reader page two"),
            page(4, None, "Reader page three"),
        ],
    )

    assert source.extraction_status == "completed"
    assert source.matched_pdf_page_numbers == [2, 3, 4]
    assert any(
        "consistent printed-page offset" in warning
        for warning in source.pages[-1].warnings
    )


def test_missing_reader_file_is_structured_and_non_throwing(tmp_path) -> None:
    missing = tmp_path / "missing.pdf"

    source = StudentReaderLocator().retrieve(
        curriculum(str(missing)),
        entry(["12–13"]),
        missing,
    )

    assert source.source_available is False
    assert source.extraction_status == "unavailable"
    assert source.pages == []
    assert "unavailable" in source.warnings[0]


def test_missing_lesson_reader_references_fails_clearly(tmp_path) -> None:
    source = retrieve(tmp_path, [], [page(0, "1", "Reader page one")])

    assert source.source_available is True
    assert source.extraction_status == "failed"
    assert "no usable Student Reader page references" in source.warnings[0]


def test_ambiguous_printed_page_mapping_is_not_guessed(tmp_path) -> None:
    source = retrieve(
        tmp_path,
        ["12"],
        [
            page(0, "12", "First candidate"),
            page(1, "12", "Second candidate"),
        ],
    )

    assert source.extraction_status == "failed"
    assert source.pages == []
    assert "ambiguous" in source.warnings[0]
    assert "PDF pages 1, 2" in source.warnings[0]


def test_teacheros_saves_a_structured_student_reader_artifact(
    tmp_path,
) -> None:
    service, _ = prepared_fixture(tmp_path)
    reader = tmp_path / "reader.pdf"
    reader.unlink()
    make_pdf(
        reader,
        [
            f"Assigned Reader page {number}\n{number}"
            for number in range(12, 19)
        ],
    )

    source = service.retrieve_student_reader_source(
        grade=8,
        unit=1,
        lesson_number=1,
    )

    artifact = (
        tmp_path
        / "outputs"
        / "ckla_grade_8_unit_1_lesson_1_student_reader_source.json"
    )
    saved = StudentReaderSource.model_validate_json(
        artifact.read_text(encoding="utf-8")
    )
    assert source.extraction_status == "completed"
    assert saved == source
    assert saved.requested_printed_page_references == ["12-18"]
    assert len(saved.pages) == 7


def test_existing_pipeline_inputs_remain_valid_and_serialization_unchanged(
    tmp_path,
) -> None:
    service, _ = prepared_fixture(tmp_path)
    result = service.prepare_lesson(grade=8, unit=1, lesson_number=1)
    serialized = open(result.output_files[0], encoding="utf-8").read()
    payload = json.loads(serialized)

    assert "student_reader_source" not in payload
    assert LessonPipelineInput.model_validate(payload)
    assert LessonPipelineInput.model_validate_json(serialized)


def test_lesson_generation_outputs_do_not_consume_reader_source(
    tmp_path,
) -> None:
    service, _ = prepared_fixture(tmp_path)
    service.openai_client = PipelineClient()
    before = service.prepare_lesson(grade=8, unit=1, lesson_number=1)
    before_json = open(before.output_files[0], encoding="utf-8").read()
    service.retrieve_student_reader_source(
        grade=8,
        unit=1,
        lesson_number=1,
    )

    result = service.generate_lesson(grade=8, unit=1, lesson_number=1)

    assert result.status in {"completed", "completed_with_warnings"}
    assert open(before.output_files[0], encoding="utf-8").read() == before_json
    assert "gamma_handoff_prompt_generator" in result.completed_stages


def test_teacher_companion_behavior_remains_reader_independent(
    tmp_path,
) -> None:
    prepared = pipeline_input()
    service, _ = teacheros(tmp_path, guide(prepared))

    result = service.generate_teacher_companion(prepared)

    assert result.status == "completed"
    assert result.validation_result == "pass"
    generated = service._read_model(
        tmp_path
        / "runs"
        / prepared.request.request_id
        / "teacher_companion.json",
        TeacherCompanionGuide,
    )
    assert generated.source_basis.student_reader_text_available is False
