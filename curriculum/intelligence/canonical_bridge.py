"""Read-only bridge from verified source bundles to canonical candidates."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from brain.canonical_lesson_validator import CanonicalLessonValidator
from curriculum.intelligence.bundle import validate_prepared_source_bundle
from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.snapshot import write_json
from schemas.canonical_bridge_schema import (
    CanonicalBridgeComparison,
    CanonicalFieldComparison,
    ComparisonStatus,
)
from schemas.canonical_lesson_schema import (
    ActivityBookTask,
    Agenda,
    AgendaItem,
    Availability,
    CanonicalLesson,
    CurriculumReference,
    ExitTicket,
    GroundedStatement,
    GuidanceOrigin,
    HomeworkAssignment,
    InstructionalResource,
    LessonBlock,
    LessonInformation,
    ReadingChunk,
    SourceProvenance,
    TeacherReflection,
    TimingMetadata,
)
from schemas.curriculum_intelligence_schema import (
    MappingReviewStatus,
    ReadinessState,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
    PreparedSourceAssignment,
)


BRIDGE_SCHEMA_VERSION = "1.0"
BRIDGE_BUILDER_VERSION = "1.0"


UNSUPPORTED_FIELDS = [
    "verified lesson duration and agenda timing",
    "instructional sequence within the Teacher Guide",
    "language objective",
    "success criteria",
    "reading mode",
    "teacher guidance and scripts",
    "student tasks",
    "questions and expected answers",
    "text evidence",
    "pause points",
    "annotations",
    "misconceptions and corrections",
    "WIDA and differentiation supports",
    "assessment plan",
    "exit-ticket content",
    "slide mappings and speaker notes",
    "teacher reflection prompts",
]


@dataclass(frozen=True)
class CanonicalBridgeResult:
    candidate: CanonicalLesson
    comparison: CanonicalBridgeComparison
    candidate_path: Path
    comparison_json_path: Path
    comparison_markdown_path: Path


def _canonical_reference(
    assignment: PreparedSourceAssignment,
    bundle: PreparedCurriculumSourceBundle,
) -> CurriculumReference:
    resource = next(
        value
        for value in bundle.resource_summaries
        if value.resource_id == assignment.resource_id
    )
    pdf_pages = sorted({
        provenance.pdf_page_number
        for segment in assignment.source_segments
        for provenance in segment.provenance
        if provenance.pdf_page_number is not None
    })
    printed = [
        value.value
        for value in assignment.original_curriculum_references
        if value.reference_system == "printed_page"
    ]
    sections = [
        f"segment_id:{segment_id}"
        for segment_id in assignment.text_segment_ids
    ]
    sections.extend(
        (
            "curriculum_reference:"
            f"{value.reference_system}:{value.value}"
        )
        for value in assignment.original_curriculum_references
    )
    sections.extend(
        (
            f"coordinate_mapping:{mapping.mapping_id}:"
            f"{mapping.mapping_method.value}:{mapping.review_status.value}:"
            f"{mapping.reference_system}:{mapping.reference_value}:"
            f"pdf:{mapping.target_pdf_start_page}-"
            f"{mapping.target_pdf_end_page}"
        )
        for mapping in assignment.coordinate_mapping_provenance
    )
    mapping_warnings = [
        warning
        for mapping in assignment.coordinate_mapping_provenance
        for warning in mapping.warnings
    ]
    provenance_notes = [
        f"assignment_id={assignment.assignment_id}",
        f"resource_checksum={resource.stored_checksum}",
        f"resource_version={resource.source_version}",
        f"extraction_version={resource.extraction_version}",
        f"bundle_digest={bundle.bundle_digest}",
    ]
    return CurriculumReference(
        source_id=assignment.resource_id,
        source_type=assignment.assignment_type,
        printed_page_references=printed,
        pdf_page_numbers=pdf_pages,
        section_references=sections,
        availability=Availability.AVAILABLE,
        warnings=list(dict.fromkeys(
            assignment.warnings + mapping_warnings + provenance_notes
        )),
    )


def _provenance(
    assignment: PreparedSourceAssignment,
    bundle: PreparedCurriculumSourceBundle,
) -> SourceProvenance:
    resource = next(
        value
        for value in bundle.resource_summaries
        if value.resource_id == assignment.resource_id
    )
    return SourceProvenance(
        references=[_canonical_reference(assignment, bundle)],
        origin=GuidanceOrigin.SOURCE_DERIVED,
        availability=Availability.AVAILABLE,
        notes=[
            f"assignment_id={assignment.assignment_id}",
            f"resource_id={assignment.resource_id}",
            f"segment_ids={','.join(assignment.text_segment_ids)}",
            f"resource_checksum={resource.stored_checksum}",
            f"resource_version={resource.source_version}",
            f"extraction_version={resource.extraction_version}",
            f"bundle_digest={bundle.bundle_digest}",
        ],
    )


def _lesson_provenance(
    bundle: PreparedCurriculumSourceBundle,
) -> SourceProvenance:
    assignment = next(
        value
        for value in bundle.required_assignments
        if value.assignment_type == "defines_lesson"
    )
    return _provenance(assignment, bundle)


def _reading_chunk(
    assignment: PreparedSourceAssignment,
    bundle: PreparedCurriculumSourceBundle,
) -> ReadingChunk:
    references = [
        value.value for value in assignment.original_curriculum_references
        if value.reference_system in {
            "printed_page",
            "story_relative_page",
            "document_label",
        }
    ]
    sections = [
        value.value for value in assignment.original_curriculum_references
        if value.reference_system == "section"
    ]
    return ReadingChunk(
        id=stable_id("bridge-reading-chunk", assignment.assignment_id),
        title=assignment.title,
        purpose=assignment.instructional_purpose,
        instructional_resource_ids=[assignment.resource_id],
        reader_page_references=references,
        paragraph_or_section_references=sections,
        reading_mode="unavailable",
        timing=TimingMetadata(duration_minutes=0),
        source_provenance=[_provenance(assignment, bundle)],
        source_availability=Availability.AVAILABLE,
    )


def validate_canonical_bridge_input(
    bundle: PreparedCurriculumSourceBundle,
) -> None:
    errors = validate_prepared_source_bundle(bundle)
    if errors:
        raise ValueError(
            "Prepared bundle failed validation: "
            + "; ".join(value.message for value in errors)
        )
    if bundle.readiness_state != ReadinessState.SOURCE_READY:
        raise ValueError("Prepared bundle must be source_ready.")
    if any(
        not assignment.available
        for assignment in bundle.required_assignments
    ):
        raise ValueError("Every required assignment must be available.")
    if any(
        mapping.review_status != MappingReviewStatus.VERIFIED
        for assignment in bundle.required_assignments
        for mapping in assignment.coordinate_mapping_provenance
    ):
        raise ValueError("Canonical bridge cannot use a stale mapping.")
    readings = [
        value
        for value in bundle.required_assignments
        if value.assignment_type == "assigned_reading"
    ]
    supporting_readings = [
        value
        for value in bundle.required_assignments
        if (
            value.assignment_type == "background_reading"
            or (
                value.assignment_type == "homework"
                and any(
                    resource.resource_id == value.resource_id
                    and resource.resource_type == "instructional_text"
                    for resource in bundle.resource_summaries
                )
            )
        )
    ]
    if not readings or not supporting_readings:
        raise ValueError(
            "Main reading and supporting reading must both be present."
        )
    if set(readings[0].text_segment_ids) & set(
        supporting_readings[0].text_segment_ids
    ):
        raise ValueError(
            "Main reading and supporting reading must remain separate."
        )


def validate_bundle_derived_candidate(
    candidate: CanonicalLesson,
    bundle: PreparedCurriculumSourceBundle,
) -> None:
    """Reject instructional text that is not directly represented in input."""
    assignments = bundle.required_assignments
    if [value.title for value in candidate.lesson_blocks] != [
        value.title for value in assignments
    ]:
        raise ValueError("Candidate lesson blocks changed assignment order.")
    allowed_purposes = {
        value.instructional_purpose for value in assignments
    }
    for block in candidate.lesson_blocks:
        if (
            block.questions
            or block.student_tasks
            or block.teacher_guidance.model_dump(
                exclude_defaults=True
            )
            or block.wida_supports
            or block.slide_mappings
            or block.transitions
        ):
            raise ValueError(
                "Candidate introduced unsupported instructional content."
            )
        for chunk in block.reading_chunks:
            if (
                chunk.purpose not in allowed_purposes
                or chunk.questions
                or chunk.expected_answers
                or chunk.evidence
                or chunk.pause_points
                or chunk.annotations
                or chunk.misconceptions
                or chunk.follow_up_support
                or chunk.extensions
                or chunk.slide_mappings
            ):
                raise ValueError(
                    "Candidate introduced unsupported reading content."
                )
    if candidate.standards != bundle.curriculum_lesson.standards:
        raise ValueError("Candidate changed verified standards.")
    if candidate.materials != bundle.curriculum_lesson.materials:
        raise ValueError("Candidate changed verified materials.")
    if [value.directions for value in candidate.homework] != (
        bundle.curriculum_lesson.homework
    ):
        raise ValueError("Candidate changed verified homework text.")
    if candidate.vocabulary or candidate.assessment:
        raise ValueError(
            "Candidate introduced unsupported vocabulary or assessment."
        )
    if (
        candidate.exit_ticket.prompt.availability
        != Availability.UNAVAILABLE
    ):
        raise ValueError("Candidate introduced an unsupported exit ticket.")


class BundleCanonicalBridge:
    """Build the smallest valid canonical graph supported by the bundle."""

    def build(
        self,
        bundle: PreparedCurriculumSourceBundle,
    ) -> CanonicalLesson:
        validate_canonical_bridge_input(bundle)
        lesson = bundle.curriculum_lesson
        lesson_provenance = _lesson_provenance(bundle)
        resources = []
        for summary in bundle.resource_summaries:
            assignments = [
                value
                for value in (
                    bundle.required_assignments
                    + bundle.optional_assignments
                )
                if value.resource_id == summary.resource_id
            ]
            resources.append(InstructionalResource(
                id=summary.resource_id,
                title=summary.title,
                resource_type=summary.resource_type,
                source_identifier=summary.source_identity,
                availability=(
                    Availability.AVAILABLE
                    if summary.current
                    else Availability.UNAVAILABLE
                ),
                references=[
                    _canonical_reference(value, bundle)
                    for value in assignments
                ],
                warnings=summary.warnings,
            ))

        resource_types = {
            value.resource_id: value.resource_type
            for value in bundle.resource_summaries
        }
        blocks = []
        agenda_items = []
        for sequence, assignment in enumerate(
            bundle.required_assignments, start=1
        ):
            provenance = _provenance(assignment, bundle)
            reading_chunks = []
            if (
                assignment.assignment_type
                in {"background_reading", "assigned_reading"}
                or (
                    assignment.assignment_type == "homework"
                    and resource_types.get(assignment.resource_id)
                    == "instructional_text"
                )
            ):
                reading_chunks.append(_reading_chunk(assignment, bundle))
            block_id = stable_id(
                "bridge-lesson-block", assignment.assignment_id
            )
            blocks.append(LessonBlock(
                id=block_id,
                title=assignment.title,
                block_type=assignment.assignment_type,
                timing=TimingMetadata(duration_minutes=0),
                objective=GroundedStatement(
                    availability=Availability.UNAVAILABLE
                ),
                reading_chunks=reading_chunks,
                materials=[
                    next(
                        value.title
                        for value in bundle.resource_summaries
                        if value.resource_id == assignment.resource_id
                    )
                ],
                source_provenance=[provenance],
                availability=Availability.AVAILABLE,
            ))
            agenda_items.append(AgendaItem(
                id=stable_id("bridge-agenda", assignment.assignment_id),
                sequence=sequence,
                title=assignment.title,
                start_offset_minutes=0,
                end_offset_minutes=0,
                duration_minutes=0,
                lesson_block_reference=block_id,
                materials=blocks[-1].materials,
                status=assignment.required_status,
            ))

        activity_tasks = []
        for assignment in bundle.required_assignments:
            if resource_types.get(assignment.resource_id) != "activity_resource":
                continue
            labels = [
                value.value
                for value in assignment.original_curriculum_references
                if value.reference_system == "document_label"
            ]
            activity_tasks.append(ActivityBookTask(
                id=stable_id(
                    "bridge-activity-task", assignment.assignment_id
                ),
                resource_id=assignment.resource_id,
                page=labels[0] if labels else assignment.title,
                source_provenance=[_provenance(assignment, bundle)],
                source_availability=Availability.AVAILABLE,
            ))

        homework = [
            HomeworkAssignment(
                title=f"Homework {sequence}",
                directions=value,
                source_provenance=[lesson_provenance],
            )
            for sequence, value in enumerate(lesson.homework, start=1)
        ]
        bridge_warnings = [
            (
                "Read-only canonical bridge candidate; the production "
                "CanonicalLesson path remains unchanged."
            ),
            (
                "Verified duration and internal instructional sequence are "
                "unavailable; zero-duration blocks preserve assignment order "
                "solely for schema compatibility."
            ),
        ]
        bridge_warnings.extend(
            f"Unsupported by verified sources: {value}."
            for value in UNSUPPORTED_FIELDS
        )
        candidate = CanonicalLesson(
            lesson_information=LessonInformation(
                curriculum=lesson.curriculum_id,
                grade=lesson.grade_or_course,
                unit=lesson.unit_id,
                lesson_number=lesson.sequence,
                lesson_title=lesson.title,
                duration_minutes=0,
                essential_question=GroundedStatement(
                    availability=Availability.UNAVAILABLE
                ),
            ),
            standards=lesson.standards,
            learning_target=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            language_objective=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            success_criteria=[],
            materials=lesson.materials,
            instructional_resources=resources,
            agenda=Agenda(
                selected_duration_minutes=0,
                items=agenda_items,
            ),
            lesson_blocks=blocks,
            vocabulary=[],
            activity_book=activity_tasks,
            assessment=[],
            exit_ticket=ExitTicket(
                prompt=GroundedStatement(
                    availability=Availability.UNAVAILABLE
                ),
                timing=TimingMetadata(duration_minutes=0),
            ),
            homework=homework,
            teacher_reflection=TeacherReflection(),
            source_provenance=[lesson_provenance],
            warnings=bridge_warnings,
            source_digest=content_digest({
                "bundle_digest": bundle.bundle_digest,
                "bridge_schema_version": BRIDGE_SCHEMA_VERSION,
                "bridge_builder_version": BRIDGE_BUILDER_VERSION,
            }),
        )
        validate_bundle_derived_candidate(candidate, bundle)
        report = CanonicalLessonValidator().validate(candidate)
        if report.status == "fail":
            raise ValueError(
                "Bundle-derived CanonicalLesson failed validation: "
                + "; ".join(value.message for value in report.findings)
            )
        return candidate


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _generated_guidance_paths(value: Any, path: str = "") -> list[str]:
    output = []
    if isinstance(value, dict):
        if value.get("origin") == "generated_instructional_guidance":
            output.append(path or "$")
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            output.extend(_generated_guidance_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(
                _generated_guidance_paths(child, f"{path}[{index}]")
            )
    return output


def _comparison_digest(
    comparison: CanonicalBridgeComparison,
) -> str:
    return content_digest(
        comparison.model_dump(
            mode="json", exclude={"comparison_digest"}
        )
    )


def compare_canonical_lessons(
    current: CanonicalLesson | dict[str, Any],
    candidate: CanonicalLesson,
    bundle: PreparedCurriculumSourceBundle,
) -> CanonicalBridgeComparison:
    current_payload = (
        current.model_dump(mode="json")
        if isinstance(current, CanonicalLesson)
        else current
    )
    current_information = current_payload.get("lesson_information", {})
    current_activity = [
        value.get("page")
        for value in current_payload.get("activity_book", [])
        if isinstance(value, dict)
    ]
    candidate_activity = [value.page for value in candidate.activity_book]
    current_homework = [
        value.get("directions", "")
        for value in current_payload.get("homework", [])
        if isinstance(value, dict)
    ]
    candidate_homework = [value.directions for value in candidate.homework]
    current_resources = [
        value.get("title", "")
        for value in current_payload.get("instructional_resources", [])
        if isinstance(value, dict)
    ]
    candidate_resources = [
        value.title for value in candidate.instructional_resources
    ]
    current_generated = sorted(set(_generated_guidance_paths(
        current_payload
    )))
    current_title = current_information.get("lesson_title")
    current_number = current_information.get("lesson_number")
    current_blocks = [
        value.get("title", "")
        for value in current_payload.get("lesson_blocks", [])
        if isinstance(value, dict)
    ]
    current_duration = current_information.get("duration_minutes")
    current_source_digest = current_payload.get("source_digest")
    if not current_source_digest:
        current_source_digest = content_digest(current_payload)
    current_readings = [
        {
            "title": chunk.get("title"),
            "reader_page_references": chunk.get(
                "reader_page_references", []
            ),
        }
        for block in current_payload.get("lesson_blocks", [])
        if isinstance(block, dict)
        for chunk in block.get("reading_chunks", [])
        if isinstance(chunk, dict) and chunk.get("reader_page_references")
    ]
    candidate_readings = [
        {
            "title": chunk.title,
            "reader_page_references": chunk.reader_page_references,
        }
        for block in candidate.lesson_blocks
        for chunk in block.reading_chunks
    ]
    candidate_online = [
        value.title
        for value in candidate.instructional_resources
        if value.resource_type == "online_resource_guide"
    ]
    candidate_teacher_references = [
        value.title
        for value in candidate.lesson_blocks
        if value.block_type == "teacher_reference"
    ]
    comparisons = [
        CanonicalFieldComparison(
            field="lesson_title",
            status=(
                ComparisonStatus.EXACT_MATCH
                if current_title
                == candidate.lesson_information.lesson_title
                else ComparisonStatus.CURRENT_ONLY_CONTENT
            ),
            current_value=current_title,
            bundle_derived_value=candidate.lesson_information.lesson_title,
        ),
        CanonicalFieldComparison(
            field="lesson_number",
            status=(
                ComparisonStatus.EXACT_MATCH
                if current_number
                == candidate.lesson_information.lesson_number
                else ComparisonStatus.CURRENT_ONLY_CONTENT
            ),
            current_value=current_number,
            bundle_derived_value=candidate.lesson_information.lesson_number,
        ),
        CanonicalFieldComparison(
            field="lesson_sequence",
            status=ComparisonStatus.CURRENT_ONLY_CONTENT,
            current_value=current_blocks,
            bundle_derived_value=[
                value.title for value in candidate.lesson_blocks
            ],
            notes=[
                "The candidate preserves assignment order only; verified "
                "internal Teacher Guide sequencing is not yet modeled."
            ],
        ),
        CanonicalFieldComparison(
            field="reading_assignments",
            status=ComparisonStatus.EQUIVALENT_SOURCE_CONTENT,
            current_value=current_readings,
            bundle_derived_value=candidate_readings,
            notes=[
                "The candidate includes only the verified introduction, main "
                "reading, and homework reading assignments."
            ],
        ),
        CanonicalFieldComparison(
            field="instructional_resources",
            status=(
                ComparisonStatus.EQUIVALENT_SOURCE_CONTENT
                if set(candidate_resources) <= set(current_resources)
                else ComparisonStatus.BUNDLE_ONLY_CONTENT
            ),
            current_value=current_resources,
            bundle_derived_value=candidate_resources,
        ),
        CanonicalFieldComparison(
            field="online_resources",
            status=(
                ComparisonStatus.EQUIVALENT_SOURCE_CONTENT
                if [
                    value
                    for value in current_resources
                    if "online" in value.casefold()
                ]
                else ComparisonStatus.BUNDLE_ONLY_CONTENT
            ),
            current_value=[
                value
                for value in current_resources
                if "online" in value.casefold()
            ],
            bundle_derived_value=candidate_online,
        ),
        CanonicalFieldComparison(
            field="teacher_references",
            status=ComparisonStatus.BUNDLE_ONLY_CONTENT,
            current_value=[],
            bundle_derived_value=candidate_teacher_references,
            notes=[
                "The bridge preserves refrane and story-note assignments as "
                "separate teacher-facing source blocks."
            ],
        ),
        CanonicalFieldComparison(
            field="activity_resources",
            status=(
                ComparisonStatus.EXACT_MATCH
                if current_activity == candidate_activity
                else ComparisonStatus.EQUIVALENT_SOURCE_CONTENT
            ),
            current_value=current_activity,
            bundle_derived_value=candidate_activity,
        ),
        CanonicalFieldComparison(
            field="homework",
            status=(
                ComparisonStatus.EXACT_MATCH
                if [_normalized(value) for value in current_homework]
                == [_normalized(value) for value in candidate_homework]
                else ComparisonStatus.EQUIVALENT_SOURCE_CONTENT
            ),
            current_value=current_homework,
            bundle_derived_value=candidate_homework,
        ),
        CanonicalFieldComparison(
            field="source_provenance",
            status=ComparisonStatus.BUNDLE_ONLY_CONTENT,
            current_value="Legacy canonical provenance",
            bundle_derived_value=(
                "Assignment, resource, segment, coordinate mapping, checksum, "
                "version, and bundle digest provenance"
            ),
        ),
        CanonicalFieldComparison(
            field="unsupported_instructional_fields",
            status=ComparisonStatus.UNSUPPORTED_BY_VERIFIED_SOURCES,
            current_value="May be populated by the production path",
            bundle_derived_value=[],
            notes=UNSUPPORTED_FIELDS,
        ),
        CanonicalFieldComparison(
            field="instructional_enrichment",
            status=ComparisonStatus.POSSIBLE_UNPROVEN_CONTENT,
            current_value=current_generated,
            bundle_derived_value=[],
            notes=[
                "These current fields identify generated guidance or content "
                "not reproduced by the verified-source-only bridge. This is "
                "not an automatic judgment that the content is incorrect."
            ],
        ),
    ]
    comparison = CanonicalBridgeComparison(
        lesson_id=bundle.lesson_id,
        bundle_digest=bundle.bundle_digest,
        current_source_digest=current_source_digest,
        bundle_derived_source_digest=candidate.source_digest,
        comparisons=comparisons,
        bundle_fields_populated=[
            "lesson identity",
            "standards",
            "materials",
            "instructional resource inventory",
            "ordered assignment-backed lesson blocks",
            "reading and homework resource separation",
            "Activity Resources and Student Resources",
            "Online Resources and teacher references",
            "homework directions",
            "source provenance",
        ],
        bundle_fields_missing=[
            "verified duration",
            "learning target transformation",
            "language objective",
            "success criteria",
            "vocabulary interpretation",
            "assessment and exit-ticket content",
            "instructional enrichment",
        ],
        unsupported_instructional_fields=UNSUPPORTED_FIELDS,
        possible_unproven_current_fields=current_generated,
        structural_differences=[
            (
                f"Current lesson has {len(current_blocks)} blocks; "
                f"bundle-derived candidate has {len(candidate.lesson_blocks)} "
                "assignment-backed blocks."
            ),
            (
                f"Current duration is "
                f"{current_duration} minutes; "
                "bundle-derived duration is unavailable and represented as 0."
            ),
            (
                "The cached current artifact does not validate against the "
                "current CanonicalLesson schema when exit_ticket is null."
                if current_payload.get("exit_ticket") is None
                else "The cached current artifact validates its exit-ticket shape."
            ),
            "Candidate contains no slide mappings.",
            "Candidate contains no generated instructional guidance.",
        ],
        comparison_digest="pending",
        schema_version=BRIDGE_SCHEMA_VERSION,
        builder_version=BRIDGE_BUILDER_VERSION,
    )
    return comparison.model_copy(
        update={"comparison_digest": _comparison_digest(comparison)}
    )


def comparison_markdown(
    comparison: CanonicalBridgeComparison,
) -> str:
    lines = [
        "# Canonical Bridge Comparison",
        "",
        f"- Lesson ID: `{comparison.lesson_id}`",
        f"- Bundle digest: `{comparison.bundle_digest}`",
        f"- Comparison digest: `{comparison.comparison_digest}`",
        "",
        "## Field Comparisons",
        "",
    ]
    for value in comparison.comparisons:
        lines.extend([
            f"### {value.field}",
            f"- Status: **{value.status.value}**",
            f"- Current: `{value.current_value}`",
            f"- Bundle-derived: `{value.bundle_derived_value}`",
        ])
        lines.extend(f"- Note: {note}" for note in value.notes)
        lines.append("")
    for title, values in (
        ("Bundle Fields Populated", comparison.bundle_fields_populated),
        ("Bundle Fields Missing", comparison.bundle_fields_missing),
        (
            "Unsupported Instructional Fields",
            comparison.unsupported_instructional_fields,
        ),
        (
            "Possible Unproven Current Fields",
            comparison.possible_unproven_current_fields,
        ),
        ("Structural Differences", comparison.structural_differences),
    ):
        lines.extend([f"## {title}", ""])
        lines.extend(f"- {value}" for value in values)
        if not values:
            lines.append("- None.")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


class CanonicalBridgeService:
    """Write independent candidate and comparison inspection artifacts."""

    def build_candidate(
        self,
        *,
        bundle_path: str | Path,
        current_canonical_path: str | Path,
        output_directory: str | Path,
    ) -> CanonicalBridgeResult:
        bundle = PreparedCurriculumSourceBundle.model_validate_json(
            Path(bundle_path).read_text(encoding="utf-8")
        )
        current_payload = json.loads(
            Path(current_canonical_path).read_text(encoding="utf-8")
        )
        try:
            current: CanonicalLesson | dict[str, Any] = (
                CanonicalLesson.model_validate(current_payload)
            )
        except ValidationError:
            current = current_payload
        candidate = BundleCanonicalBridge().build(bundle)
        comparison = compare_canonical_lessons(
            current, candidate, bundle
        )
        output = Path(output_directory)
        candidate_path = write_json(
            output / "bundle_derived_canonical_lesson.json",
            candidate,
        )
        comparison_json_path = write_json(
            output / "canonical_bridge_comparison.json",
            comparison,
        )
        comparison_markdown_path = (
            output / "canonical_bridge_comparison.md"
        )
        comparison_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_markdown_path.write_text(
            comparison_markdown(comparison),
            encoding="utf-8",
        )
        return CanonicalBridgeResult(
            candidate=candidate,
            comparison=comparison,
            candidate_path=candidate_path,
            comparison_json_path=comparison_json_path,
            comparison_markdown_path=comparison_markdown_path,
        )


__all__ = [
    "BRIDGE_BUILDER_VERSION",
    "BRIDGE_SCHEMA_VERSION",
    "BundleCanonicalBridge",
    "CanonicalBridgeResult",
    "CanonicalBridgeService",
    "UNSUPPORTED_FIELDS",
    "compare_canonical_lessons",
    "comparison_markdown",
    "validate_canonical_bridge_input",
    "validate_bundle_derived_candidate",
]
