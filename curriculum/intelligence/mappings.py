"""Validation and application of explicit coordinate mappings."""

from __future__ import annotations

from collections.abc import Iterable

from curriculum.intelligence.ids import stable_id
from schemas.curriculum_intelligence_schema import (
    InstructionalResource,
    MappingReviewStatus,
    ResolutionStatus,
    ResourceAssignment,
    SourceCoordinateMapping,
    SourceProvenance,
    TextSegment,
)


def coordinate_mapping_id(
    assignment_id: str,
    reference_system: str,
    reference_value: str,
    target_coordinate_system: str,
) -> str:
    return stable_id(
        "mapping",
        assignment_id,
        reference_system,
        reference_value,
        target_coordinate_system,
    )


def _unique_provenance(
    values: Iterable[SourceProvenance],
) -> list[SourceProvenance]:
    seen = set()
    output = []
    for value in values:
        key = (
            value.resource_id,
            value.resource_version,
            value.pdf_page_number,
            value.segment_id,
        )
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output


def evaluate_mapping_staleness(
    mapping: SourceCoordinateMapping,
    *,
    resources: dict[str, InstructionalResource],
    segments: dict[str, TextSegment],
) -> SourceCoordinateMapping:
    """Return a mapping with current provenance or an explicit stale state."""
    if mapping.review_status != MappingReviewStatus.VERIFIED:
        return mapping
    reasons: list[str] = []
    resource = resources.get(mapping.resource_id)
    if resource is None:
        reasons.append("Mapped resource no longer exists.")
    else:
        if resource.checksum != mapping.resource_checksum:
            reasons.append("Mapped resource checksum changed.")
        if resource.resource_version != mapping.source_version:
            reasons.append("Mapped source version changed.")
        if resource.extraction_version != mapping.extraction_version:
            reasons.append("Mapped extraction version changed.")
    target_segments = [
        segments.get(segment_id) for segment_id in mapping.target_segment_ids
    ]
    if any(segment is None for segment in target_segments):
        reasons.append("One or more mapped text segments no longer exist.")
    existing_segments = [
        segment for segment in target_segments if segment is not None
    ]
    if existing_segments:
        page_numbers = [
            provenance.pdf_page_number
            for segment in existing_segments
            for provenance in segment.source_provenance
            if provenance.pdf_page_number is not None
        ]
        if (
            not page_numbers
            or min(page_numbers) != mapping.target_pdf_start_page
            or max(page_numbers) != mapping.target_pdf_end_page
        ):
            reasons.append(
                "Mapped segment coordinates no longer match the reviewed PDF range."
            )
    if reasons:
        return mapping.model_copy(update={
            "review_status": MappingReviewStatus.STALE,
            "warnings": list(dict.fromkeys(mapping.warnings + reasons)),
        })
    provenance = _unique_provenance(
        provenance
        for segment in existing_segments
        for provenance in segment.source_provenance
    )
    return mapping.model_copy(update={"source_provenance": provenance})


def apply_coordinate_mappings(
    assignments: list[ResourceAssignment],
    mappings: list[SourceCoordinateMapping],
    *,
    resources: list[InstructionalResource],
    segments: list[TextSegment],
) -> tuple[list[ResourceAssignment], list[SourceCoordinateMapping]]:
    """Apply only current verified mappings to their exact assignments."""
    resources_by_id = {value.id: value for value in resources}
    segments_by_id = {value.id: value for value in segments}
    evaluated = [
        evaluate_mapping_staleness(
            mapping,
            resources=resources_by_id,
            segments=segments_by_id,
        )
        for mapping in mappings
    ]
    by_assignment: dict[str, list[SourceCoordinateMapping]] = {}
    for mapping in evaluated:
        by_assignment.setdefault(mapping.assignment_id, []).append(mapping)
    output = []
    for assignment in assignments:
        applicable = [
            mapping
            for mapping in by_assignment.get(assignment.id, [])
            if mapping.review_status == MappingReviewStatus.VERIFIED
            and mapping.lesson_id == assignment.lesson_id
            and mapping.resource_id == assignment.resource_id
            and set(mapping.target_segment_ids) <= set(assignment.segment_ids)
        ]
        if applicable:
            mapping_warnings = [
                warning
                for mapping in applicable
                for warning in mapping.warnings
            ]
            output.append(assignment.model_copy(update={
                "resolution_status": ResolutionStatus.RESOLVED,
                "coordinate_mapping_ids": list(dict.fromkeys(
                    assignment.coordinate_mapping_ids
                    + [mapping.id for mapping in applicable]
                )),
                "warnings": list(dict.fromkeys(
                    assignment.warnings + mapping_warnings
                )),
            }))
        else:
            output.append(assignment)
    return output, evaluated


__all__ = [
    "apply_coordinate_mappings",
    "coordinate_mapping_id",
    "evaluate_mapping_staleness",
]
