"""Deterministic validation for provider-neutral presentation specifications."""

from __future__ import annotations

from collections import Counter

from curriculum.intelligence.ids import content_digest
from schemas.playbook_enrichment_schema import (
    ApprovedPlaybookEnrichment,
    TeacherApprovalStatus,
)
from schemas.presentation_spec_schema import (
    ActivityCoverage,
    PresentationSpec,
    PresentationValidationIssue,
    PresentationValidationReport,
    RequiredSectionKey,
    SectionCoverage,
    SlideType,
    SourceCoverage,
    ValidationSeverity,
    ValidationStatus,
)


STRUCTURAL_SLIDE_TYPES = {
    SlideType.title,
    SlideType.agenda,
    SlideType.essential_question,
    SlideType.learning_objectives,
    SlideType.vocabulary,
    SlideType.reflection,
    SlideType.exit_ticket,
    SlideType.homework,
    SlideType.teacher_only,
}
SINGLETON_TYPES = {
    SlideType.title,
    SlideType.essential_question,
    SlideType.learning_objectives,
    SlideType.homework,
    SlideType.exit_ticket,
}


def _ref_key(reference) -> str:
    return content_digest(reference.model_dump(mode="json"))


def _known_references(approved: ApprovedPlaybookEnrichment):
    playbook = approved.enriched_playbook
    references = list(playbook.source_references)
    for activity in playbook.activities:
        references.extend(activity.source_references)
    by_key = {_ref_key(reference): reference for reference in references}
    return by_key


