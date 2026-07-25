"""Build and persist a deterministic, source-grounded lesson rendering model."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.lesson_phase_support import (
    SUPPORT_POLICY_VERSION,
    resolve_phase_support,
)
from curriculum.intelligence.snapshot import write_json
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    ReadinessState,
    ValidationFinding,
)
from schemas.instructional_relationship_graph_schema import (
    GraphNodeType,
    GraphRelationshipType,
    InstructionalRelationshipGraph,
    InstructionalRelationshipGraphAudit,
)
from schemas.lesson_rendering_model_schema import (
    AnswerRevealBehavior,
    AssignmentCoverageEntry,
    ContentOrigin,
    LessonRenderingModel,
    OriginText,
    PhaseCoverageEntry,
    PhaseRenderingRecord,
    QuestionCoverageEntry,
    QuestionDisposition,
    ReadingPageReference,
    RenderingReadinessStatus,
    RequiredStatus,
    ResourceCoverageEntry,
    SlideCoverageEntry,
    SlideScope,
    SlideSpecification,
    SlideType,
    SourceSnapshot,
    StudentVisibleContent,
    SupportStatus,
    TeacherNotesContent,
    TimingBasis,
    TimingScope,
    VisualAssetRequirement,
)
from schemas.phase_teacher_support_schema import (
    PhaseTeacherSupportDraft,
    TeacherSupportType,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
    PreparedSourceAssignment,
)
from schemas.source_grounded_instruction_schema import (
    SourceGroundedInstructionPhase,
    SourceGroundedInstructionPlan,
    SourceQuestion,
)


SCHEMA_VERSION = "1.0"
PLANNER_VERSION = "1.0"
SPLITTING_POLICY_VERSION = "1.0"
VOCABULARY_CAPACITY = 4
NORMAL_QUESTION_CAPACITY = 3
LONG_QUESTION_WORDS = 24


def _finding(code: str, severity: FindingSeverity, message: str, ref: str) -> ValidationFinding:
    return ValidationFinding(
        code=code, severity=severity, message=message, reference_id=ref
    )


def _origin(
    text: str,
    origin: ContentOrigin,
    *,
    node_ids: Iterable[str] = (),
    support_ids: Iterable[str] = (),
) -> OriginText:
    return OriginText(
        text=text, origin=origin, source_node_ids=list(node_ids),
        support_item_ids=list(support_ids),
    )


def _graph_indexes(graph: InstructionalRelationshipGraph):
    by_source: dict[str, list] = {}
    for node in graph.nodes:
        if node.source_identifier:
            by_source.setdefault(node.source_identifier, []).append(node)
    answered_by = {
        edge.source_node_id: edge.target_node_id
        for edge in graph.edges
        if edge.relationship_type == GraphRelationshipType.ANSWERED_BY
    }
    by_id = {node.node_id: node for node in graph.nodes}
    return by_source, by_id, answered_by


def _source_nodes(by_source: dict[str, list], source_id: str) -> list[str]:
    return [node.node_id for node in by_source.get(source_id, [])]


def _question_boundary(phase: SourceGroundedInstructionPhase, question: SourceQuestion) -> tuple[str | None, list[str]]:
    """Use only an explicit page marker preceding the exact question text."""
    position = phase.exact_source_text.find(question.question_text)
    if position < 0:
        return None, ["Question text could not be located in the phase source segment."]
    prefix = phase.exact_source_text[:position]
    matches = list(re.finditer(
        r"(?i)\bpages?\s+([ivxlcdm]+|\d+)(?:\s*[–—-]\s*([ivxlcdm]+|\d+))?",
        prefix,
    ))
    if not matches:
        return None, ["No unambiguous explicit reading boundary precedes this question."]
    match = matches[-1]
    start, end = match.group(1), match.group(2)
    value = f"{start}–{end}" if end else start
    return f"source_page:{value}", []


def _assignment_pages(assignment: PreparedSourceAssignment) -> list[ReadingPageReference]:
    return [
        ReadingPageReference(
            reference_system=value.reference_system,
            value=value.value,
            assignment_id=assignment.assignment_id,
        )
        for value in assignment.original_curriculum_references
        if "page" in value.reference_system
    ]


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


def _boundary_assignment(
    assignments: dict[str, PreparedSourceAssignment],
    boundary: str,
) -> PreparedSourceAssignment | None:
    candidates = [
        assignment
        for assignment in assignments.values()
        if any(
            "page" in reference.reference_system
            and _range_contains(reference.value, boundary)
            for reference in assignment.original_curriculum_references
        )
    ]
    return candidates[0] if len(candidates) == 1 else None


def _slide_id(
    lesson_id: str,
    phase_id: str | None,
    slide_type: SlideType,
    anchors: list[str],
    ordinal: int,
) -> str:
    return stable_id(
        "lesson-slide", lesson_id, phase_id or "lesson",
        slide_type.value, *anchors, ordinal,
    )


def _slide_title(slide_type: SlideType, phase_title: str, ordinal: int = 1) -> str:
    if slide_type == SlideType.TEXT_DEPENDENT_QUESTION:
        return "Text-Dependent Questions" if ordinal == 1 else f"Text-Dependent Questions — {ordinal}"
    if slide_type == SlideType.DISCUSSION:
        return "Discussion" if ordinal == 1 else f"Discussion — {ordinal}"
    return phase_title


def _phase_slide_type(phase: SourceGroundedInstructionPhase) -> SlideType:
    return {
        "introduction": SlideType.CONTEXT,
        "reading_preparation": SlideType.READING_DIRECTIONS,
        "reflection": SlideType.SYNTHESIS,
        "homework": SlideType.HOMEWORK,
        "reading": SlideType.READING_CHUNK,
        "discussion": SlideType.DISCUSSION,
    }.get(phase.phase_type, SlideType.CONTEXT)


def _support_notes(
    draft: PhaseTeacherSupportDraft | None,
    *,
    question_ids: set[str] | None = None,
) -> tuple[dict[str, list[OriginText]], list[str], list[str]]:
    values = {
        "facilitation_notes": [], "checks_for_understanding": [],
        "language_supports": [], "differentiation_supports": [],
    }
    support_ids: list[str] = []
    warnings: list[str] = []
    if draft is None:
        return values, support_ids, warnings
    for item in draft.support_sections:
        if question_ids and item.linked_question_ids and not (
            set(item.linked_question_ids) & question_ids
        ):
            continue
        target = {
            TeacherSupportType.CHECKS_FOR_UNDERSTANDING: "checks_for_understanding",
            TeacherSupportType.LANGUAGE_SUPPORTS: "language_supports",
            TeacherSupportType.DIFFERENTIATION_SUPPORTS: "differentiation_supports",
        }.get(item.support_type, "facilitation_notes")
        values[target].append(_origin(
            item.content, ContentOrigin.AI_GENERATED_TEACHER_SUPPORT,
            support_ids=[item.support_id],
        ))
        support_ids.append(item.support_id)
        warnings.extend(item.warnings)
    return values, support_ids, warnings


def _question_groups(
    phase: SourceGroundedInstructionPhase,
) -> list[tuple[list[SourceQuestion], str | None, list[str]]]:
    groups: list[tuple[list[SourceQuestion], str | None, list[str]]] = []
    current: list[SourceQuestion] = []
    current_boundary: str | None = None
    current_warnings: list[str] = []
    for question in phase.questions:
        boundary, warnings = _question_boundary(phase, question)
        long_or_multipart = (
            len(question.question_text.split()) > LONG_QUESTION_WORDS
            or question.question_text.count("?") > 1
        )
        must_split = (
            current
            and (
                boundary != current_boundary
                or len(current) >= NORMAL_QUESTION_CAPACITY
                or long_or_multipart
            )
        )
        if must_split:
            groups.append((current, current_boundary, current_warnings))
            current, current_warnings = [], []
        if long_or_multipart:
            groups.append(([question], boundary, warnings))
            current_boundary = None
            continue
        if not current:
            current_boundary = boundary
        current.append(question)
        current_warnings.extend(warnings)
    if current:
        groups.append((current, current_boundary, current_warnings))
    return groups


def build_lesson_rendering_model(
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    graph: InstructionalRelationshipGraph,
    graph_audit: InstructionalRelationshipGraphAudit,
    *,
    support_manifest,
    support_drafts: dict[str, PhaseTeacherSupportDraft],
) -> LessonRenderingModel:
    """Build a deterministic model without mutating any input artifact."""
    by_source, by_node_id, answered_by = _graph_indexes(graph)
    assignments = {
        item.assignment_id: item
        for item in bundle.required_assignments + bundle.optional_assignments
    }
    manifest_by_phase = {item.phase_id: item for item in support_manifest}
    slides: list[SlideSpecification] = []
    phase_records: list[PhaseRenderingRecord] = []
    phase_coverage: list[PhaseCoverageEntry] = []
    slide_coverage: list[SlideCoverageEntry] = []
    question_coverage: list[QuestionCoverageEntry] = []
    phase_slide_ids: dict[str, list[str]] = {}
    last_day: str | None = None

    def append_slide(
        *,
        phase_id: str | None,
        slide_type: SlideType,
        title: str,
        anchors: list[str],
        ordinal: int,
        visible: StudentVisibleContent,
        notes: TeacherNotesContent | None = None,
        estimated: int | None = None,
        timing_basis: TimingBasis = TimingBasis.NOT_SEPARATELY_SPECIFIED,
        timing_scope: TimingScope = TimingScope.NONE,
        reading_pages: list[ReadingPageReference] | None = None,
        activity_refs: list[str] | None = None,
        question_ids: list[str] | None = None,
        answer_ids: list[str] | None = None,
        support_ids: list[str] | None = None,
        source_node_ids: list[str] | None = None,
        question_behavior: QuestionDisposition | None = None,
        answer_behavior: AnswerRevealBehavior = AnswerRevealBehavior.NOT_AVAILABLE,
        layout: str = "title_and_content",
        visuals: list[VisualAssetRequirement] | None = None,
        warnings: list[str] | None = None,
    ) -> SlideSpecification:
        slide = SlideSpecification(
            slide_id=_slide_id(plan.lesson_id, phase_id, slide_type, anchors, ordinal),
            lesson_id=plan.lesson_id, phase_id=phase_id,
            scope=(
                SlideScope.PHASE
                if phase_id else SlideScope.LESSON_STRUCTURE
            ),
            slide_number=len(slides) + 1, slide_type=slide_type,
            student_visible_content=visible,
            teacher_notes=notes or TeacherNotesContent(),
            estimated_minutes=estimated, timing_basis=timing_basis,
            timing_scope=timing_scope,
            reading_pages=reading_pages or [],
            activity_book_references=activity_refs or [],
            question_ids=question_ids or [], answer_ids=answer_ids or [],
            support_item_ids=support_ids or [],
            source_node_ids=source_node_ids or [],
            question_display_behavior=question_behavior,
            answer_reveal_behavior=answer_behavior,
            layout_hint=layout, visual_asset_requirements=visuals or [],
            warnings=warnings or [],
        )
        slides.append(slide)
        slide_coverage.append(SlideCoverageEntry(
            slide_id=slide.slide_id,
            slide_number=slide.slide_number,
            scope=slide.scope,
            phase_id=phase_id,
            coverage_reference=(
                phase_id if phase_id else f"lesson:{slide.slide_type.value}"
            ),
        ))
        if phase_id:
            phase_slide_ids.setdefault(phase_id, []).append(slide.slide_id)
        return slide

    lesson_nodes = _source_nodes(by_source, plan.lesson_id)
    append_slide(
        phase_id=None, slide_type=SlideType.TITLE, title=plan.lesson_title,
        anchors=lesson_nodes or [plan.lesson_id], ordinal=1,
        visible=StudentVisibleContent(title=_origin(
            plan.lesson_title, ContentOrigin.PUBLISHER_SOURCE,
            node_ids=lesson_nodes,
        )),
        source_node_ids=lesson_nodes, layout="title_hero",
    )
    objective_nodes = [
        node_id for objective in plan.objectives
        for node_id in _source_nodes(by_source, objective.id)
    ]
    append_slide(
        phase_id=None, slide_type=SlideType.OBJECTIVES, title="Lesson Objectives",
        anchors=objective_nodes or ["objectives"], ordinal=1,
        visible=StudentVisibleContent(
            title=_origin("Lesson Objectives", ContentOrigin.DETERMINISTIC_STRUCTURE),
            statements=[
                _origin(
                    objective.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                    node_ids=_source_nodes(by_source, objective.id),
                )
                for objective in plan.objectives
            ],
        ),
        source_node_ids=objective_nodes, layout="objective_agenda",
    )
    append_slide(
        phase_id=None, slide_type=SlideType.AGENDA, title="Agenda",
        anchors=[phase.id for phase in plan.instructional_phases], ordinal=1,
        visible=StudentVisibleContent(
            title=_origin("Agenda", ContentOrigin.DETERMINISTIC_STRUCTURE),
            statements=[
                _origin(phase.phase_title, ContentOrigin.PUBLISHER_SOURCE,
                        node_ids=_source_nodes(by_source, phase.id))
                for phase in plan.instructional_phases
                if phase.phase_type != "teacher_preparation"
            ],
        ),
        source_node_ids=[
            node for phase in plan.instructional_phases
            for node in _source_nodes(by_source, phase.id)
        ], layout="objective_agenda",
    )
    material_nodes = [
        node_id for material in plan.materials
        for node_id in _source_nodes(by_source, material.id)
    ]
    append_slide(
        phase_id=None, slide_type=SlideType.MATERIALS, title="Materials",
        anchors=material_nodes or ["materials"], ordinal=1,
        visible=StudentVisibleContent(
            title=_origin("Materials", ContentOrigin.DETERMINISTIC_STRUCTURE),
            statements=[
                _origin(material.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                        node_ids=_source_nodes(by_source, material.id))
                for material in plan.materials
            ],
        ),
        source_node_ids=material_nodes, layout="simple_directions",
    )

    preparation_notes = [
        _origin(action.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                node_ids=_source_nodes(by_source, action.id))
        for action in plan.teacher_preparation
    ]

    for phase in plan.instructional_phases:
        phase_nodes = _source_nodes(by_source, phase.id)
        manifest = manifest_by_phase[phase.id]
        draft = support_drafts.get(phase.id)
        phase_assignments = list(dict.fromkeys(
            phase.referenced_assignment_ids + phase.activity_assignment_ids
            + phase.homework_assignment_ids
        ))
        phase_resources = list(dict.fromkeys(
            phase.referenced_resource_ids + [
                assignments[item].resource_id
                for item in phase_assignments if item in assignments
            ]
        ))

        if phase.day_label and phase.day_label != last_day:
            append_slide(
                phase_id=phase.id, slide_type=SlideType.DAY_DIVIDER,
                title=phase.day_label, anchors=phase_nodes or [phase.id], ordinal=0,
                visible=StudentVisibleContent(title=_origin(
                    phase.day_label, ContentOrigin.PUBLISHER_SOURCE,
                    node_ids=phase_nodes,
                )),
                source_node_ids=phase_nodes, layout="day_divider",
            )
            last_day = phase.day_label

        if phase.phase_type == "teacher_preparation":
            phase_coverage.append(PhaseCoverageEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                slide_ids=phase_slide_ids.get(phase.id, []),
                disposition="teacher_notes_on_first_instructional_slide",
                covered=True,
            ))
        elif phase.questions:
            groups = _question_groups(phase)
            for group_number, (questions, boundary, boundary_warnings) in enumerate(groups, 1):
                q_ids = [question.id for question in questions]
                q_nodes = [
                    node_id for question in questions
                    for node_id in _source_nodes(by_source, question.id)
                ]
                answers = [answer for question in questions for answer in question.answers]
                answer_ids = [answer.id for answer in answers]
                answer_nodes = [
                    node_id for answer in answers
                    for node_id in _source_nodes(by_source, answer.id)
                ]
                boundary_value = (
                    boundary.split(":", 1)[1] if boundary else None
                )
                reading_assignment = (
                    _boundary_assignment(assignments, boundary_value)
                    if boundary_value else None
                )
                boundary_pages = (
                    [ReadingPageReference(
                        reference_system="source_page",
                        value=boundary_value,
                        assignment_id=reading_assignment.assignment_id,
                    )]
                    if boundary_value and reading_assignment else []
                )
                support_values, support_ids, support_warnings = _support_notes(
                    draft, question_ids=set(q_ids + q_nodes)
                )
                slide_type = (
                    SlideType.DISCUSSION
                    if phase.phase_type == "discussion"
                    else SlideType.TEXT_DEPENDENT_QUESTION
                )
                slide = append_slide(
                    phase_id=phase.id, slide_type=slide_type,
                    title=_slide_title(slide_type, phase.phase_title, group_number),
                    anchors=q_nodes or q_ids, ordinal=group_number,
                    visible=StudentVisibleContent(
                        title=_origin(
                            _slide_title(slide_type, phase.phase_title, group_number),
                            ContentOrigin.DETERMINISTIC_STRUCTURE,
                        ),
                        statements=[
                            _origin(question.question_text, ContentOrigin.PUBLISHER_SOURCE,
                                    node_ids=_source_nodes(by_source, question.id))
                            for question in questions
                        ],
                        visible_question_ids=q_ids,
                        reading_cue=(
                            _origin(
                                f"Pages {boundary_value}",
                                ContentOrigin.DETERMINISTIC_STRUCTURE,
                            )
                            if boundary_value else None
                        ),
                    ),
                    notes=TeacherNotesContent(
                        publisher_directions=[
                            _origin(action.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                                    node_ids=_source_nodes(by_source, action.id))
                            for action in phase.teacher_actions
                        ],
                        source_answer_ids=answer_ids,
                        source_answers=[
                            _origin(answer.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                                    node_ids=_source_nodes(by_source, answer.id))
                            for answer in answers
                        ],
                        facilitation_notes=support_values["facilitation_notes"],
                        checks_for_understanding=support_values["checks_for_understanding"],
                        language_supports=support_values["language_supports"],
                        differentiation_supports=support_values["differentiation_supports"],
                        support_references=support_ids,
                        provenance_references=q_nodes + answer_nodes,
                        warnings=boundary_warnings + support_warnings,
                    ),
                    timing_basis=TimingBasis.SHARED_PHASE_TIME,
                    timing_scope=TimingScope.PHASE,
                    reading_pages=boundary_pages,
                    question_ids=q_ids, answer_ids=answer_ids,
                    support_ids=support_ids, source_node_ids=phase_nodes + q_nodes + answer_nodes,
                    question_behavior=QuestionDisposition.STUDENT_VISIBLE,
                    answer_behavior=(
                        AnswerRevealBehavior.SPEAKER_NOTES_ONLY
                        if answer_ids else AnswerRevealBehavior.NOT_AVAILABLE
                    ),
                    layout="discussion_prompt" if slide_type == SlideType.DISCUSSION else "question_focus",
                    warnings=boundary_warnings,
                )
                for question in questions:
                    source_answer_ids = [answer.id for answer in question.answers]
                    q_node_ids = _source_nodes(by_source, question.id)
                    q_provenance = [
                        provenance for node_id in q_node_ids
                        for provenance in by_node_id[node_id].provenance
                    ]
                    question_coverage.append(QuestionCoverageEntry(
                        question_id=question.id, phase_id=phase.id,
                        source_order=sum(
                            len(item.questions)
                            for item in plan.instructional_phases
                            if item.sequence < phase.sequence
                        ) + phase.questions.index(question) + 1,
                        source_answer_ids=source_answer_ids,
                        primary_disposition=QuestionDisposition.STUDENT_VISIBLE,
                        slide_ids=[slide.slide_id],
                        answer_disposition=(
                            AnswerRevealBehavior.SPEAKER_NOTES_ONLY
                            if source_answer_ids else AnswerRevealBehavior.NOT_AVAILABLE
                        ),
                        reading_boundary=boundary, source_node_ids=q_node_ids,
                        provenance=q_provenance,
                        warnings=(
                            boundary_warnings
                            + (["Publisher did not provide an answer; no answer was invented."]
                               if not source_answer_ids else [])
                        ),
                    ))
            phase_coverage.append(PhaseCoverageEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                slide_ids=phase_slide_ids.get(phase.id, []),
                disposition="student_visible_questions", covered=True,
            ))
        else:
            slide_type = _phase_slide_type(phase)
            activity_refs = [
                ref.value
                for assignment_id in phase_assignments
                if assignment_id in assignments
                for ref in assignments[assignment_id].original_curriculum_references
                if ref.reference_system == "document_label"
            ]
            reading_pages = [
                page
                for assignment_id in phase_assignments
                if assignment_id in assignments
                for page in _assignment_pages(assignments[assignment_id])
            ]
            support_values, support_ids, support_warnings = _support_notes(draft)
            visuals = [
                VisualAssetRequirement(
                    resource_id=assignments[assignment_id].resource_id,
                    assignment_id=assignment_id,
                    description=assignments[assignment_id].title,
                    required=assignments[assignment_id].required_status == "required",
                    warnings=list(assignments[assignment_id].warnings),
                )
                for assignment_id in phase_assignments
                if assignment_id in assignments
                and assignments[assignment_id].assignment_type == "visual_resource"
            ]
            visible_actions = [
                _origin(action.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                        node_ids=_source_nodes(by_source, action.id))
                for action in phase.student_actions
            ]
            slide = append_slide(
                phase_id=phase.id, slide_type=slide_type,
                title=phase.phase_title, anchors=phase_nodes or [phase.id], ordinal=1,
                visible=StudentVisibleContent(
                    title=_origin(phase.phase_title, ContentOrigin.PUBLISHER_SOURCE,
                                  node_ids=phase_nodes),
                    directions=visible_actions,
                    reading_cue=(
                        _origin(
                            "Read " + ", ".join(page.value for page in reading_pages),
                            ContentOrigin.DETERMINISTIC_STRUCTURE,
                        ) if reading_pages else None
                    ),
                ),
                notes=TeacherNotesContent(
                    publisher_directions=(
                        preparation_notes
                        if preparation_notes and phase.sequence == 2 else []
                    ) + [
                        _origin(action.exact_text, ContentOrigin.PUBLISHER_SOURCE,
                                node_ids=_source_nodes(by_source, action.id))
                        for action in phase.teacher_actions
                    ],
                    facilitation_notes=support_values["facilitation_notes"],
                    checks_for_understanding=support_values["checks_for_understanding"],
                    language_supports=support_values["language_supports"],
                    differentiation_supports=support_values["differentiation_supports"],
                    support_references=support_ids,
                    provenance_references=phase_nodes,
                    warnings=support_warnings,
                ),
                estimated=phase.duration_minutes,
                timing_basis=(
                    TimingBasis.PUBLISHER_EXPLICIT
                    if phase.duration_minutes is not None
                    else TimingBasis.NOT_SEPARATELY_SPECIFIED
                ),
                timing_scope=(
                    TimingScope.PHASE if phase.duration_minutes is not None
                    else TimingScope.NONE
                ),
                reading_pages=reading_pages, activity_refs=activity_refs,
                support_ids=support_ids, source_node_ids=phase_nodes,
                answer_behavior=(
                    AnswerRevealBehavior.SOURCE_ACTIVITY_RESOURCE
                    if activity_refs else AnswerRevealBehavior.NOT_AVAILABLE
                ),
                layout=(
                    "homework" if slide_type == SlideType.HOMEWORK
                    else "reading_checkpoint" if slide_type == SlideType.READING_DIRECTIONS
                    else "simple_directions"
                ),
                visuals=visuals,
                warnings=[
                    *phase.warnings,
                    *(["A neutral visual placeholder is required until the approved asset is rendered."]
                      if visuals else []),
                ],
            )
            phase_coverage.append(PhaseCoverageEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                slide_ids=phase_slide_ids.get(phase.id, []),
                disposition="student_visible_phase",
                covered=True,
            ))

        phase_records.append(PhaseRenderingRecord(
            phase_id=phase.id, sequence=phase.sequence, title=phase.phase_title,
            phase_type=phase.phase_type, day_label=phase.day_label,
            source_duration_minutes=phase.duration_minutes,
            required_status=RequiredStatus.REQUIRED,
            support_requirement=manifest.requirement,
            support_status=manifest.status,
            support_draft_digest=manifest.draft_digest,
            assignment_ids=phase_assignments, resource_ids=phase_resources,
            question_ids=[question.id for question in phase.questions],
            slide_ids=phase_slide_ids.get(phase.id, []),
            source_node_ids=phase_nodes,
            provenance=[
                provenance for node_id in phase_nodes
                for provenance in by_node_id[node_id].provenance
            ],
            warnings=list(phase.warnings) + list(manifest.warnings),
            blockers=list(manifest.blockers),
        ))

    assignment_coverage = []
    for assignment in bundle.required_assignments + bundle.optional_assignments:
        phase_ids = [
            phase.id for phase in plan.instructional_phases
            if assignment.assignment_id in (
                phase.referenced_assignment_ids + phase.activity_assignment_ids
                + phase.homework_assignment_ids
            )
        ]
        if assignment.assignment_type == "defines_lesson" and not phase_ids:
            phase_ids = [phase.id for phase in plan.instructional_phases]
        slide_ids = [
            slide_id for phase_id in phase_ids
            for slide_id in phase_slide_ids.get(phase_id, [])
        ]
        covered = assignment.available and (
            bool(phase_ids)
            or assignment.required_status == "required"
            and assignment.assignment_type in {
                "background_reading", "teacher_reference", "license_reference"
            }
        )
        assignment_coverage.append(AssignmentCoverageEntry(
            assignment_id=assignment.assignment_id,
            required_status=RequiredStatus(assignment.required_status),
            phase_ids=phase_ids, slide_ids=list(dict.fromkeys(slide_ids)),
            disposition=(
                "homework" if assignment.assignment_type == "homework"
                else "source_basis" if assignment.assignment_type == "defines_lesson"
                else "verified_teacher_reference"
                if not phase_ids and covered
                else "instructional_resource"
            ),
            covered=covered,
        ))

    resource_coverage = []
    for resource in bundle.resource_summaries:
        resource_assignments = [
            item for item in assignment_coverage
            if assignments[item.assignment_id].resource_id == resource.resource_id
        ]
        phase_ids = list(dict.fromkeys(
            phase_id for item in resource_assignments for phase_id in item.phase_ids
        ))
        slide_ids = list(dict.fromkeys(
            slide_id for item in resource_assignments for slide_id in item.slide_ids
        ))
        required = any(item.required_status == RequiredStatus.REQUIRED for item in resource_assignments)
        resource_coverage.append(ResourceCoverageEntry(
            resource_id=resource.resource_id, required=required,
            assignment_ids=[item.assignment_id for item in resource_assignments],
            phase_ids=phase_ids, slide_ids=slide_ids,
            disposition="verified_instructional_resource",
            covered=bool(resource_assignments) and resource.source_available,
        ))

    timing_warnings = [
        value for value in plan.warnings
        if "timing" in value.code or "minute" in value.message.casefold()
    ]
    warnings = list(plan.warnings) + [
        _finding(
            (
                "optional_phase_support_unavailable"
                if item.status == SupportStatus.OPTIONAL_UNAVAILABLE
                else "phase_support_warning"
            ),
            FindingSeverity.WARNING,
            warning, item.phase_id,
        )
        for item in support_manifest
        for warning in item.warnings
    ]
    blockers = list(plan.blockers)
    if bundle.readiness_state != ReadinessState.SOURCE_READY:
        blockers.append(_finding(
            "bundle_not_source_ready", FindingSeverity.ERROR,
            "Prepared curriculum bundle is not source_ready.", plan.lesson_id,
        ))
    ordered_support_digests = [
        item.content_digest for item in support_manifest
        if item.status == SupportStatus.VALID_CACHE and item.content_digest
    ]
    snapshot = SourceSnapshot(
        prepared_bundle_digest=bundle.bundle_digest,
        instruction_plan_digest=plan.digest,
        relationship_graph_digest=graph.graph_digest,
        graph_audit_digest=graph_audit.audit_digest,
        ordered_support_digests=ordered_support_digests,
    )
    provisional = LessonRenderingModel(
        curriculum_id=plan.curriculum_id, unit_id=plan.unit_id,
        lesson_id=plan.lesson_id, lesson_title=plan.lesson_title,
        schema_version=SCHEMA_VERSION, planner_version=PLANNER_VERSION,
        splitting_policy_version=SPLITTING_POLICY_VERSION,
        support_policy_version=SUPPORT_POLICY_VERSION,
        source_snapshot=snapshot,
        declared_duration_minutes=plan.total_duration_minutes,
        explicit_phase_duration_minutes=sum(
            phase.duration_minutes or 0 for phase in plan.instructional_phases
        ),
        timing_warnings=timing_warnings, phases=phase_records, slides=slides,
        phase_support_manifest=support_manifest,
        slide_coverage=slide_coverage,
        phase_coverage=phase_coverage, question_coverage=question_coverage,
        assignment_coverage=assignment_coverage,
        resource_coverage=resource_coverage,
        provenance=[
            provenance for node in graph.nodes
            if node.node_type == GraphNodeType.LESSON
            for provenance in node.provenance
        ],
        warnings=warnings, blockers=blockers,
        readiness_status=(
            RenderingReadinessStatus.BLOCKED if blockers
            else RenderingReadinessStatus.SOURCE_READY_WITH_SUPPORT
            if ordered_support_digests
            else RenderingReadinessStatus.SOURCE_READY
        ),
        content_digest="pending", artifact_digest="pending",
    )
    content_payload = provisional.model_dump(
        mode="json", exclude={"content_digest", "artifact_digest", "warnings", "blockers"}
    )
    provisional = provisional.model_copy(update={
        "content_digest": content_digest(content_payload)
    })
    artifact_payload = provisional.model_dump(
        mode="json", exclude={"artifact_digest"}
    )
    return provisional.model_copy(update={
        "artifact_digest": content_digest(artifact_payload)
    })


def lesson_rendering_model_markdown(
    model: LessonRenderingModel,
    *,
    validation_status: str | None = None,
) -> str:
    lines = [
        f"# Lesson Rendering Model: {model.lesson_title}", "",
        f"- Lesson: `{model.lesson_id}`",
        f"- Readiness: `{model.readiness_status.value}`",
        f"- Slides: {len(model.slides)}",
        f"- Declared duration: {model.declared_duration_minutes}",
        f"- Explicit phase duration: {model.explicit_phase_duration_minutes}",
        f"- Validation: `{validation_status or 'not_run'}`", "",
        "## Source Digests", "",
        f"- Bundle: `{model.source_snapshot.prepared_bundle_digest}`",
        f"- Instruction plan: `{model.source_snapshot.instruction_plan_digest}`",
        f"- Relationship graph: `{model.source_snapshot.relationship_graph_digest}`",
        f"- Graph audit: `{model.source_snapshot.graph_audit_digest}`", "",
        "## Warnings", "",
    ]
    lines.extend(
        f"- `{value.code}`: {value.message}" for value in model.warnings
    )
    if not model.warnings:
        lines.append("- None.")
    lines.extend(["", "## Blockers", ""])
    lines.extend(
        f"- `{value.code}`: {value.message}" for value in model.blockers
    )
    if not model.blockers:
        lines.append("- None.")
    lines.extend(["", "## Phase Support Manifest", ""])
    for item in model.phase_support_manifest:
        lines.append(
            f"- Phase {item.phase_sequence}: `{item.requirement.value}` / "
            f"`{item.status.value}` — {item.reason}"
        )
    lines.extend(["", "## Ordered Slides", ""])
    for slide in model.slides:
        view, notes = slide.student_visible_content, slide.teacher_notes
        lines.extend([
            f"### {slide.slide_number}. {view.title.text}", "",
            f"- Type: `{slide.slide_type.value}`",
            f"- Phase: `{slide.phase_id or 'lesson'}`",
            f"- Scope: `{slide.scope.value}`",
            f"- Timing: `{slide.estimated_minutes}` / `{slide.timing_basis.value}`",
            f"- Layout: `{slide.layout_hint}`",
            f"- Question IDs: {', '.join(slide.question_ids) or 'None'}",
            f"- Answer IDs: {', '.join(slide.answer_ids) or 'None'}",
            f"- Source node IDs: {', '.join(slide.source_node_ids) or 'None'}",
            "", "**Student-visible content**", "",
        ])
        for item in [*view.directions, *view.statements]:
            lines.append(f"- [{item.origin.value}] {item.text}")
        if view.reading_cue:
            lines.append(f"- [{view.reading_cue.origin.value}] {view.reading_cue.text}")
        if not (view.directions or view.statements or view.reading_cue):
            lines.append("- Title only.")
        lines.extend(["", "**Teacher notes summary**", ""])
        lines.append(f"- Publisher directions: {len(notes.publisher_directions)}")
        lines.append(f"- Source answers: {len(notes.source_answers)}")
        lines.append(f"- AI support items: {len(slide.support_item_ids)}")
        for warning in slide.warnings:
            lines.append(f"- Warning: {warning}")
        lines.append("")
    lines.extend(["## Question Coverage Ledger", ""])
    for item in model.question_coverage:
        lines.append(
            f"- {item.source_order}. `{item.question_id}` → "
            f"{', '.join(item.slide_ids)}; answer `{item.answer_disposition.value}`"
        )
    lines.extend(["", "## Assignment Coverage Ledger", ""])
    for item in model.assignment_coverage:
        lines.append(f"- `{item.assignment_id}`: covered={item.covered}; {item.disposition}")
    lines.extend(["", "## Resource Coverage Ledger", ""])
    for item in model.resource_coverage:
        lines.append(f"- `{item.resource_id}`: covered={item.covered}; {item.disposition}")
    return "\n".join(lines).strip() + "\n"


class LessonRenderingModelService:
    """Load verified artifacts, resolve optional support, build, validate, cache."""

    def generate(
        self,
        *,
        bundle_path: str | Path,
        instruction_plan_path: str | Path,
        relationship_graph_path: str | Path,
        relationship_graph_audit_path: str | Path,
        output_directory: str | Path,
        phase_support_directory: str | Path | None = None,
        expected_support_identities=None,
    ):
        from curriculum.intelligence.lesson_rendering_model_validator import (
            lesson_rendering_validation_markdown,
            validate_lesson_rendering_model,
        )

        bundle = PreparedCurriculumSourceBundle.model_validate_json(
            Path(bundle_path).read_text(encoding="utf-8")
        )
        plan = SourceGroundedInstructionPlan.model_validate_json(
            Path(instruction_plan_path).read_text(encoding="utf-8")
        )
        graph = InstructionalRelationshipGraph.model_validate_json(
            Path(relationship_graph_path).read_text(encoding="utf-8")
        )
        audit = InstructionalRelationshipGraphAudit.model_validate_json(
            Path(relationship_graph_audit_path).read_text(encoding="utf-8")
        )
        manifest, drafts = resolve_phase_support(
            bundle, plan, graph, audit,
            cache_directory=phase_support_directory,
            expected_support_identities=expected_support_identities,
        )
        expected = build_lesson_rendering_model(
            bundle, plan, graph, audit,
            support_manifest=manifest, support_drafts=drafts,
        )
        target = Path(output_directory)
        target.mkdir(parents=True, exist_ok=True)
        model_path = target / "lesson_rendering_model.json"
        reused = False
        if model_path.is_file():
            try:
                saved = LessonRenderingModel.model_validate_json(
                    model_path.read_text(encoding="utf-8")
                )
                report = validate_lesson_rendering_model(
                    saved, bundle, plan, graph, audit, support_drafts=drafts
                )
                if (
                    saved.artifact_digest == expected.artifact_digest
                    and report.status != "fail"
                ):
                    expected = saved
                    reused = True
            except Exception:
                pass
        report = validate_lesson_rendering_model(
            expected, bundle, plan, graph, audit, support_drafts=drafts
        )
        write_json(target / "lesson_phase_support_manifest.json", manifest)
        write_json(model_path, expected)
        write_json(target / "lesson_rendering_model_validation.json", report)
        (target / "lesson_rendering_model.md").write_text(
            lesson_rendering_model_markdown(
                expected, validation_status=report.status
            ), encoding="utf-8",
        )
        (target / "lesson_rendering_model_validation.md").write_text(
            lesson_rendering_validation_markdown(report), encoding="utf-8"
        )
        return expected, report, reused


__all__ = [
    "LessonRenderingModelService", "build_lesson_rendering_model",
    "lesson_rendering_model_markdown",
]
