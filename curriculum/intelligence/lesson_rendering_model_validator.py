"""Independent fidelity validation for deterministic lesson rendering models."""

from __future__ import annotations

import re

from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.instruction_plan import validate_instruction_plan
from curriculum.intelligence.relationship_graph import validate_relationship_graph
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    ReadinessState,
    ValidationFinding,
)
from schemas.instructional_relationship_graph_schema import (
    InstructionalRelationshipGraph,
    InstructionalRelationshipGraphAudit,
)
from schemas.lesson_rendering_model_schema import (
    AnswerRevealBehavior,
    ContentOrigin,
    LessonRenderingModel,
    LessonRenderingValidationReport,
    RenderingReadinessStatus,
    SlideScope,
    SlideType,
)
from schemas.phase_teacher_support_schema import PhaseTeacherSupportDraft
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)
from schemas.source_grounded_instruction_schema import (
    SourceGroundedInstructionPlan,
)


VALIDATOR_VERSION = "1.0"


def _finding(code: str, message: str, reference: str, *, warning: bool = False):
    return ValidationFinding(
        code=code,
        severity=FindingSeverity.WARNING if warning else FindingSeverity.ERROR,
        message=message,
        reference_id=reference,
    )


def _page_number(value: str) -> int | None:
    value = value.strip().casefold()
    if value.isdigit():
        return int(value)
    roman = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    if not value or any(character not in roman for character in value):
        return None
    total, previous = 0, 0
    for character in reversed(value):
        current = roman[character]
        total += -current if current < previous else current
        previous = max(previous, current)
    return total


def _range_contains(container: str, requested: str) -> bool:
    def endpoints(value: str):
        parts = re.split(r"\s*[–—-]\s*", value.strip(), maxsplit=1)
        numbers = [_page_number(item) for item in parts]
        if any(item is None for item in numbers):
            return None
        return numbers[0], numbers[-1]

    outer, inner = endpoints(container), endpoints(requested)
    return bool(
        outer and inner and outer[0] <= inner[0] <= inner[1] <= outer[1]
    )


