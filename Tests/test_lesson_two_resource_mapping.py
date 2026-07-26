from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from curriculum.intelligence.lesson_resource_mapping import (
    LessonTwoResourceMappingBuilder,
    validate_lesson_two_manifest,
)
from curriculum.intelligence.mapping_review import lesson_mapping_review_markdown
from curriculum.intelligence.repository import CurriculumIntelligenceRepository
from curriculum.lesson_locator import CKLALessonLocator
from schemas.curriculum_mapping_proposal_schema import (
    LessonResourceMappingManifest,
    ProposalStatus,
)


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data/indexes/ckla_grade_8_unit_1_index.json"
DATABASE = ROOT / "data/curriculum/library.sqlite3"
LESSON_ONE_MAPPING = (
    ROOT
    / "curriculum/mappings/"
    "ckla_grade_8_unit_1_lesson_1_coordinate_mappings.json"
)


def _build():
    if not INDEX.is_file() or not DATABASE.is_file():
        pytest.skip("Registered Unit 1 curriculum intelligence is unavailable.")
    repository = CurriculumIntelligenceRepository(DATABASE)
    manifest = LessonTwoResourceMappingBuilder().build(
        index_path=INDEX, repository=repository
    )
    index = CKLALessonLocator().load_index(INDEX)
    entry = CKLALessonLocator.get_lesson_entry(index, 2)
    resources = repository.load_all_resources()
    pages = {
        resource.id: repository.load_resource_pages(resource.id)
        for resource in resources
    }
    return manifest, entry, resources, pages


def test_lesson_two_uses_exact_saved_index_boundary():
    manifest, _, _, _ = _build()
    assert manifest.teacher_guide_pdf_start_page == 47
    assert manifest.teacher_guide_pdf_end_page == 62
    assert manifest.teacher_guide_printed_start_page == 42
    assert manifest.teacher_guide_printed_end_page == 57
    assert all(
        47 <= evidence.teacher_guide_pdf_page <= 62
        for assignment in manifest.assignments
        for evidence in assignment.evidence
    )


def test_exact_lesson_two_references_and_activity_labels_are_preserved():
    manifest, _, _, _ = _build()
    references = {item.curriculum_reference for item in manifest.assignments}
    assert "“Burrito Man” [pages 59–69]" in references
    assert "“Band-Aid” [pages 71–91]" in references
    assert "homework reading “Güera” (pages 51–57)" in references
    for label in ("1.3", "2.1", "2.2", "2.3", "2.4", "2.5"):
        item = next(
            value for value in manifest.assignments
            if value.curriculum_reference == f"Activity Page {label}"
        )
        assert item.verification_status == ProposalStatus.DETERMINISTICALLY_VERIFIED
        assert item.resolution_method == "exact_document_label_boundary"


def test_answer_keys_match_exact_activity_labels_only():
    manifest, _, _, _ = _build()
    answer_keys = [
        item for item in manifest.assignments
        if "answer_key" in item.resource_role
    ]
    assert {item.title_or_label for item in answer_keys} == {
        "Answer Key 1.3", "Answer Key 2.2", "Answer Key 2.3"
    }
    assert {
        (item.title_or_label, item.proposed_pdf_start_page)
        for item in answer_keys
    } == {
        ("Answer Key 1.3", 154),
        ("Answer Key 2.2", 154),
        ("Answer Key 2.3", 155),
    }
    assert not any("2.4" in item.title_or_label or "2.5" in item.title_or_label for item in answer_keys)


def test_reflowed_story_mappings_record_human_reviewed_overrides():
    manifest, _, _, _ = _build()
    reviewed = [
        item for item in manifest.assignments
        if item.resource_type == "instructional_text"
    ]
    assert reviewed
    assert all(
        item.verification_status == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
        for item in reviewed
    )
    assert all(not item.human_review_required for item in reviewed)
    assert all(item.reviewer_note for item in reviewed)


def test_band_aid_preserves_principal_range_and_guided_continuation():
    manifest, _, _, pages = _build()
    assignment = next(
        item for item in manifest.assignments
        if item.curriculum_reference == "“Band-Aid” [pages 71–91]"
    )
    assert assignment.referenced_printed_pages == [
        "71–91", "guided reading through 92"
    ]
    assert (
        "principal at-a-glance assignment remains pages 71–91"
        in assignment.reviewer_note
    )
    reader_page = next(
        page
        for resource_pages in pages.values()
        for page in resource_pages
        if page.pdf_page_number == 54
        and "Her laugh chiming like silver bells" in page.normalized_text
    )
    assert reader_page.pdf_page_number == 54


def test_map_remains_unresolved_and_requires_teacher_supply():
    manifest, _, _, _ = _build()
    assignment = next(
        item for item in manifest.assignments
        if item.resource_role == "classroom_map"
    )
    assert assignment.verification_status == ProposalStatus.UNRESOLVED
    assert assignment.resolved_resource_id is None
    assert assignment.proposed_pdf_start_page is None
    assert assignment.resolution_method == "no_registered_exact_asset_match"


def test_validation_rejects_adjacent_lesson_leakage():
    manifest, entry, resources, pages = _build()
    first = manifest.assignments[0]
    leaked = first.model_copy(update={
        "evidence": [
            first.evidence[0].model_copy(
                update={"teacher_guide_pdf_page": 63}
            )
        ]
    })
    invalid = manifest.model_copy(
        update={"assignments": [leaked] + manifest.assignments[1:]}
    )
    with pytest.raises(ValueError, match="leaks outside Lesson 2"):
        validate_lesson_two_manifest(
            invalid, entry=entry, resources=resources,
            pages_by_resource=pages,
        )


def test_manifest_round_trip_and_review_document():
    manifest, _, _, _ = _build()
    restored = LessonResourceMappingManifest.model_validate_json(
        manifest.model_dump_json()
    )
    assert restored == manifest
    review = lesson_mapping_review_markdown(manifest)
    assert review.startswith("# Lesson 2 Mapping Review")
    assert "## Decisions required before generation" in review
    assert "Burrito Man" in review
    assert "Activity Page 2.3" in review


def test_lesson_one_mapping_remains_unchanged_during_build():
    before = hashlib.sha256(LESSON_ONE_MAPPING.read_bytes()).hexdigest()
    _build()
    after = hashlib.sha256(LESSON_ONE_MAPPING.read_bytes()).hexdigest()
    assert before == after


def test_mapping_builder_has_no_external_provider_dependency(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    manifest, _, _, _ = _build()
    assert manifest.lesson_number == 2
