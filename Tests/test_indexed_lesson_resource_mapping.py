from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from curriculum.intelligence.lesson_resource_mapping import (
    IndexedLessonResourceMappingBuilder,
    validate_indexed_lesson_manifest,
)
from curriculum.intelligence.mapping_review import (
    consolidated_mapping_review_markdown,
)
from curriculum.intelligence.propose_lesson_mapping import (
    propose_lesson_mappings,
)
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
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
LESSON_TWO_MANIFEST = (
    ROOT
    / "curriculum/mappings/"
    "ckla_grade_8_unit_1_lesson_2_resource_manifest.json"
)
BOUNDARIES = {
    3: (63, 76),
    4: (77, 89),
    5: (90, 99),
    6: (100, 111),
    7: (112, 121),
    8: (122, 132),
    9: (133, 139),
}


def _repository():
    if not INDEX.is_file() or not DATABASE.is_file():
        pytest.skip("Registered Unit 1 curriculum intelligence unavailable.")
    return CurriculumIntelligenceRepository(DATABASE)


def _build(lesson: int):
    return IndexedLessonResourceMappingBuilder().build(
        index_path=INDEX,
        repository=_repository(),
        lesson_number=lesson,
    )


@pytest.mark.parametrize("lesson,boundary", BOUNDARIES.items())
def test_generic_builder_uses_exact_indexed_boundaries(lesson, boundary):
    manifest = _build(lesson)
    assert (
        manifest.teacher_guide_pdf_start_page,
        manifest.teacher_guide_pdf_end_page,
    ) == boundary
    assert all(
        boundary[0]
        <= evidence.teacher_guide_pdf_page
        <= boundary[1]
        for assignment in manifest.assignments
        for evidence in assignment.evidence
    )


@pytest.mark.parametrize("lesson", range(3, 10))
def test_all_manifests_serialize_without_approving_reader_ranges(lesson):
    manifest = _build(lesson)
    restored = LessonResourceMappingManifest.model_validate_json(
        manifest.model_dump_json()
    )
    assert restored == manifest
    assert not any(
        assignment.verification_status
        == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
        for assignment in manifest.assignments
    )
    assert all(
        assignment.verification_status
        != ProposalStatus.DETERMINISTICALLY_VERIFIED
        for assignment in manifest.assignments
        if assignment.resource_type == "instructional_text"
    )


@pytest.mark.parametrize("lesson", range(3, 10))
def test_activity_labels_resolve_deterministically(lesson):
    manifest = _build(lesson)
    activities = [
        assignment
        for assignment in manifest.assignments
        if assignment.resource_type == "activity_resource"
    ]
    assert activities
    assert all(
        assignment.verification_status
        == ProposalStatus.DETERMINISTICALLY_VERIFIED
        for assignment in activities
    )
    assert all(
        assignment.resolution_method == "exact_document_label_boundary"
        for assignment in activities
    )


@pytest.mark.parametrize("lesson", range(3, 10))
def test_answer_keys_require_exact_current_activity_labels(lesson):
    manifest = _build(lesson)
    activity_labels = {
        assignment.title_or_label.rsplit(" ", 1)[-1]
        for assignment in manifest.assignments
        if assignment.resource_type == "activity_resource"
    }
    answer_keys = [
        assignment
        for assignment in manifest.assignments
        if "answer_key" in assignment.resource_role
    ]
    assert answer_keys
    assert all(
        assignment.title_or_label.rsplit(" ", 1)[-1]
        in activity_labels
        for assignment in answer_keys
    )
    assert all(
        assignment.resolution_method
        == "exact_answer_key_heading_and_activity_label"
        for assignment in answer_keys
    )