def validate_lesson_rendering_model(
    model: LessonRenderingModel,
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    graph: InstructionalRelationshipGraph,
    graph_audit: InstructionalRelationshipGraphAudit,
    *,
    support_drafts: dict[str, PhaseTeacherSupportDraft] | None = None,
) -> LessonRenderingValidationReport:
    findings: list[ValidationFinding] = []
    support_drafts = support_drafts or {}

    def error(code: str, message: str, reference: str = model.lesson_id):
        findings.append(_finding(code, message, reference))

    def warning(code: str, message: str, reference: str = model.lesson_id):
        findings.append(_finding(code, message, reference, warning=True))

    if bundle.readiness_state != ReadinessState.SOURCE_READY:
        error("bundle_not_source_ready", "Prepared bundle is not source_ready.")
    for item in validate_instruction_plan(plan, bundle):
        error("instruction_plan_invalid", item, plan.lesson_id)
    for item in validate_relationship_graph(graph, graph_audit, bundle, plan):
        error("relationship_graph_invalid", item, graph.lesson_id)
    identities = {
        (bundle.curriculum_id, bundle.unit_id, bundle.lesson_id),
        (plan.curriculum_id, plan.unit_id, plan.lesson_id),
        (graph.curriculum_id, graph.unit_id, graph.lesson_id),
        (model.curriculum_id, model.unit_id, model.lesson_id),
    }
    if len(identities) != 1 or graph_audit.lesson_id != model.lesson_id:
        error("artifact_identity_mismatch", "Artifact lesson identities disagree.")
    snapshot = model.source_snapshot
    if snapshot.prepared_bundle_digest != bundle.bundle_digest:
        error("bundle_digest_mismatch", "Rendering model references the wrong bundle digest.")
    if snapshot.instruction_plan_digest != plan.digest:
        error("plan_digest_mismatch", "Rendering model references the wrong plan digest.")
    if snapshot.relationship_graph_digest != graph.graph_digest:
        error("graph_digest_mismatch", "Rendering model references the wrong graph digest.")
    if snapshot.graph_audit_digest != graph_audit.audit_digest:
        error("graph_audit_digest_mismatch", "Rendering model references the wrong graph-audit digest.")

    expected_phase_ids = [phase.id for phase in plan.instructional_phases]
    actual_phase_ids = [phase.phase_id for phase in model.phases]
    if actual_phase_ids != expected_phase_ids:
        error("phase_order_changed", "Rendering phase order differs from the source plan.")
    coverage_ids = [item.phase_id for item in model.phase_coverage]
    if coverage_ids != expected_phase_ids or not all(item.covered for item in model.phase_coverage):
        error("phase_coverage_incomplete", "Every source phase must have one ordered coverage record.")

    slide_ids = [slide.slide_id for slide in model.slides]
    if len(slide_ids) != len(set(slide_ids)):
        error("duplicate_slide_id", "Slide IDs must be unique.")
    numbers = [slide.slide_number for slide in model.slides]
    if numbers != list(range(1, len(model.slides) + 1)):
        error("slide_numbers_invalid", "Slide numbers must be unique, contiguous, and ordered.")
    coverage_slide_ids = [item.slide_id for item in model.slide_coverage]
    if coverage_slide_ids != slide_ids:
        error(
            "slide_coverage_order_invalid",
            "Slide coverage must account for every slide exactly once in order.",
        )
    if len(coverage_slide_ids) != len(set(coverage_slide_ids)):
        error(
            "duplicate_slide_coverage",
            "A slide appears in multiple coverage scopes.",
        )
    valid_phase_ids = set(expected_phase_ids)
    coverage_by_id = {
        item.slide_id: item for item in model.slide_coverage
    }
    for slide in model.slides:
        coverage = coverage_by_id.get(slide.slide_id)
        if coverage is None:
            error("orphaned_slide", "Slide has no coverage scope.", slide.slide_id)
            continue
        if coverage.slide_number != slide.slide_number:
            error(
                "slide_coverage_number_mismatch",
                "Slide coverage number differs from the ordered slide.",
                slide.slide_id,
            )
        if slide.scope != coverage.scope or slide.phase_id != coverage.phase_id:
            error(
                "slide_scope_mismatch",
                "Slide and coverage scope disagree.",
                slide.slide_id,
            )
        if slide.scope == SlideScope.LESSON_STRUCTURE:
            if slide.phase_id is not None:
                error(
                    "lesson_slide_has_phase",
                    "Lesson-level structural slide must not reference a phase.",
                    slide.slide_id,
                )
        elif slide.phase_id not in valid_phase_ids:
            error(
                "slide_phase_invalid",
                "Phase-scoped slide does not reference a valid phase.",
                slide.slide_id,
            )
    phase_counted_ids = [
        slide_id for item in model.phase_coverage for slide_id in item.slide_ids
    ]
    lesson_counted_ids = [
        item.slide_id for item in model.slide_coverage
        if item.scope == SlideScope.LESSON_STRUCTURE
    ]
    if (
        len(phase_counted_ids) + len(lesson_counted_ids)
        != len(model.slides)
        or set(phase_counted_ids).intersection(lesson_counted_ids)
        or set(phase_counted_ids + lesson_counted_ids) != set(slide_ids)
    ):
        error(
            "slide_count_accounting_invalid",
            "Phase-scoped and lesson-level slide counts do not reconstruct the deck.",
        )

    plan_questions = [
        (phase, question)
        for phase in plan.instructional_phases
        for question in phase.questions
    ]
    coverage_question_ids = [item.question_id for item in model.question_coverage]
    expected_question_ids = [question.id for _, question in plan_questions]
    if coverage_question_ids != expected_question_ids:
        error(
            "question_coverage_order_invalid",
            "Question coverage must contain every source question exactly once in source order.",
        )
    if len(coverage_question_ids) != len(set(coverage_question_ids)):
        error("duplicate_question_disposition", "A source question has multiple primary dispositions.")

    slides_by_id = {slide.slide_id: slide for slide in model.slides}
    questions_by_id = {question.id: question for _, question in plan_questions}
    phase_by_question = {
        question.id: phase.id for phase, question in plan_questions
    }
    for index, coverage in enumerate(model.question_coverage, 1):
        question = questions_by_id.get(coverage.question_id)
        if question is None:
            error("unknown_question", "Coverage references an unknown question.", coverage.question_id)
            continue
        if coverage.source_order != index:
            error("question_order_changed", "Question source order was changed.", question.id)
        if coverage.phase_id != phase_by_question[question.id]:
            error("question_phase_mismatch", "Question is linked to the wrong phase.", question.id)
        if len(coverage.slide_ids) != 1 or coverage.slide_ids[0] not in slides_by_id:
            error("question_disposition_invalid", "Question must have one primary slide.", question.id)
            continue
        slide = slides_by_id[coverage.slide_ids[0]]
        if question.id not in slide.question_ids:
            error("question_missing_from_slide", "Question ledger and slide disagree.", question.id)
        visible_values = [
            item.text for item in slide.student_visible_content.statements
            if question.id in item.source_node_ids
            or set(item.source_node_ids) & set(coverage.source_node_ids)
        ]
        if question.question_text not in visible_values:
            error("question_mutated", "Source question text is missing or altered.", question.id)
        expected_answers = [answer.id for answer in question.answers]
        if coverage.source_answer_ids != expected_answers:
            error("wrong_answer_link", "Question is linked to the wrong publisher answer.", question.id)
        if expected_answers:
            if coverage.answer_disposition != AnswerRevealBehavior.SPEAKER_NOTES_ONLY:
                error("answer_behavior_invalid", "Publisher answers must remain in speaker notes.", question.id)
            if not set(expected_answers) <= set(slide.teacher_notes.source_answer_ids):
                error("answer_missing_from_notes", "Publisher answer is absent from speaker notes.", question.id)
            note_answers = {
                item.text for item in slide.teacher_notes.source_answers
                if item.origin == ContentOrigin.PUBLISHER_SOURCE
            }
            if not {answer.exact_text for answer in question.answers} <= note_answers:
                error("answer_mutated", "Publisher answer text is missing or altered.", question.id)
        elif coverage.answer_disposition != AnswerRevealBehavior.NOT_AVAILABLE:
            error("invented_open_answer", "A source question without an answer must remain not_available.", question.id)
        if not coverage.reading_boundary:
            warning(
                "unresolved_reading_boundary",
                "Question has no unambiguous explicit reading boundary.",
                question.id,
            )

    for slide in model.slides:
        if len(slide.question_ids) > 3:
            error("question_capacity_exceeded", "A slide contains more than three questions.", slide.slide_id)
        for item in [
            slide.student_visible_content.title,
            *slide.student_visible_content.directions,
            *slide.student_visible_content.statements,
        ]:
            if item.origin == ContentOrigin.AI_GENERATED_TEACHER_SUPPORT:
                error("ai_support_student_visible", "AI teacher support appears in student-visible content.", slide.slide_id)
        for item in slide.teacher_notes.source_answers:
            if item.origin != ContentOrigin.PUBLISHER_SOURCE:
                error("source_answer_origin_invalid", "A source answer is not publisher-labeled.", slide.slide_id)

    allowed_publisher_text = {
        plan.lesson_title,
        *[value.exact_text for value in plan.objectives],
        *[value.exact_text for value in plan.materials],
        *[value.phase_title for value in plan.instructional_phases],
        *[
            value.day_label for value in plan.instructional_phases
            if value.day_label
        ],
        *[
            action.exact_text
            for phase in plan.instructional_phases
            for action in phase.teacher_actions + phase.student_actions
        ],
        *[
            question.question_text
            for phase in plan.instructional_phases
            for question in phase.questions
        ],
        *[
            answer.exact_text
            for phase in plan.instructional_phases
            for question in phase.questions
            for answer in question.answers
        ],
        *[action.exact_text for action in plan.teacher_preparation],
    }
    for slide in model.slides:
        content_items = [
            slide.student_visible_content.title,
            *slide.student_visible_content.directions,
            *slide.student_visible_content.statements,
            *slide.teacher_notes.publisher_directions,
            *slide.teacher_notes.source_answers,
        ]
        for item in content_items:
            if (
                item.origin == ContentOrigin.PUBLISHER_SOURCE
                and item.text not in allowed_publisher_text
            ):
                error(
                    "unsupported_publisher_content",
                    "Publisher-labeled content is absent from verified source fields.",
                    slide.slide_id,
                )
            if (
                item.origin == ContentOrigin.DETERMINISTIC_STRUCTURE
                and any(mark in item.text for mark in ('"', "“", "”"))
            ):
                error(
                    "unsupported_quotation",
                    "Deterministic structure introduced an unsupported quotation.",
                    slide.slide_id,
                )

    required_assignments = {
        item.assignment_id for item in bundle.required_assignments
    }
    assignment_records = {item.assignment_id: item for item in model.assignment_coverage}
    if not required_assignments <= assignment_records.keys():
        error("required_assignment_omitted", "A required source assignment is omitted.")
    for assignment_id in required_assignments:
        if assignment_id in assignment_records and not assignment_records[assignment_id].covered:
            error("required_assignment_uncovered", "A required assignment is not covered.", assignment_id)
    required_resources = {
        item.resource_id for item in bundle.required_assignments
    }
    resource_records = {item.resource_id: item for item in model.resource_coverage}
    if not required_resources <= resource_records.keys():
        error("required_resource_omitted", "A required source resource is omitted.")
    for resource_id in required_resources:
        if resource_id in resource_records and not resource_records[resource_id].covered:
            error("required_resource_uncovered", "A required resource is not covered.", resource_id)

    assignment_source = {
        item.assignment_id: item
        for item in bundle.required_assignments + bundle.optional_assignments
    }
    phase_source = {phase.id: phase for phase in plan.instructional_phases}
    for phase in model.phases:
        for assignment_id in phase.assignment_ids:
            assignment = assignment_source.get(assignment_id)
            if (
                assignment and assignment.assignment_type == "homework"
                and phase_source[phase.phase_id].phase_type != "homework"
            ):
                error("homework_leakage", "Homework appears before the homework phase.", assignment_id)
    verified_pages = {
        (reference.reference_system, reference.value, assignment.assignment_id)
        for assignment in assignment_source.values()
        for reference in assignment.original_curriculum_references
    }
    verified_pages.update({
        ("source_page", boundary, assignment.assignment_id)
        for item in model.question_coverage
        if item.reading_boundary
        for boundary in [item.reading_boundary.split(":", 1)[1]]
        for assignment in assignment_source.values()
        if any(
            "page" in reference.reference_system
            and _range_contains(reference.value, boundary)
            for reference in assignment.original_curriculum_references
        )
    })
    for slide in model.slides:
        for page in slide.reading_pages:
            if (page.reference_system, page.value, page.assignment_id) not in verified_pages:
                error("unsupported_page", "Slide contains an unsupported page reference.", slide.slide_id)
        if slide.slide_type == SlideType.ASSESSMENT and not plan.assessment_sequence:
            error("unsupported_assessment", "Slide introduces an unsupported assessment.", slide.slide_id)
        allowed_labels = {
            reference.value
            for assignment in assignment_source.values()
            for reference in assignment.original_curriculum_references
            if reference.reference_system == "document_label"
        }
        if not set(slide.activity_book_references) <= allowed_labels:
            error("unsupported_required_activity", "Slide introduces an unsupported activity reference.", slide.slide_id)

    consumed_digests = [
        item.content_digest for item in model.phase_support_manifest
        if item.content_digest
    ]
    if consumed_digests != model.source_snapshot.ordered_support_digests:
        error("support_digest_order_mismatch", "Consumed support digests disagree with the source snapshot.")
    for phase_id, draft in support_drafts.items():
        manifest = next(
            (item for item in model.phase_support_manifest if item.phase_id == phase_id),
            None,
        )
        if not manifest or manifest.draft_digest != draft.digest or manifest.content_digest != draft.content_digest:
            error("consumed_support_digest_mismatch", "Consumed support artifact has a digest mismatch.", phase_id)

    calculated_content = content_digest(model.model_dump(
        mode="json", exclude={"content_digest", "artifact_digest", "warnings", "blockers"}
    ))
    if model.content_digest != calculated_content:
        error("content_digest_invalid", "Rendering-model content digest is invalid.")
    calculated_artifact = content_digest(model.model_dump(
        mode="json", exclude={"artifact_digest"}
    ))
    if model.artifact_digest != calculated_artifact:
        error("artifact_digest_invalid", "Rendering-model artifact digest is invalid.")

    errors = [item for item in findings if item.severity == FindingSeverity.ERROR]
    if errors and model.readiness_status != RenderingReadinessStatus.BLOCKED:
        error("readiness_status_invalid", "A model with blockers must be marked blocked.")
    if not errors and model.readiness_status == RenderingReadinessStatus.BLOCKED:
        error("readiness_status_invalid", "A valid model must not be marked blocked.")
    status = "fail" if any(
        item.severity == FindingSeverity.ERROR for item in findings
    ) else "pass_with_warnings" if findings else "pass"
    report = LessonRenderingValidationReport(
        status=status, lesson_id=model.lesson_id,
        model_digest=model.artifact_digest, findings=findings,
        phase_count=len(model.phases), slide_count=len(model.slides),
        question_count=len(model.question_coverage),
        validation_digest="pending", validator_version=VALIDATOR_VERSION,
    )
    return report.model_copy(update={
        "validation_digest": content_digest(
            report.model_dump(mode="json", exclude={"validation_digest"})
        )
    })


def lesson_rendering_validation_markdown(
    report: LessonRenderingValidationReport,
) -> str:
    lines = [
        "# Lesson Rendering Model Validation", "",
        f"- Status: `{report.status}`",
        f"- Lesson: `{report.lesson_id}`",
        f"- Phases: {report.phase_count}",
        f"- Slides: {report.slide_count}",
        f"- Questions: {report.question_count}", "",
        "## Findings", "",
    ]
    if report.findings:
        lines.extend(
            f"- **{item.severity.value}** `{item.code}`: {item.message}"
            for item in report.findings
        )
    else:
        lines.append("- None.")
    return "\n".join(lines).strip() + "\n"


__all__ = [
    "lesson_rendering_validation_markdown",
    "validate_lesson_rendering_model",
]