def validate_presentation_spec(
    spec: PresentationSpec,
    approved: ApprovedPlaybookEnrichment,
) -> PresentationValidationReport:
    """Validate identity, order, coverage, grounding, notes, and timing."""
    issues: list[PresentationValidationIssue] = []
    playbook = approved.enriched_playbook
    if approved.teacher_approval_status != TeacherApprovalStatus.approved:
        issues.append(PresentationValidationIssue(
            code="unapproved_enrichment",
            severity=ValidationSeverity.error,
            message="Presentation input is not teacher approved.",
        ))
    identity_pairs = {
        "approved_enrichment_id": (
            spec.approved_enrichment_id, approved.enrichment_id
        ),
        "playbook_id": (spec.playbook_id, playbook.playbook_id),
        "source_id": (spec.source_id, approved.source_id),
    }
    for field, (actual, expected) in identity_pairs.items():
        if actual != expected:
            issues.append(PresentationValidationIssue(
                code="association_mismatch",
                severity=ValidationSeverity.error,
                message=f"{field} does not match the approved playbook.",
            ))

    expected_numbers = list(range(1, len(spec.slides) + 1))
    if [slide.slide_number for slide in spec.slides] != expected_numbers:
        issues.append(PresentationValidationIssue(
            code="invalid_slide_numbering",
            severity=ValidationSeverity.error,
            message="Slide numbers must be sequential and ordered.",
        ))
    if (
        spec.slides
        and spec.slides[0].slide_type != SlideType.title
    ):
        issues.append(PresentationValidationIssue(
            code="title_slide_not_first",
            severity=ValidationSeverity.error,
            message="The required title slide must remain first.",
            slide_id=spec.slides[0].slide_id,
        ))

    slide_ids = {slide.slide_id for slide in spec.slides}
    activity_by_id = {
        activity.activity_id: activity for activity in playbook.activities
    }
    activity_order = {
        activity.activity_id: index
        for index, activity in enumerate(playbook.activities)
    }
    represented_activity_order: list[int] = []
    known_refs = _known_references(approved)
    retained_refs: dict[str, object] = {}
    unsupported_refs: dict[str, object] = {}

    day_values = [
        slide.instructional_day
        for slide in spec.slides
        if slide.instructional_day is not None
    ]
    if day_values != sorted(day_values):
        issues.append(PresentationValidationIssue(
            code="instructional_day_ordering_error",
            severity=ValidationSeverity.error,
            message="Instructional days are not in ascending order.",
        ))

    for slide in spec.slides:
        if not slide.student_facing_content:
            if slide.slide_type != SlideType.teacher_only:
                issues.append(PresentationValidationIssue(
                    code="empty_slide_content",
                    severity=ValidationSeverity.error,
                    message="Student-facing slide content is empty.",
                    slide_id=slide.slide_id,
                ))
        if slide.notes_required and not slide.speaker_notes.has_content():
            issues.append(PresentationValidationIssue(
                code="missing_speaker_notes",
                severity=ValidationSeverity.error,
                message="Required speaker notes are missing.",
                slide_id=slide.slide_id,
            ))
        if slide.activity_id:
            if slide.activity_id not in activity_by_id:
                issues.append(PresentationValidationIssue(
                    code="orphan_slide",
                    severity=ValidationSeverity.error,
                    message="Slide references an unknown activity.",
                    slide_id=slide.slide_id,
                    activity_id=slide.activity_id,
                ))
            else:
                represented_activity_order.append(
                    activity_order[slide.activity_id]
                )
        elif slide.slide_type not in STRUCTURAL_SLIDE_TYPES:
            issues.append(PresentationValidationIssue(
                code="orphan_slide",
                severity=ValidationSeverity.error,
                message="Instructional slide has no activity association.",
                slide_id=slide.slide_id,
            ))
        for reference in (
            slide.source_references
            + slide.speaker_notes.source_references
            + [
                element.source_reference
                for element in slide.student_facing_content
                if element.source_reference is not None
            ]
            + (
                [slide.visual_spec.source_reference]
                if slide.visual_spec
                and slide.visual_spec.source_reference is not None
                else []
            )
        ):
            key = _ref_key(reference)
            if key in known_refs:
                retained_refs[key] = reference
            else:
                unsupported_refs[key] = reference
                issues.append(PresentationValidationIssue(
                    code="unsupported_source_reference",
                    severity=ValidationSeverity.error,
                    message="Slide introduced a source reference absent from the approved playbook.",
                    slide_id=slide.slide_id,
                ))

    if represented_activity_order != sorted(represented_activity_order):
        issues.append(PresentationValidationIssue(
            code="activity_ordering_error",
            severity=ValidationSeverity.error,
            message="Slides do not preserve approved activity order.",
        ))

    coverage: list[ActivityCoverage] = []
    for activity in playbook.activities:
        mapped = [
            slide for slide in spec.slides
            if slide.activity_id == activity.activity_id
        ]
        activity_refs = {_ref_key(value) for value in activity.source_references}
        mapped_refs = {
            _ref_key(reference)
            for slide in mapped
            for reference in slide.source_references
        }
        covered = bool(mapped)
        coverage.append(ActivityCoverage(
            activity_id=activity.activity_id,
            covered=covered,
            slide_ids=[slide.slide_id for slide in mapped],
            retained_source_references=[
                value for value in activity.source_references
                if _ref_key(value) in mapped_refs
            ],
        ))
        if not covered:
            code = (
                "missing_windows_and_mirrors"
                if "windows and mirrors" in activity.title.casefold()
                else "activity_missing_from_deck"
            )
            issues.append(PresentationValidationIssue(
                code=code,
                severity=ValidationSeverity.error,
                message=f"Required activity is not represented: {activity.title}",
                activity_id=activity.activity_id,
            ))
        elif activity_refs - mapped_refs:
            issues.append(PresentationValidationIssue(
                code="missing_activity_source_reference",
                severity=ValidationSeverity.error,
                message=f"Activity source references were not fully retained: {activity.title}",
                activity_id=activity.activity_id,
            ))

    section_coverage: list[SectionCoverage] = []
    for section in spec.required_sections:
        present = [
            value for value in section.represented_by_slide_ids
            if value in slide_ids
        ]
        covered = bool(present)
        section_coverage.append(SectionCoverage(
            section_key=section.section_key.value,
            required=section.required,
            covered=covered,
            slide_ids=present,
        ))
        if section.required and not covered:
            issues.append(PresentationValidationIssue(
                code=f"missing_{section.section_key.value}",
                severity=ValidationSeverity.error,
                message=f"Required section is not represented: {section.section_key.value}",
                activity_id=section.activity_id,
            ))

    counts = Counter(slide.slide_type for slide in spec.slides)
    for slide_type in SINGLETON_TYPES:
        if counts[slide_type] > 1:
            issues.append(PresentationValidationIssue(
                code="duplicated_required_section",
                severity=ValidationSeverity.error,
                message=f"Required singleton section is duplicated: {slide_type.value}",
            ))

    day_starts = {
        slide.instructional_day
        for slide in spec.slides
        if slide.slide_type == SlideType.agenda
        and slide.instructional_day is not None
    }
    for day in playbook.instructional_days:
        if day not in day_starts:
            issues.append(PresentationValidationIssue(
                code="missing_day_start",
                severity=ValidationSeverity.error,
                message=f"Instructional day {day} has no visible starting point.",
            ))
        first_for_day = next(
            (
                slide for slide in spec.slides
                if slide.instructional_day == day
            ),
            None,
        )
        if (
            first_for_day is not None
            and first_for_day.slide_type != SlideType.agenda
        ):
            issues.append(PresentationValidationIssue(
                code="invalid_day_start_order",
                severity=ValidationSeverity.error,
                message=(
                    f"Instructional day {day} must begin with its day opener."
                ),
                slide_id=first_for_day.slide_id,
            ))

    expected_minutes = sum(
        activity.duration_minutes or 0 for activity in playbook.activities
    )
    represented_minutes = sum(
        slide.estimated_minutes or 0
        for slide in spec.slides
        if slide.activity_id is not None
    )
    if represented_minutes != expected_minutes:
        issues.append(PresentationValidationIssue(
            code="timing_mismatch",
            severity=ValidationSeverity.error,
            message=(
                f"Activity timing is {represented_minutes} minutes; "
                f"approved playbook timing is {expected_minutes} minutes."
            ),
        ))

    all_expected_refs = set(known_refs)
    source_coverage = SourceCoverage(
        expected_reference_count=len(all_expected_refs),
        retained_reference_count=len(set(retained_refs) & all_expected_refs),
        unsupported_references=list(unsupported_refs.values()),
        complete=(
            not unsupported_refs
            and all_expected_refs <= set(retained_refs)
        ),
    )
    if all_expected_refs and not source_coverage.complete:
        issues.append(PresentationValidationIssue(
            code="incomplete_source_coverage",
            severity=ValidationSeverity.error,
            message="Presentation does not retain all approved source references.",
        ))

    errors = [
        issue for issue in issues
        if issue.severity == ValidationSeverity.error
    ]
    warnings = [
        issue for issue in issues
        if issue.severity == ValidationSeverity.warning
    ]
    status = (
        ValidationStatus.failed if errors
        else ValidationStatus.passed_with_warnings if warnings
        else ValidationStatus.passed
    )
    return PresentationValidationReport(
        status=status,
        issues=issues,
        section_coverage=section_coverage,
        activity_coverage=coverage,
        source_coverage=source_coverage,
        expected_activity_minutes=expected_minutes,
        represented_activity_minutes=represented_minutes,
        valid=not errors,
    )


__all__ = ["validate_presentation_spec"]
