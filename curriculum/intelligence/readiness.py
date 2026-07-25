"""Deterministic source-readiness evaluation."""

from __future__ import annotations

from schemas.curriculum_intelligence_schema import (
    ExtractionStatus,
    FindingSeverity,
    InstructionalResource,
    ReadinessReport,
    ReadinessState,
    ResolutionStatus,
    ResourceAssignment,
    ValidationFinding,
)


def evaluate_readiness(
    lesson_id: str,
    resources: list[InstructionalResource],
    assignments: list[ResourceAssignment],
) -> ReadinessReport:
    achieved = [ReadinessState.REGISTERED]
    if resources and all(
        value.extraction_status
        in {
            ExtractionStatus.COMPLETED,
            ExtractionStatus.COMPLETED_WITH_WARNINGS,
        }
        for value in resources
    ):
        achieved.append(ReadinessState.EXTRACTED)
    if resources and all(value.page_count > 0 for value in resources):
        achieved.append(ReadinessState.INDEXED)
    if assignments:
        achieved.append(ReadinessState.MAPPED)

    required = [
        value for value in assignments if value.required_status == "required"
    ]
    resolved = [
        value
        for value in required
        if value.resolution_status == ResolutionStatus.RESOLVED
    ]
    blockers = [
        ValidationFinding(
            code="required_assignment_unresolved",
            severity=FindingSeverity.ERROR,
            message=(
                f"{assignment.title} is "
                f"{assignment.resolution_status.value}."
            ),
            reference_id=assignment.id,
        )
        for assignment in required
        if assignment.resolution_status != ResolutionStatus.RESOLVED
    ]
    warnings = [
        ValidationFinding(
            code="assignment_warning",
            severity=FindingSeverity.WARNING,
            message=f"{assignment.title}: {warning}",
            reference_id=assignment.id,
        )
        for assignment in assignments
        for warning in assignment.warnings
    ]
    if required and len(resolved) == len(required):
        state = ReadinessState.SOURCE_READY
        achieved.append(ReadinessState.SOURCE_READY)
    else:
        state = ReadinessState.PARTIALLY_READY
        achieved.append(ReadinessState.PARTIALLY_READY)
    return ReadinessReport(
        lesson_id=lesson_id,
        state=state,
        achieved_states=list(dict.fromkeys(achieved)),
        required_assignment_count=len(required),
        resolved_required_assignment_count=len(resolved),
        blockers=blockers,
        warnings=warnings,
    )


__all__ = ["evaluate_readiness"]
