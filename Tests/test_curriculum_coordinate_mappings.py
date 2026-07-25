"""Tests for explicit, reviewed source-coordinate mappings."""

from __future__ import annotations

from datetime import datetime, timezone

from curriculum.intelligence.mappings import (
    apply_coordinate_mappings,
    coordinate_mapping_id,
    evaluate_mapping_staleness,
)
from curriculum.intelligence.readiness import evaluate_readiness
from schemas.curriculum_intelligence_schema import (
    ExtractionStatus,
    IndexingStatus,
    InstructionalResource,
    MappingMethod,
    MappingReviewStatus,
    ResolutionStatus,
    ResourceAssignment,
    ResourcePage,
    SourceCoordinateMapping,
    SourceProvenance,
    TextSegment,
)


def source_models():
    resource = InstructionalResource(
        id="resource-1",
        curriculum_id="curriculum-1",
        resource_type="instructional_text",
        title="Instructional text",
        source_identity="source.pdf",
        checksum="checksum-1",
        file_size=100,
        page_count=2,
        resource_version="version-1",
        extraction_version="extract-v1",
        extraction_status=ExtractionStatus.COMPLETED,
        indexing_status=IndexingStatus.INDEXED,
    )
    provenance = SourceProvenance(
        resource_id=resource.id,
        resource_version=resource.resource_version,
        resource_checksum=resource.checksum,
        pdf_page_number=4,
        display_page_number=5,
        segment_id="segment-1",
        extraction_method="text",
        extraction_version=resource.extraction_version,
        confidence=1,
    )
    segment = TextSegment(
        id="segment-1",
        resource_id=resource.id,
        resource_page_ids=["page-1"],
        segment_type="section",
        title="A section",
        sequence=1,
        exact_text="Exact source text.",
        normalized_text="Exact source text.",
        source_provenance=[provenance],
        confidence=1,
    )
    assignment = ResourceAssignment(
        id="assignment-1",
        lesson_id="lesson-1",
        resource_id=resource.id,
        assignment_type="assigned_reading",
        title="Assigned section",
        instructional_purpose="Required reading",
        printed_page_references=["12–13"],
        pdf_page_numbers=[4],
        display_page_numbers=[5],
        segment_ids=[segment.id],
        required_status="required",
        resolution_status=ResolutionStatus.PARTIAL,
        extraction_status=ExtractionStatus.COMPLETED,
        confidence=0.8,
        source_provenance=[provenance],
        warnings=["Printed numbering is absent from this edition."],
    )
    return resource, segment, assignment


def mapping_for(
    assignment: ResourceAssignment,
    resource: InstructionalResource,
    *,
    review_status: MappingReviewStatus = MappingReviewStatus.VERIFIED,
) -> SourceCoordinateMapping:
    return SourceCoordinateMapping(
        id=coordinate_mapping_id(
            assignment.id,
            "printed_page",
            "12–13",
            "pdf_page_range",
        ),
        lesson_id=assignment.lesson_id,
        assignment_id=assignment.id,
        resource_id=resource.id,
        source_version=resource.resource_version,
        resource_checksum=resource.checksum,
        extraction_version=resource.extraction_version,
        reference_system="printed_page",
        reference_value="12–13",
        target_coordinate_system="pdf_page_range",
        target_pdf_start_page=4,
        target_pdf_end_page=4,
        target_display_start_page=5,
        target_display_end_page=5,
        target_segment_ids=["segment-1"],
        mapping_method=MappingMethod.HUMAN_REVIEWED_OVERRIDE,
        confidence=1,
        review_status=review_status,
        reviewer_type="human",
        reviewer_note=(
            "The absent printed reference was manually matched to this range."
        ),
        created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        mapping_version="1.0",
        warnings=["Printed numbering is absent from this edition."],
    )


def test_mapping_ids_are_deterministic() -> None:
    args = ("assignment-1", "printed_page", "12–13", "pdf_page_range")
    assert coordinate_mapping_id(*args) == coordinate_mapping_id(*args)


def test_proposed_and_rejected_mappings_do_not_satisfy_readiness() -> None:
    resource, segment, assignment = source_models()
    for status in (
        MappingReviewStatus.PROPOSED,
        MappingReviewStatus.REJECTED,
    ):
        assignments, _ = apply_coordinate_mappings(
            [assignment],
            [mapping_for(assignment, resource, review_status=status)],
            resources=[resource],
            segments=[segment],
        )
        report = evaluate_readiness("lesson-1", [resource], assignments)
        assert assignments[0].resolution_status == ResolutionStatus.PARTIAL
        assert report.state == "partially_ready"


def test_verified_mapping_satisfies_assignment_and_retains_provenance() -> None:
    resource, segment, assignment = source_models()
    mapping = mapping_for(assignment, resource)
    assignments, mappings = apply_coordinate_mappings(
        [assignment],
        [mapping],
        resources=[resource],
        segments=[segment],
    )
    report = evaluate_readiness("lesson-1", [resource], assignments)

    assert assignments[0].resolution_status == ResolutionStatus.RESOLVED
    assert assignments[0].coordinate_mapping_ids == [mapping.id]
    assert mappings[0].source_provenance == segment.source_provenance
    assert mappings[0].reference_system == "printed_page"
    assert mappings[0].target_coordinate_system == "pdf_page_range"
    assert report.state == "source_ready"


def test_source_changes_and_missing_segment_make_mapping_stale() -> None:
    resource, segment, assignment = source_models()
    mapping = mapping_for(assignment, resource)
    changed = resource.model_copy(update={"checksum": "changed"})
    stale_checksum = evaluate_mapping_staleness(
        mapping,
        resources={resource.id: changed},
        segments={segment.id: segment},
    )
    stale_segment = evaluate_mapping_staleness(
        mapping,
        resources={resource.id: resource},
        segments={},
    )
    stale_version = evaluate_mapping_staleness(
        mapping,
        resources={
            resource.id: resource.model_copy(
                update={"resource_version": "version-2"}
            )
        },
        segments={segment.id: segment},
    )
    stale_extraction = evaluate_mapping_staleness(
        mapping,
        resources={
            resource.id: resource.model_copy(
                update={"extraction_version": "extract-v2"}
            )
        },
        segments={segment.id: segment},
    )

    assert stale_checksum.review_status == MappingReviewStatus.STALE
    assert "checksum changed" in " ".join(stale_checksum.warnings)
    assert stale_segment.review_status == MappingReviewStatus.STALE
    assert "no longer exist" in " ".join(stale_segment.warnings)
    assert stale_version.review_status == MappingReviewStatus.STALE
    assert "source version changed" in " ".join(stale_version.warnings)
    assert stale_extraction.review_status == MappingReviewStatus.STALE
    assert "extraction version changed" in " ".join(
        stale_extraction.warnings
    )


def test_mapping_does_not_add_absent_printed_label_to_resource_page() -> None:
    resource, segment, assignment = source_models()
    page = ResourcePage(
        id="page-1",
        resource_id=resource.id,
        source_version=resource.resource_version,
        pdf_page_number=4,
        display_page_number=5,
        raw_text="Exact source text.",
        normalized_text="Exact source text.",
        extraction_method="text",
        extraction_version=resource.extraction_version,
        extraction_confidence=1,
    )
    apply_coordinate_mappings(
        [assignment],
        [mapping_for(assignment, resource)],
        resources=[resource],
        segments=[segment],
    )

    assert page.printed_page_label is None
    assert page.document_page_label is None
