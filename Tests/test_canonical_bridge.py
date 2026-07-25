"""Tests for the Phase 3A read-only canonical bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.canonical_lesson_validator import CanonicalLessonValidator
from curriculum.intelligence.canonical_bridge import (
    BundleCanonicalBridge,
    CanonicalBridgeService,
    compare_canonical_lessons,
    validate_bundle_derived_candidate,
)
from curriculum.intelligence.ids import content_digest
from schemas.canonical_bridge_schema import ComparisonStatus
from schemas.canonical_lesson_schema import CanonicalLesson
from schemas.curriculum_intelligence_schema import (
    MappingReviewStatus,
    ReadinessState,
)
from Tests.test_prepared_curriculum_source_bundle import prepared


def bundle_and_candidate(tmp_path: Path):
    _, _, _, result = prepared(tmp_path)
    candidate = BundleCanonicalBridge().build(result.bundle)
    return result.bundle, candidate


def with_current_digest(bundle):
    return bundle.model_copy(update={
        "bundle_digest": content_digest(
            bundle.model_dump(mode="json", exclude={"bundle_digest"})
        )
    })


def test_bridge_builds_valid_deterministic_candidate_with_zero_ai_calls(
    tmp_path,
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("AI client must not be constructed")

    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__",
        forbidden,
    )
    bundle, first = bundle_and_candidate(tmp_path)
    second = BundleCanonicalBridge().build(bundle)

    assert isinstance(first, CanonicalLesson)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert CanonicalLessonValidator().validate(first).status == "pass"
    assert first.source_digest == second.source_digest


def test_assignment_coverage_and_source_roles_remain_separate(tmp_path) -> None:
    bundle, candidate = bundle_and_candidate(tmp_path)
    expected_titles = [
        value.title for value in bundle.required_assignments
    ]

    assert [value.title for value in candidate.lesson_blocks] == expected_titles
    assert len(candidate.lesson_blocks) == 11
    attack = next(
        value for value in candidate.lesson_blocks
        if value.title == "The Attack"
    )
    guera = next(
        value for value in candidate.lesson_blocks
        if value.title == "Güera homework reading"
    )
    assert attack.block_type == "assigned_reading"
    assert guera.block_type == "homework"
    assert (
        attack.reading_chunks[0].source_provenance[0].notes
        != guera.reading_chunks[0].source_provenance[0].notes
    )
    assert any(
        value.title == "Lesson 1 Online Resources"
        and value.block_type == "visual_resource"
        for value in candidate.lesson_blocks
    )
    assert {
        value.title for value in candidate.lesson_blocks
        if value.block_type == "teacher_reference"
    } == {"Relevant refrane reference", "Relevant story notes"}


def test_activity_and_student_resources_are_exact(tmp_path) -> None:
    _, candidate = bundle_and_candidate(tmp_path)

    assert [value.page for value in candidate.activity_book] == [
        "1.1",
        "1.2",
        "1.3",
        "SR.1",
    ]
    assert all(
        not value.expected_answers and not value.common_mistakes
        for value in candidate.activity_book
    )


def test_every_assignment_backed_element_retains_provenance(tmp_path) -> None:
    bundle, candidate = bundle_and_candidate(tmp_path)
    for block in candidate.lesson_blocks:
        provenance = block.source_provenance[0]
        notes = "\n".join(provenance.notes)
        reference = provenance.references[0]
        assignment = next(
            value for value in bundle.required_assignments
            if value.title == block.title
        )
        assert f"assignment_id={assignment.assignment_id}" in notes
        assert f"resource_id={assignment.resource_id}" in notes
        assert f"bundle_digest={bundle.bundle_digest}" in notes
        assert set(assignment.text_segment_ids) <= {
            value.removeprefix("segment_id:")
            for value in reference.section_references
            if value.startswith("segment_id:")
        }
        if assignment.coordinate_mapping_provenance:
            assert any(
                value.startswith("coordinate_mapping:")
                for value in reference.section_references
            )


def test_unsupported_instructional_fields_are_empty(tmp_path) -> None:
    bundle, candidate = bundle_and_candidate(tmp_path)

    validate_bundle_derived_candidate(candidate, bundle)
    assert candidate.lesson_information.duration_minutes == 0
    assert candidate.learning_target.availability == "unavailable"
    assert candidate.language_objective.availability == "unavailable"
    assert candidate.success_criteria == []
    assert candidate.vocabulary == []
    assert candidate.assessment == []
    assert candidate.exit_ticket.prompt.availability == "unavailable"
    assert all(
        not block.questions
        and not block.student_tasks
        and not block.slide_mappings
        and not block.wida_supports
        for block in candidate.lesson_blocks
    )


def test_bridge_rejects_non_ready_or_stale_bundle(tmp_path) -> None:
    bundle, _ = bundle_and_candidate(tmp_path)
    partial = with_current_digest(bundle.model_copy(
        update={"readiness_state": ReadinessState.PARTIALLY_READY}
    ))
    with pytest.raises(ValueError, match="source_ready"):
        BundleCanonicalBridge().build(partial)

    assignments = list(bundle.required_assignments)
    mapped_index = next(
        index for index, value in enumerate(assignments)
        if value.coordinate_mapping_provenance
    )
    mappings = list(
        assignments[mapped_index].coordinate_mapping_provenance
    )
    mappings[0] = mappings[0].model_copy(
        update={"review_status": MappingReviewStatus.STALE}
    )
    assignments[mapped_index] = assignments[mapped_index].model_copy(
        update={"coordinate_mapping_provenance": mappings}
    )
    stale = with_current_digest(bundle.model_copy(
        update={"required_assignments": assignments}
    ))
    with pytest.raises(ValueError, match="validation|stale"):
        BundleCanonicalBridge().build(stale)


def test_parallel_artifacts_and_comparison_are_deterministic(tmp_path) -> None:
    bundle, candidate = bundle_and_candidate(tmp_path)
    bundle_path = tmp_path / "prepared_source_bundle.json"
    current_path = tmp_path / "current_lesson.json"
    output = tmp_path / "bridge"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    current_path.write_text(
        candidate.model_dump_json(indent=2), encoding="utf-8"
    )
    service = CanonicalBridgeService()
    first = service.build_candidate(
        bundle_path=bundle_path,
        current_canonical_path=current_path,
        output_directory=output,
    )
    first_bytes = {
        path.name: path.read_bytes()
        for path in (
            first.candidate_path,
            first.comparison_json_path,
            first.comparison_markdown_path,
        )
    }
    second = service.build_candidate(
        bundle_path=bundle_path,
        current_canonical_path=current_path,
        output_directory=output,
    )

    assert first.comparison == second.comparison
    assert first_bytes == {
        path.name: path.read_bytes()
        for path in (
            second.candidate_path,
            second.comparison_json_path,
            second.comparison_markdown_path,
        )
    }
    assert first.candidate_path.name == (
        "bundle_derived_canonical_lesson.json"
    )
    assert first.comparison_json_path.name == (
        "canonical_bridge_comparison.json"
    )
    assert first.comparison_markdown_path.name == (
        "canonical_bridge_comparison.md"
    )
    assert not (output / "slides.json").exists()
    assert not (output / "speaker_notes.json").exists()


def test_legacy_current_artifact_is_read_only_and_reported(tmp_path) -> None:
    bundle, candidate = bundle_and_candidate(tmp_path)
    bundle_path = tmp_path / "prepared_source_bundle.json"
    current_path = tmp_path / "lesson.json"
    payload = candidate.model_dump(mode="json")
    payload["exit_ticket"] = None
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    current_path.write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    before = current_path.read_bytes()

    result = CanonicalBridgeService().build_candidate(
        bundle_path=bundle_path,
        current_canonical_path=current_path,
        output_directory=tmp_path / "comparison",
    )

    assert current_path.read_bytes() == before
    assert any(
        "does not validate" in value
        for value in result.comparison.structural_differences
    )


def test_comparison_distinguishes_required_statuses(tmp_path) -> None:
    bundle, candidate = bundle_and_candidate(tmp_path)
    comparison = compare_canonical_lessons(
        candidate, candidate, bundle
    )
    statuses = {value.status for value in comparison.comparisons}

    assert ComparisonStatus.EXACT_MATCH in statuses
    assert ComparisonStatus.EQUIVALENT_SOURCE_CONTENT in statuses
    assert ComparisonStatus.CURRENT_ONLY_CONTENT in statuses
    assert ComparisonStatus.BUNDLE_ONLY_CONTENT in statuses
    assert ComparisonStatus.UNSUPPORTED_BY_VERIFIED_SOURCES in statuses
    assert ComparisonStatus.POSSIBLE_UNPROVEN_CONTENT in statuses
