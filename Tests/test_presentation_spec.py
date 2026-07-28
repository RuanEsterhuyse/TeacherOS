"""Phase 3D provider-neutral presentation specification tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.interface_server import TeacherOSInterface
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
)
from curriculum.intelligence.presentation_spec import (
    DEFAULT_THEME,
    build_presentation_spec,
)
from curriculum.intelligence.presentation_spec_validator import (
    validate_presentation_spec,
)
from schemas.pasted_lesson_schema import PastedLessonSource
from schemas.playbook_enrichment_schema import (
    ApprovedPlaybookEnrichment,
    TeacherApprovalStatus,
)
from schemas.presentation_spec_schema import (
    ApprovalStatus,
    ContentElement,
    ContentElementType,
    GroundingLabel,
    PresentationBuildOptions,
    PresentationSpec,
    SlideType,
    ValidationStatus,
    VisualSpec,
    VisualType,
)
from Tests.test_teacheros import prepared_fixture


FIXTURES = Path(__file__).parent / "fixtures"
APPROVED_FIXTURE = (
    FIXTURES / "approved_playbook_enrichment_synthetic.json"
)
EXPECTED_FIXTURE = (
    FIXTURES / "presentation_spec_synthetic_expected.json"
)


def _approved() -> ApprovedPlaybookEnrichment:
    return ApprovedPlaybookEnrichment.model_validate_json(
        APPROVED_FIXTURE.read_text(encoding="utf-8")
    )


def _source_for(approved: ApprovedPlaybookEnrichment) -> PastedLessonSource:
    metadata = approved.enriched_playbook.lesson_metadata
    return PastedLessonSource(
        source_id=approved.source_id,
        grade=metadata.grade,
        unit=metadata.unit,
        lesson_number=metadata.lesson_number,
        lesson_title=metadata.lesson_title,
        teacher_guide_page_start=metadata.teacher_guide_page_start,
        teacher_guide_page_end=metadata.teacher_guide_page_end,
        teacher_guide_text="Synthetic teacher guide source.",
        student_reader_text="Synthetic reader source.",
        activity_book_text="Synthetic activity source.",
        created_at=approved.generated_at,
        updated_at=approved.generated_at,
    )


def _renumber(spec: PresentationSpec) -> PresentationSpec:
    slides = [
        slide.model_copy(update={"slide_number": index})
        for index, slide in enumerate(spec.slides, 1)
    ]
    return spec.model_copy(update={"slides": slides})


def test_schema_serialization_optional_content_theme_and_visual_models():
    result = build_presentation_spec(_approved())
    restored = PresentationSpec.model_validate_json(
        result.presentation_spec.model_dump_json()
    )

    assert restored == result.presentation_spec
    assert restored.theme == DEFAULT_THEME
    assert restored.slides[0].subtitle is None
    assert VisualSpec(visual_type=VisualType.text_only).image_prompt is None
    element = ContentElement(
        element_id="optional-element",
        element_type=ContentElementType.table,
        order=1,
        table_rows=[["A", "B"]],
    )
    assert element.text is None
    with pytest.raises(ValidationError, match="cannot be empty"):
        ContentElement(
            element_id="empty",
            element_type=ContentElementType.paragraph,
            order=1,
        )


def test_gold_standard_fixture_generates_expected_complete_ordered_spec():
    approved = _approved()
    expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
    result = build_presentation_spec(approved)
    spec = result.presentation_spec

    assert spec.lesson_title == expected["lesson_title"]
    assert spec.instructional_days == expected["instructional_days"]
    assert spec.estimated_total_minutes == expected[
        "estimated_total_minutes"
    ]
    assert len(spec.slides) == expected["slide_count"]
    assert [slide.slide_type.value for slide in spec.slides] == (
        expected["ordered_slide_types"]
    )
    assert [
        slide.activity_id for slide in spec.slides if slide.activity_id
    ] == expected["ordered_activity_ids"]
    assert result.validation_report.valid
    assert result.validation_report.status == ValidationStatus.passed
    assert result.missing_sections == []


def test_presentation_ids_and_output_are_deterministic():
    approved = _approved()
    options = PresentationBuildOptions(target_slide_count=24)

    first = build_presentation_spec(approved, options)
    second = build_presentation_spec(approved, options)

    assert first == second
    assert first.presentation_spec.presentation_id == (
        second.presentation_spec.presentation_id
    )
    assert first.warnings[0].code == "target_slide_count_not_met"
    assert (
        build_presentation_spec(
            approved,
            options.model_copy(update={"target_slide_count": 23}),
        ).presentation_spec.presentation_id
        != first.presentation_spec.presentation_id
    )


def test_approved_playbook_and_valid_theme_are_required():
    approved = _approved()
    pending = approved.model_copy(update={
        "teacher_approval_status": TeacherApprovalStatus.pending,
        "approved_at": None,
    })
    with pytest.raises(ValueError, match="approved enrichment"):
        build_presentation_spec(pending)
    with pytest.raises(ValueError, match="Unknown presentation theme"):
        build_presentation_spec(
            approved,
            PresentationBuildOptions(preferred_theme_id="unknown"),
        )
    with pytest.raises(ValidationError, match="Target slide count"):
        PresentationBuildOptions(
            target_slide_count=20, maximum_slide_count=10
        )


def test_generation_preserves_order_timing_sources_and_grounding_labels():
    approved = _approved()
    result = build_presentation_spec(approved)
    spec = result.presentation_spec

    assert [slide.slide_number for slide in spec.slides] == list(
        range(1, len(spec.slides) + 1)
    )
    assert [
        slide.instructional_day
        for slide in spec.slides
        if slide.instructional_day is not None
    ] == sorted(
        slide.instructional_day
        for slide in spec.slides
        if slide.instructional_day is not None
    )
    assert result.validation_report.expected_activity_minutes == 102
    assert result.validation_report.represented_activity_minutes == 102
    assert all(value.covered for value in result.activity_coverage)
    assert result.source_coverage.complete
    assert {
        reference.source_type
        for slide in spec.slides
        for reference in slide.source_references
    } >= {"teacher_guide", "student_reader", "activity_book"}
    core = next(
        slide for slide in spec.slides
        if slide.activity_id == "activity-core-connections"
    )
    assert GroundingLabel.generated_guidance_review in (
        core.speaker_notes.grounding_labels
    )
    assert core.eld_supports[0].startswith(
        "[Generated guidance — review]"
    )


def test_required_sections_cover_days_activities_exit_ticket_and_homework():
    result = build_presentation_spec(_approved())
    spec = result.presentation_spec
    represented_ids = {
        slide_id
        for section in spec.required_sections
        for slide_id in section.represented_by_slide_ids
    }

    assert represented_ids <= {slide.slide_id for slide in spec.slides}
    assert sum(
        section.section_key.value == "day_start"
        for section in spec.required_sections
    ) == 2
    assert sum(
        section.section_key.value == "activity"
        for section in spec.required_sections
    ) == len(_approved().enriched_playbook.activities)
    assert any(
        slide.slide_type == SlideType.exit_ticket
        for slide in spec.slides
    )
    assert any(
        slide.slide_type == SlideType.homework
        for slide in spec.slides
    )


def test_validator_reports_missing_activity_notes_and_timing():
    approved = _approved()
    spec = build_presentation_spec(approved).presentation_spec
    activity_slide = next(
        slide for slide in spec.slides if slide.activity_id
    )
    changed_slides = [
        slide for slide in spec.slides
        if slide.slide_id != activity_slide.slide_id
    ]
    changed_slides[0] = changed_slides[0].model_copy(update={
        "speaker_notes": changed_slides[0].speaker_notes.model_copy(
            update={
                "purpose": None,
                "source_references": [],
                "grounding_labels": [],
            }
        )
    })
    changed = _renumber(spec.model_copy(update={"slides": changed_slides}))

    report = validate_presentation_spec(changed, approved)
    codes = {issue.code for issue in report.issues}

    assert "activity_missing_from_deck" in codes
    assert "missing_speaker_notes" in codes
    assert "timing_mismatch" in codes
    assert not report.valid


def test_validator_reports_windows_activity_day_order_and_orphan():
    approved = _approved()
    spec = build_presentation_spec(approved).presentation_spec
    windows = next(
        slide for slide in spec.slides
        if slide.activity_id == "activity-windows-mirrors"
    )
    slides = [
        slide for slide in spec.slides if slide.slide_id != windows.slide_id
    ]
    orphan = slides[-1].model_copy(update={
        "activity_id": "unknown-activity",
        "slide_type": SlideType.discussion,
        "instructional_day": 1,
    })
    slides[-1] = orphan
    changed = _renumber(spec.model_copy(update={"slides": slides}))

    report = validate_presentation_spec(changed, approved)
    codes = {issue.code for issue in report.issues}

    assert "missing_windows_and_mirrors" in codes
    assert "orphan_slide" in codes
    assert "instructional_day_ordering_error" in codes


def test_validator_rejects_unsupported_reference_and_missing_page_mapping():
    approved = _approved()
    spec = build_presentation_spec(approved).presentation_spec
    reading_index = next(
        index for index, slide in enumerate(spec.slides)
        if slide.activity_id == "activity-reading-one"
    )
    reading = spec.slides[reading_index]
    invented = reading.source_references[0].model_copy(update={
        "page_start": 99, "page_end": 100
    })
    slides = list(spec.slides)
    slides[reading_index] = reading.model_copy(update={
        "source_references": [invented]
    })
    changed = spec.model_copy(update={"slides": slides})

    report = validate_presentation_spec(changed, approved)
    codes = {issue.code for issue in report.issues}

    assert "unsupported_source_reference" in codes
    assert "missing_activity_source_reference" in codes
    assert not report.source_coverage.complete


def test_schema_rejects_unsupported_slide_type_and_invalid_numbering():
    spec = build_presentation_spec(_approved()).presentation_spec
    payload = spec.model_dump(mode="json")
    payload["slides"][0]["slide_type"] = "free_form_provider_slide"
    with pytest.raises(ValidationError):
        PresentationSpec.model_validate(payload)


def test_validator_reports_duplicated_section_and_missing_homework():
    approved = _approved()
    spec = build_presentation_spec(approved).presentation_spec
    homework = next(
        slide for slide in spec.slides
        if slide.slide_type == SlideType.homework
    )
    without_homework = [
        slide for slide in spec.slides
        if slide.slide_id != homework.slide_id
    ]
    exit_slide = next(
        slide for slide in without_homework
        if slide.slide_type == SlideType.exit_ticket
    )
    duplicate = exit_slide.model_copy(update={
        "slide_id": "duplicate-exit-ticket",
        "slide_number": len(without_homework) + 1,
    })
    changed = _renumber(spec.model_copy(update={
        "slides": without_homework + [duplicate]
    }))

    report = validate_presentation_spec(changed, approved)
    codes = {issue.code for issue in report.issues}

    assert "duplicated_required_section" in codes
    assert "missing_homework" in codes
    assert not report.valid

    payload = spec.model_dump(mode="json")
    payload["slides"][0]["slide_number"] = 2
    with pytest.raises(ValidationError, match="sequential"):
        PresentationSpec.model_validate(payload)


def test_repository_requires_valid_approval_and_exact_association(tmp_path):
    approved = _approved()
    repository = PastedLessonRepository(tmp_path / "runtime")
    repository.save_source(_source_for(approved))
    repository.save_approved_enrichment(approved)
    pending = build_presentation_spec(approved).presentation_spec
    with pytest.raises(ValueError, match="teacher-approved"):
        repository.save_presentation_spec(pending)

    approved_spec = pending.model_copy(update={
        "approval_status": ApprovalStatus.approved,
        "approved_at": approved.approved_at,
    })
    repository.save_presentation_spec(approved_spec)
    assert repository.load_presentation_spec(
        approved_spec.presentation_id
    ) == approved_spec
    assert repository.list_presentation_specs() == [approved_spec]

    mismatched = approved_spec.model_copy(update={
        "presentation_id": "mismatched-presentation",
        "playbook_id": "other-playbook",
    })
    with pytest.raises(ValueError, match="association"):
        repository.save_presentation_spec(mismatched)
    with pytest.raises(ValueError, match="Invalid artifact"):
        repository.load_presentation_spec("../unsafe")
    path = repository.presentation_specs_directory / "malformed.json"
    path.write_text('{"not": "a presentation"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed saved artifact"):
        repository.load_presentation_spec("malformed")


def test_interface_preview_validate_approve_workflow(tmp_path):
    teacheros, _ = prepared_fixture(tmp_path)
    approved = _approved()
    repository = PastedLessonRepository(tmp_path / "pasted")
    repository.save_source(_source_for(approved))
    repository.save_approved_enrichment(approved)
    interface = TeacherOSInterface(
        teacheros, pasted_repository=repository
    )

    result = interface.build_presentation_spec(
        approved.enrichment_id, {}
    )
    presentation_id = result["presentation_spec"]["presentation_id"]
    assert repository.list_presentation_specs() == []
    assert interface.validate_presentation_preview(
        presentation_id
    )["valid"]
    ordered = [
        value["slide_id"]
        for value in result["presentation_spec"]["slides"]
    ]
    reordered = list(ordered)
    reordered[2], reordered[3] = reordered[3], reordered[2]
    updated = interface.reorder_presentation_preview(
        presentation_id, reordered
    )
    assert updated["validation_report"]["valid"]
    invalid = list(reordered)
    invalid[0], invalid[1] = invalid[1], invalid[0]
    with pytest.raises(ValueError, match="title_slide_not_first"):
        interface.reorder_presentation_preview(
            presentation_id, invalid
        )

    saved = interface.approve_presentation_spec(presentation_id)
    assert saved["approval_status"] == "approved"
    assert len(interface.list_presentation_specs()) == 1
    assert interface.load_presentation_spec(
        presentation_id
    ) == saved
    with pytest.raises(KeyError):
        interface.approve_presentation_spec(presentation_id)


def test_maximum_count_warns_without_dropping_required_content():
    approved = _approved()
    result = build_presentation_spec(
        approved,
        PresentationBuildOptions(maximum_slide_count=5),
    )

    assert result.warnings[0].code == "maximum_slide_count_exceeded"
    assert len(result.presentation_spec.slides) > 5
    assert all(value.covered for value in result.activity_coverage)
    assert result.validation_report.valid


def test_disabled_required_sections_are_teacher_only_or_fail_strict_coverage():
    approved = _approved()
    teacher_only = build_presentation_spec(
        approved,
        PresentationBuildOptions(
            include_objectives=False,
            include_vocabulary=False,
            include_homework=False,
            include_exit_ticket=False,
            include_teacher_only_slides=True,
        ),
    )
    teacher_titles = [
        slide.title
        for slide in teacher_only.presentation_spec.slides
        if slide.slide_type == SlideType.teacher_only
    ]
    assert {
        "Teacher Only: Learning Objectives",
        "Teacher Only: Vocabulary",
        "Teacher Only: Exit Ticket",
        "Teacher Only: Homework",
    } <= set(teacher_titles)
    assert teacher_only.validation_report.valid

    missing = build_presentation_spec(
        approved,
        PresentationBuildOptions(
            include_vocabulary=False,
            include_teacher_only_slides=False,
        ),
    )
    assert not missing.validation_report.valid
    assert "vocabulary" in missing.missing_sections
