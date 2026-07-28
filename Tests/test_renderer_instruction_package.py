"""Phase 3E provider-neutral renderer instruction tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.interface_server import TeacherOSInterface
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
)
from curriculum.intelligence.presentation_spec import build_presentation_spec
from curriculum.intelligence.renderer_instruction_adapter import (
    build_renderer_instruction_package,
    compile_theme,
    layout_contracts,
)
from curriculum.intelligence.renderer_instruction_validator import (
    validate_renderer_instruction_package,
)
from schemas.pasted_lesson_schema import PastedLessonSource
from schemas.playbook_enrichment_schema import ApprovedPlaybookEnrichment
from schemas.presentation_spec_schema import ApprovalStatus, ValidationStatus
from schemas.renderer_instruction_schema import (
    AssetStatus,
    InstructionLayout,
    RendererInstructionOptions,
    RendererInstructionPackage,
    RendererPackageApprovalStatus,
)
from Tests.test_teacheros import prepared_fixture


FIXTURES = Path(__file__).parent / "fixtures"
APPROVED_FIXTURE = (
    FIXTURES / "approved_playbook_enrichment_synthetic.json"
)
EXPECTED_FIXTURE = (
    FIXTURES / "renderer_instruction_package_synthetic_expected.json"
)


def _approved() -> ApprovedPlaybookEnrichment:
    return ApprovedPlaybookEnrichment.model_validate_json(
        APPROVED_FIXTURE.read_text(encoding="utf-8")
    )


def _approved_spec():
    approved = _approved()
    pending = build_presentation_spec(approved).presentation_spec
    return pending.model_copy(update={
        "approval_status": ApprovalStatus.approved,
        "approved_at": approved.approved_at,
    })


def _source(approved: ApprovedPlaybookEnrichment) -> PastedLessonSource:
    metadata = approved.enriched_playbook.lesson_metadata
    return PastedLessonSource(
        source_id=approved.source_id,
        grade=metadata.grade,
        unit=metadata.unit,
        lesson_number=metadata.lesson_number,
        lesson_title=metadata.lesson_title,
        teacher_guide_text="Synthetic teacher guide source.",
        student_reader_text="Synthetic reader source.",
        activity_book_text="Synthetic activity source.",
        created_at=approved.generated_at,
        updated_at=approved.generated_at,
    )


def _repository_with_spec(tmp_path):
    approved = _approved()
    spec = _approved_spec()
    repository = PastedLessonRepository(tmp_path / "runtime")
    repository.save_source(_source(approved))
    repository.save_approved_enrichment(approved)
    repository.save_presentation_spec(spec)
    return repository, approved, spec


def test_schema_round_trip_and_strict_optional_models():
    result = build_renderer_instruction_package(_approved_spec())
    package = result.instruction_package
    restored = RendererInstructionPackage.model_validate_json(
        package.model_dump_json()
    )

    assert restored == package
    assert package.canvas.width == 13.333
    assert package.canvas.height == 7.5
    assert package.canvas.units.value == "inches"
    assert package.renderer_contract_version == "renderer-contract-v1"
    with pytest.raises(ValidationError):
        RendererInstructionOptions.model_validate({"unknown": True})


def test_synthetic_golden_fixture_preserves_count_order_and_contract():
    expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))
    spec = _approved_spec()
    result = build_renderer_instruction_package(spec)
    package = result.instruction_package

    assert len(package.slides) == expected["slide_count"]
    assert [slide.slide_id for slide in package.slides] == [
        slide.slide_id for slide in spec.slides
    ]
    assert [slide.slide_number for slide in package.slides] == list(
        range(1, expected["slide_count"] + 1)
    )
    assert [
        slide.layout_type.value for slide in package.slides
    ] == expected["ordered_layouts"]
    assert [
        len(slide.text_blocks) for slide in package.slides
    ] == expected["text_block_counts"]
    assert [
        slide.slide_number for slide in package.slides
        if slide.visual_blocks
    ] == expected["visual_slide_numbers"]
    assert [
        asset.asset_type.value for asset in package.asset_manifest
    ] == expected["asset_types"]
    assert [warning.code for warning in result.overflow_risks] == (
        expected["overflow_codes"]
    )
    assert package.validation_report.status.value == (
        expected["validation_status"]
    )


def test_package_ids_and_complete_output_are_deterministic():
    spec = _approved_spec()
    first = build_renderer_instruction_package(spec)
    second = build_renderer_instruction_package(spec)

    assert first == second
    assert first.instruction_package.package_id == (
        second.instruction_package.package_id
    )
    changed = build_renderer_instruction_package(
        spec,
        RendererInstructionOptions(include_slide_numbers=False),
    )
    assert changed.instruction_package.package_id != (
        first.instruction_package.package_id
    )


def test_approved_and_valid_presentation_spec_is_required():
    spec = _approved_spec()
    with pytest.raises(ValueError, match="approved PresentationSpec"):
        build_renderer_instruction_package(spec.model_copy(update={
            "approval_status": ApprovalStatus.pending,
            "approved_at": None,
        }))
    with pytest.raises(ValueError, match="valid PresentationSpec"):
        build_renderer_instruction_package(spec.model_copy(update={
            "validation_status": ValidationStatus.failed,
        }))


def test_text_visual_notes_sources_grounding_and_timing_are_preserved():
    spec = _approved_spec()
    package = build_renderer_instruction_package(spec).instruction_package
    for source, rendered in zip(spec.slides, package.slides):
        assert rendered.slide_id == source.slide_id
        assert rendered.slide_number == source.slide_number
        assert rendered.timing == source.estimated_minutes
        assert rendered.source_references == source.source_references
        assert rendered.grounding_labels == source.grounding_labels
        assert rendered.source_content_element_ids == [
            element.element_id for element in source.student_facing_content
        ]
        assert rendered.notes_payload.teacher_script == (
            source.speaker_notes.teacher_script
        )
        assert rendered.notes_payload.teacher_actions == (
            source.speaker_notes.teacher_actions
        )
        assert rendered.notes_payload.anticipated_responses == (
            source.speaker_notes.anticipated_responses
        )
        assert rendered.notes_payload.misconception_support == (
            source.speaker_notes.misconception_support
        )
        assert rendered.notes_payload.transition_language == (
            source.speaker_notes.transition_language
        )
    visual = next(slide for slide in package.slides if slide.visual_blocks)
    assert visual.visual_blocks[0].alt_text
    assert visual.visual_blocks[0].description
    assert visual.visual_blocks[0].source_uri is None


def test_theme_compilation_layout_contract_and_asset_manifest():
    spec = _approved_spec()
    theme = compile_theme(spec)
    contracts = layout_contracts()
    result = build_renderer_instruction_package(spec)

    assert theme.theme_id == "teacheros_classroom"
    assert theme.background_colors == ["#F7F4EE"]
    assert theme.heading_color == "#3B97A8"
    assert theme.body_color == "#2E2E2E"
    assert theme.title_font_family == "Aptos Display"
    assert {value.layout for value in contracts} == set(InstructionLayout)
    assert len(result.asset_requirements) == len(spec.slides)
    assert all(
        asset.status in {
            AssetStatus.not_required,
            AssetStatus.neutral_placeholder_allowed,
            AssetStatus.approved_source_required,
        }
        for asset in result.asset_requirements
    )
    assert all(asset.status != "resolved" for asset in result.asset_requirements)


def test_validator_rejects_layout_content_notes_and_slide_loss():
    spec = _approved_spec()
    package = build_renderer_instruction_package(spec).instruction_package
    first = package.slides[0]
    wrong_layout = first.model_copy(update={
        "layout_type": InstructionLayout.homework,
        "text_blocks": [
            first.text_blocks[0].model_copy(update={"text": "Changed title"})
        ] + first.text_blocks[1:],
    })
    missing_content = package.slides[1].model_copy(update={
        "source_content_element_ids": []
    })
    missing_notes = package.slides[2].model_copy(update={
        "notes_payload": package.slides[2].notes_payload.model_copy(update={
            "plain_text_fallback": "",
        })
    })
    mutated = package.model_copy(update={
        "slides": [wrong_layout, missing_content, missing_notes]
        + package.slides[3:-1],
    })
    report = validate_renderer_instruction_package(mutated, spec)
    codes = {issue.code for issue in report.issues}

    assert "invalid_layout_for_slide_type" in codes
    assert "slide_title_mutated" in codes
    assert "required_content_loss" in codes
    assert "missing_required_notes" in codes
    assert "slide_order_or_count_mismatch" in codes
    assert "slide_coverage_mismatch" in codes
    assert not report.valid


def test_validator_rejects_missing_alt_text_assets_and_orphan_blocks():
    spec = _approved_spec()
    package = build_renderer_instruction_package(spec).instruction_package
    index = next(
        index for index, slide in enumerate(package.slides)
        if slide.visual_blocks
    )
    slide = package.slides[index]
    visual = slide.visual_blocks[0].model_copy(update={"alt_text": None})
    orphan = slide.text_blocks[-1].model_copy(update={
        "source_element_id": "unknown-element"
    })
    changed_slide = slide.model_copy(update={
        "visual_blocks": [visual],
        "text_blocks": slide.text_blocks[:-1] + [orphan],
    })
    slides = list(package.slides)
    slides[index] = changed_slide
    changed = package.model_copy(update={
        "slides": slides,
        "asset_manifest": [
            asset for asset in package.asset_manifest
            if asset.slide_id != slide.slide_id
        ],
    })
    report = validate_renderer_instruction_package(changed, spec)
    codes = {issue.code for issue in report.issues}

    assert "missing_visual_alt_text" in codes
    assert "orphan_text_block" in codes
    assert "missing_asset_manifest_entry" in codes


def test_overflow_is_structured_and_never_splits_or_drops_slides():
    spec = _approved_spec()
    result = build_renderer_instruction_package(spec)

    assert result.overflow_risks
    assert all(warning.slide_id for warning in result.overflow_risks)
    assert len(result.instruction_package.slides) == len(spec.slides)
    assert [
        slide.slide_id for slide in result.instruction_package.slides
    ] == [slide.slide_id for slide in spec.slides]


def test_repository_save_load_list_and_exact_association(tmp_path):
    repository, _, spec = _repository_with_spec(tmp_path)
    pending = build_renderer_instruction_package(spec).instruction_package
    with pytest.raises(ValueError, match="approved renderer"):
        repository.save_renderer_instruction_package(pending)
    approved = pending.model_copy(update={
        "approval_status": RendererPackageApprovalStatus.approved,
        "approved_at": spec.approved_at,
    })
    repository.save_renderer_instruction_package(approved)

    assert repository.load_renderer_instruction_package(
        approved.package_id
    ) == approved
    assert repository.list_renderer_instruction_packages() == [approved]
    mismatched = approved.model_copy(update={
        "package_id": "mismatched-package",
        "playbook_id": "other-playbook",
    })
    with pytest.raises(ValueError, match="association"):
        repository.save_renderer_instruction_package(mismatched)
    with pytest.raises(ValueError, match="Invalid artifact"):
        repository.load_renderer_instruction_package("../unsafe")
    malformed = repository.renderer_packages_directory / "malformed.json"
    malformed.write_text('{"not": "a package"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed saved artifact"):
        repository.load_renderer_instruction_package("malformed")


def test_interface_preview_validate_approve_and_server_regeneration(tmp_path):
    teacheros, _ = prepared_fixture(tmp_path)
    repository, _, spec = _repository_with_spec(tmp_path)
    interface = TeacherOSInterface(
        teacheros, pasted_repository=repository
    )

    result = interface.build_renderer_instruction_package(
        spec.presentation_id, {}
    )
    package_id = result["instruction_package"]["package_id"]
    assert repository.list_renderer_instruction_packages() == []
    assert interface.validate_renderer_instruction_preview(
        package_id
    )["valid"]
    saved = interface.approve_renderer_instruction_package(package_id)
    assert saved["approval_status"] == "approved"
    assert interface.load_renderer_instruction_package(package_id) == saved
    assert len(interface.list_renderer_instruction_packages()) == 1
    with pytest.raises(KeyError):
        interface.approve_renderer_instruction_package(package_id)


def test_phase_3d_and_production_paths_remain_independent():
    root = Path(__file__).parents[1]
    adapter = (
        root / "curriculum/intelligence/renderer_instruction_adapter.py"
    ).read_text(encoding="utf-8")
    production_files = [
        root / "renderer/google_slides_renderer.py",
        root / "renderer/gamma_prompt.py",
        root / "app/teacheros.py",
    ]

    assert "googleapiclient" not in adapter
    assert "Gamma" not in adapter
    assert "PresentationSpec" in adapter
    for path in production_files:
        assert "renderer_instruction_adapter" not in path.read_text(
            encoding="utf-8"
        )
