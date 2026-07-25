"""Deterministic preparation of one lesson's verified source bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from curriculum.intelligence.ids import content_digest, file_checksum
from curriculum.intelligence.mappings import evaluate_mapping_staleness
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
from curriculum.intelligence.snapshot import write_json
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    InstructionalResource,
    MappingReviewStatus,
    ReadinessState,
    ResolutionStatus,
    ResourceAssignment,
    SourceCoordinateMapping,
    TextSegment,
    ValidationFinding,
)
from schemas.prepared_curriculum_source_schema import (
    CoordinateMappingProvenance,
    CurriculumReference,
    PreparedBundleBuildInputs,
    PreparedCurriculumSourceBundle,
    PreparedResourceSummary,
    PreparedSourceAssignment,
    PreparedSourceSegment,
    VerifiedSourceCoordinate,
)


INTELLIGENCE_SCHEMA_VERSION = "1.0"
BUNDLE_SCHEMA_VERSION = "1.0"
BUNDLE_BUILDER_VERSION = "1.0"


@dataclass(frozen=True)
class PreparedBundleResult:
    bundle: PreparedCurriculumSourceBundle
    output_path: Path
    reused: bool


def _digest(values) -> str:
    if isinstance(values, list):
        payload = [
            value.model_dump(mode="json")
            for value in sorted(values, key=lambda item: item.id)
        ]
    else:
        payload = values.model_dump(mode="json")
    return content_digest(payload)


def _resource_summary(
    resource: InstructionalResource,
) -> PreparedResourceSummary:
    source = Path(resource.source_identity)
    available = source.is_file()
    observed_checksum = file_checksum(source) if available else None
    current = available and observed_checksum == resource.checksum
    warnings = list(resource.warnings)
    if not available:
        warnings.append("Registered source is not currently available.")
    elif not current:
        warnings.append(
            "Registered source checksum does not match the current source."
        )
    return PreparedResourceSummary(
        resource_id=resource.id,
        resource_type=resource.resource_type,
        title=resource.title,
        source_identity=resource.source_identity,
        stored_checksum=resource.checksum,
        observed_checksum=observed_checksum,
        source_version=resource.resource_version,
        extraction_version=resource.extraction_version,
        source_available=available,
        current=current,
        warnings=list(dict.fromkeys(warnings)),
    )


def _references(assignment: ResourceAssignment) -> list[CurriculumReference]:
    values = []
    groups = (
        ("printed_page", assignment.printed_page_references),
        ("document_label", assignment.document_labels),
        ("story_relative_page", assignment.story_relative_page_references),
        ("section", assignment.section_references),
    )
    for system, references in groups:
        values.extend(
            CurriculumReference(reference_system=system, value=value)
            for value in references
        )
    return values


def _coordinates(
    assignment: ResourceAssignment,
) -> list[VerifiedSourceCoordinate]:
    values = []
    if assignment.pdf_page_numbers:
        values.append(VerifiedSourceCoordinate(
            coordinate_system="pdf_page_zero_based",
            start=str(min(assignment.pdf_page_numbers)),
            end=str(max(assignment.pdf_page_numbers)),
        ))
    if assignment.display_page_numbers:
        values.append(VerifiedSourceCoordinate(
            coordinate_system="pdf_page_display",
            start=str(min(assignment.display_page_numbers)),
            end=str(max(assignment.display_page_numbers)),
        ))
    return values


def _prepared_segment(segment: TextSegment) -> PreparedSourceSegment:
    return PreparedSourceSegment(
        segment_id=segment.id,
        resource_id=segment.resource_id,
        segment_type=segment.segment_type,
        title=segment.title,
        sequence=segment.sequence,
        exact_text=segment.exact_text,
        resource_page_ids=segment.resource_page_ids,
        provenance=segment.source_provenance,
        confidence=segment.confidence,
    )


def _mapping_provenance(
    mapping: SourceCoordinateMapping,
) -> CoordinateMappingProvenance:
    return CoordinateMappingProvenance(
        mapping_id=mapping.id,
        reference_system=mapping.reference_system,
        reference_value=mapping.reference_value,
        target_coordinate_system=mapping.target_coordinate_system,
        target_pdf_start_page=mapping.target_pdf_start_page,
        target_pdf_end_page=mapping.target_pdf_end_page,
        target_display_start_page=mapping.target_display_start_page,
        target_display_end_page=mapping.target_display_end_page,
        target_segment_ids=mapping.target_segment_ids,
        mapping_method=mapping.mapping_method,
        review_status=mapping.review_status,
        mapping_version=mapping.mapping_version,
        resource_checksum=mapping.resource_checksum,
        source_version=mapping.source_version,
        extraction_version=mapping.extraction_version,
        reviewer_type=mapping.reviewer_type,
        reviewer_note=mapping.reviewer_note,
        provenance=mapping.source_provenance,
        warnings=mapping.warnings,
    )


def _finding(
    code: str,
    message: str,
    reference_id: str,
    *,
    warning: bool = False,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=(
            FindingSeverity.WARNING if warning else FindingSeverity.ERROR
        ),
        message=message,
        reference_id=reference_id,
    )


def _bundle_digest(bundle: PreparedCurriculumSourceBundle) -> str:
    return content_digest(
        bundle.model_dump(mode="json", exclude={"bundle_digest"})
    )


def validate_prepared_source_bundle(
    bundle: PreparedCurriculumSourceBundle,
) -> list[ValidationFinding]:
    """Return structural or digest errors in an already built bundle."""
    findings: list[ValidationFinding] = []
    resources = {
        value.resource_id: value for value in bundle.resource_summaries
    }
    assignments = bundle.required_assignments + bundle.optional_assignments
    for assignment in assignments:
        resource = resources.get(assignment.resource_id)
        if resource is None:
            findings.append(_finding(
                "bundle_resource_missing",
                f"{assignment.title} has no declared resource.",
                assignment.assignment_id,
            ))
        if (
            assignment.required_status == "required"
            and assignment.resolution_status == ResolutionStatus.RESOLVED
            and not assignment.source_segments
        ):
            findings.append(_finding(
                "resolved_assignment_has_no_segment",
                f"{assignment.title} has no retrieved source segment.",
                assignment.assignment_id,
            ))
        if (
            assignment.resolution_status != ResolutionStatus.RESOLVED
            and assignment.available
        ):
            findings.append(_finding(
                "unresolved_assignment_marked_available",
                f"{assignment.title} is unresolved but marked available.",
                assignment.assignment_id,
            ))
        for segment in assignment.source_segments:
            if segment.resource_id != assignment.resource_id:
                findings.append(_finding(
                    "segment_resource_mismatch",
                    f"{segment.segment_id} is attributed to the wrong resource.",
                    assignment.assignment_id,
                ))
            for provenance in segment.provenance:
                if (
                    provenance.resource_id != segment.resource_id
                    or provenance.segment_id != segment.segment_id
                    or (
                        provenance.pdf_page_number is not None
                        and provenance.display_page_number
                        != provenance.pdf_page_number + 1
                    )
                ):
                    findings.append(_finding(
                        "segment_provenance_mismatch",
                        f"{segment.segment_id} has inconsistent provenance.",
                        assignment.assignment_id,
                    ))
            if len(segment.resource_page_ids) != len(segment.provenance):
                findings.append(_finding(
                    "segment_page_provenance_mismatch",
                    f"{segment.segment_id} page and provenance counts differ.",
                    assignment.assignment_id,
                ))
        for mapping in assignment.coordinate_mapping_provenance:
            if (
                assignment.available
                and mapping.review_status != MappingReviewStatus.VERIFIED
            ):
                findings.append(_finding(
                    "coordinate_mapping_not_current",
                    f"{mapping.mapping_id} is not currently verified.",
                    assignment.assignment_id,
                ))
    if bundle.bundle_digest != _bundle_digest(bundle):
        findings.append(_finding(
            "bundle_digest_mismatch",
            "Bundle digest does not match the bundled inputs.",
            bundle.lesson_id,
        ))
    return findings


class PreparedCurriculumSourceBundleBuilder:
    """Build and safely reuse a bundle from persisted intelligence records."""

    def __init__(
        self,
        repository: CurriculumIntelligenceRepository,
    ) -> None:
        self.repository = repository

    def build(
        self,
        lesson_id: str,
        output_path: str | Path,
    ) -> PreparedBundleResult:
        lesson = self.repository.load_lesson(lesson_id)
        assignments = self.repository.load_assignments(lesson_id)
        resource_ids = [value.resource_id for value in assignments]
        resources = self.repository.load_resources(resource_ids)
        segment_ids = [
            segment_id
            for assignment in assignments
            for segment_id in assignment.segment_ids
        ]
        segments = self.repository.load_segments(segment_ids)
        mappings = self.repository.load_coordinate_mappings(lesson_id)
        manifest = self.repository.load_latest_build_manifest(lesson_id)

        resources_by_id = {value.id: value for value in resources}
        segments_by_id = {value.id: value for value in segments}
        evaluated_mappings = [
            evaluate_mapping_staleness(
                mapping,
                resources=resources_by_id,
                segments=segments_by_id,
            )
            for mapping in mappings
        ]
        mappings_by_id = {
            value.id: value for value in evaluated_mappings
        }
        resource_summaries = [
            _resource_summary(value)
            for value in sorted(resources, key=lambda item: item.id)
        ]
        summaries_by_id = {
            value.resource_id: value for value in resource_summaries
        }

        required = []
        optional = []
        blockers: list[ValidationFinding] = []
        warnings: list[ValidationFinding] = []
        all_resolved_segments: dict[str, PreparedSourceSegment] = {}
        for assignment in assignments:
            resource = resources_by_id.get(assignment.resource_id)
            resource_summary = summaries_by_id.get(assignment.resource_id)
            assigned_segments = [
                segments_by_id[segment_id]
                for segment_id in assignment.segment_ids
                if segment_id in segments_by_id
            ]
            attached_mappings = [
                mappings_by_id[mapping_id]
                for mapping_id in assignment.coordinate_mapping_ids
                if mapping_id in mappings_by_id
            ]
            mappings_current = (
                len(attached_mappings)
                == len(assignment.coordinate_mapping_ids)
                and all(
                    value.review_status == MappingReviewStatus.VERIFIED
                    for value in attached_mappings
                )
            )
            segments_current = (
                len(assigned_segments) == len(assignment.segment_ids)
                and all(
                    segment.resource_id == assignment.resource_id
                    and bool(segment.source_provenance)
                    and all(
                        provenance.resource_id == assignment.resource_id
                        and provenance.resource_checksum
                        == resource.checksum
                        and provenance.resource_version
                        == resource.resource_version
                        and provenance.extraction_version
                        == resource.extraction_version
                        and provenance.segment_id == segment.id
                        for provenance in segment.source_provenance
                    )
                    for segment in assigned_segments
                )
                if resource is not None
                else False
            )
            resource_current = bool(
                resource is not None
                and resource_summary is not None
                and resource_summary.current
            )
            available = (
                assignment.resolution_status == ResolutionStatus.RESOLVED
                and bool(assigned_segments)
                and segments_current
                and resource_current
                and mappings_current
            )
            resolution = (
                ResolutionStatus.RESOLVED
                if available
                else ResolutionStatus.UNRESOLVED
            )
            assignment_warnings = list(assignment.warnings)
            if not resource_current:
                assignment_warnings.append(
                    "Assigned resource is missing or its checksum is stale."
                )
            if not segments_current:
                assignment_warnings.append(
                    "One or more assigned source segments are missing or "
                    "attributed to another resource."
                )
            if not mappings_current:
                assignment_warnings.append(
                    "One or more coordinate mappings are missing or stale."
                )
            prepared_segments = (
                [_prepared_segment(value) for value in assigned_segments]
                if available
                else []
            )
            for segment in prepared_segments:
                all_resolved_segments.setdefault(segment.segment_id, segment)
            prepared = PreparedSourceAssignment(
                assignment_id=assignment.id,
                title=assignment.title,
                assignment_type=assignment.assignment_type,
                instructional_purpose=assignment.instructional_purpose,
                required_status=assignment.required_status,
                resource_id=assignment.resource_id,
                resource_identity=(
                    resource.source_identity if resource is not None else "missing"
                ),
                original_curriculum_references=_references(assignment),
                verified_coordinates=_coordinates(assignment),
                text_segment_ids=(
                    [value.segment_id for value in prepared_segments]
                ),
                source_segments=prepared_segments,
                provenance=(
                    assignment.source_provenance if available else []
                ),
                coordinate_mapping_provenance=[
                    _mapping_provenance(value)
                    for value in attached_mappings
                ],
                resolution_status=resolution,
                available=available,
                confidence=assignment.confidence,
                warnings=list(dict.fromkeys(assignment_warnings)),
            )
            if assignment.required_status == "required":
                required.append(prepared)
                if not available:
                    blockers.append(_finding(
                        "required_assignment_unavailable",
                        f"{assignment.title} is not currently available.",
                        assignment.id,
                    ))
            else:
                optional.append(prepared)
                if not available:
                    warnings.append(_finding(
                        "optional_assignment_unavailable",
                        f"{assignment.title} is not currently available.",
                        assignment.id,
                        warning=True,
                    ))
            warnings.extend(
                _finding(
                    "assignment_warning",
                    f"{assignment.title}: {warning}",
                    assignment.id,
                    warning=True,
                )
                for warning in assignment_warnings
            )

        build_inputs = PreparedBundleBuildInputs(
            curriculum_lesson_digest=_digest(lesson),
            resource_digest=content_digest([
                value.model_dump(mode="json")
                for value in resource_summaries
            ]),
            assignment_digest=_digest(assignments),
            segment_digest=_digest(segments),
            coordinate_mapping_digest=_digest(evaluated_mappings),
            source_build_manifest_digest=_digest(manifest),
            intelligence_schema_version=INTELLIGENCE_SCHEMA_VERSION,
            bundle_schema_version=BUNDLE_SCHEMA_VERSION,
            bundle_builder_version=BUNDLE_BUILDER_VERSION,
        )
        unresolved = [
            value.assignment_id
            for value in required + optional
            if not value.available
        ]
        bundle = PreparedCurriculumSourceBundle(
            curriculum_id=lesson.curriculum_id,
            unit_id=lesson.unit_id,
            lesson_id=lesson.id,
            curriculum_lesson=lesson,
            resource_summaries=resource_summaries,
            required_assignments=required,
            optional_assignments=optional,
            resolved_source_segments=list(all_resolved_segments.values()),
            unresolved_assignments=unresolved,
            readiness_state=(
                ReadinessState.SOURCE_READY
                if not blockers
                else ReadinessState.PARTIALLY_READY
            ),
            blockers=blockers,
            warnings=warnings,
            source_build_manifest=manifest,
            build_inputs=build_inputs,
            bundle_digest="pending",
            schema_version=BUNDLE_SCHEMA_VERSION,
            builder_version=BUNDLE_BUILDER_VERSION,
        )
        bundle = bundle.model_copy(
            update={"bundle_digest": _bundle_digest(bundle)}
        )
        structural_findings = validate_prepared_source_bundle(bundle)
        if structural_findings:
            raise ValueError(
                "Prepared source bundle validation failed: "
                + "; ".join(value.message for value in structural_findings)
            )

        target = Path(output_path)
        if target.is_file():
            try:
                cached = PreparedCurriculumSourceBundle.model_validate_json(
                    target.read_text(encoding="utf-8")
                )
                if (
                    not validate_prepared_source_bundle(cached)
                    and cached.bundle_digest == bundle.bundle_digest
                ):
                    return PreparedBundleResult(
                        bundle=cached,
                        output_path=target,
                        reused=True,
                    )
            except (ValueError, OSError):
                pass
        write_json(target, bundle)
        return PreparedBundleResult(
            bundle=bundle,
            output_path=target,
            reused=False,
        )


__all__ = [
    "BUNDLE_BUILDER_VERSION",
    "BUNDLE_SCHEMA_VERSION",
    "INTELLIGENCE_SCHEMA_VERSION",
    "PreparedBundleResult",
    "PreparedCurriculumSourceBundleBuilder",
    "validate_prepared_source_bundle",
]