@pytest.mark.parametrize("lesson", (3, 4, 5, 6, 7, 8))
def test_shared_review_resources_require_explicit_current_lesson_evidence(
    lesson,
):
    manifest = _build(lesson)
    shared = [
        assignment
        for assignment in manifest.assignments
        if assignment.resource_role.startswith("shared_review_")
    ]
    assert shared
    for assignment in shared:
        label = assignment.title_or_label.rsplit(" ", 1)[-1]
        assert any(
            label in evidence.exact_reference_text
            for evidence in assignment.evidence
        )


@pytest.mark.parametrize("lesson", (3, 4, 5, 7, 8))
def test_unavailable_maps_are_not_substituted(lesson):
    manifest = _build(lesson)
    mapping = next(
        assignment
        for assignment in manifest.assignments
        if assignment.resource_role == "classroom_map"
    )
    assert (
        mapping.verification_status
        == ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES
    )
    assert mapping.resolved_resource_id is None
    assert mapping.proposed_pdf_start_page is None
    assert mapping.required_status == "required"


def test_unbounded_guided_reading_continuations_are_not_inferred():
    for lesson_number in (3, 6, 7):
        continuations = [
            assignment
            for assignment in _build(lesson_number).assignments
            if assignment.resource_role == "guided_reading_continuation"
        ]
        assert len(continuations) == 1
        continuation = continuations[0]
        assert continuation.curriculum_reference == (
            "[Have students read the rest of the story.]"
        )
        assert continuation.referenced_printed_pages == []
        assert continuation.proposed_pdf_start_page is None
        assert continuation.proposed_pdf_end_page is None
        assert continuation.verification_status == ProposalStatus.UNRESOLVED
        assert continuation.human_review_required is True


def test_validation_rejects_adjacent_lesson_evidence():
    manifest = _build(3)
    index = CKLALessonLocator().load_index(INDEX)
    entry = CKLALessonLocator.get_lesson_entry(index, 3)
    repository = _repository()
    resources = repository.load_all_resources()
    pages = {
        resource.id: repository.load_resource_pages(resource.id)
        for resource in resources
    }
    first = manifest.assignments[0]
    leaked = first.model_copy(update={
        "evidence": [
            first.evidence[0].model_copy(
                update={"teacher_guide_pdf_page": 77}
            )
        ]
    })
    invalid = manifest.model_copy(update={
        "assignments": [leaked] + manifest.assignments[1:]
    })
    with pytest.raises(ValueError, match="outside indexed boundaries"):
        validate_indexed_lesson_manifest(
            invalid,
            entry=entry,
            resources=resources,
            pages_by_resource=pages,
        )


def test_batch_writes_seven_manifests_and_consolidated_review(tmp_path):
    paths, consolidated, failures = propose_lesson_mappings(
        unit=1,
        lessons=list(range(3, 10)),
        index_path=INDEX,
        database_path=DATABASE,
        mapping_directory=tmp_path / "mappings",
        review_directory=tmp_path / "review",
    )
    assert not failures
    assert len(paths) == 7
    assert all(path.is_file() for path in paths)
    assert consolidated.is_file()
    review = consolidated.read_text()
    assert review.startswith("# Unit 1 Lessons 3–9 Mapping Review")
    assert "## Lesson 3 decisions" in review
    assert "## Lesson 9 decisions" in review


def test_consolidated_review_counts_human_decisions():
    manifests = [_build(lesson) for lesson in range(3, 10)]
    review = consolidated_mapping_review_markdown(manifests)
    assert "Human decisions" in review
    assert "Unavailable teacher-supplied resources" in review
    assert "Selfie assessment selections" in review


def test_lesson_one_and_two_configuration_files_remain_unchanged():
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (LESSON_ONE_MAPPING, LESSON_TWO_MANIFEST)
    }
    for lesson in range(3, 10):
        _build(lesson)
    after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (LESSON_ONE_MAPPING, LESSON_TWO_MANIFEST)
    }
    assert after == before


def test_generic_proposal_path_has_no_external_provider_dependency(
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    assert _build(3).lesson_number == 3
