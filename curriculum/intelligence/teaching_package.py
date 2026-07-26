"""Deterministic structured teaching-package construction and validation."""

from __future__ import annotations

import re
from pathlib import Path

from curriculum.intelligence.ids import content_digest, stable_id
from schemas.lesson_intelligence_package_schema import (
    ClassifiedContent,
    ContentClassification,
    LessonIntelligencePackage,
    PackageCitation,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)
from schemas.teaching_package_schema import (
    ContentOrigin,
    GroundedText,
    LessonDashboard,
    ReviewStatus,
    StudentSlide,
    StructuredTeachingPackage,
    TeachingAgendaItem,
    TeachingObjective,
    TeachingPackageFinding,
    TeachingPackageValidationReport,
    TeachingQuestion,
    TeachingSourceReference,
    TeachingStep,
    TeachingVocabulary,
    TEACHING_PACKAGE_SCHEMA_VERSION,
    ValidationSeverity,
)


TEACHING_PACKAGE_BUILDER_VERSION = "1.1"
ADAPTATION_PROMPT_VERSION = "teaching-adaptation-v1"
DETERMINISTIC_MODEL_VERSION = "deterministic-preservation-v1"
TEACHING_PACKAGE_VALIDATOR_VERSION = "1.2"

COGNITIVE_DEMANDS = (
    "identify", "describe", "explain", "compare", "contrast", "analyze",
    "evaluate", "argue", "cite", "determine", "write", "discuss", "read",
    "listen", "speak", "support",
)
CONDITION_MARKERS = (
    "evidence", "in writing", "with a partner", "during discussion",
    "across the text", "student reader", "activity page", "complete sentence",
)


def _refs(
    citations: list[PackageCitation],
) -> list[TeachingSourceReference]:
    seen = set()
    values = []
    for citation in citations:
        key = (
            citation.resource_id,
            citation.stable_source_id,
            citation.pdf_page_number,
        )
        if key in seen:
            continue
        seen.add(key)
        values.append(TeachingSourceReference(
            resource_id=citation.resource_id,
            source_document=citation.source_document,
            stable_source_id=citation.stable_source_id,
            pdf_page_number=citation.pdf_page_number,
            display_page_number=citation.display_page_number,
            printed_page=citation.printed_page,
        ))
    return values


def _demands(text: str) -> list[str]:
    normalized = text.casefold()
    return [
        value for value in COGNITIVE_DEMANDS
        if re.search(rf"\b{re.escape(value)}\w*\b", normalized)
    ]


def _conditions(text: str) -> list[str]:
    normalized = text.casefold()
    return [value for value in CONDITION_MARKERS if value in normalized]


def _origin(content: ClassifiedContent) -> ContentOrigin:
    return {
        ContentClassification.PUBLISHER_SOURCE:
            ContentOrigin.EXACT_PUBLISHER,
        ContentClassification.TEACHEROS_INTERPRETATION:
            ContentOrigin.MODEL_ANALYSIS,
        ContentClassification.TEACHEROS_AI_SUPPORT:
            ContentOrigin.MODEL_ANALYSIS,
        ContentClassification.SOURCE_LIMITATION:
            ContentOrigin.UNAVAILABLE,
    }[content.classification]


def _content(
    identifier: str,
    content: ClassifiedContent,
    *,
    transformation: str | None = None,
) -> GroundedText:
    origin = _origin(content)
    return GroundedText(
        id=identifier,
        text=content.text,
        origin=origin,
        source_references=_refs(content.citations),
        transformation_type=transformation or origin.value,
        cognitive_demands=_demands(content.text),
        required_conditions=_conditions(content.text),
        confidence=1 if origin == ContentOrigin.EXACT_PUBLISHER else .9,
        review_status=(
            ReviewStatus.VERIFIED
            if origin == ContentOrigin.EXACT_PUBLISHER
            else (
                ReviewStatus.REVIEW_RECOMMENDED
                if origin == ContentOrigin.MODEL_ANALYSIS
                else ReviewStatus.NOT_APPLICABLE
            )
        ),
    )


def _generated(identifier: str, text: str) -> GroundedText:
    return GroundedText(
        id=identifier,
        text=text,
        origin=ContentOrigin.MODEL_ANALYSIS,
        transformation_type="deterministic_instructional_guidance",
        cognitive_demands=_demands(text),
        required_conditions=_conditions(text),
        confidence=.85,
        review_status=ReviewStatus.REVIEW_RECOMMENDED,
    )


def _unavailable(identifier: str, text: str) -> GroundedText:
    return GroundedText(
        id=identifier,
        text=text,
        origin=ContentOrigin.UNAVAILABLE,
        transformation_type="source_unavailable",
        confidence=1,
        review_status=ReviewStatus.NOT_APPLICABLE,
    )


def _student_adaptation(
    identifier: str,
    official: GroundedText,
    adapted: ClassifiedContent | None = None,
) -> GroundedText:
    text = adapted.text if adapted else official.text
    references = (
        _refs(adapted.citations) if adapted and adapted.citations
        else official.source_references
    )
    return GroundedText(
        id=identifier,
        text=text,
        origin=ContentOrigin.STUDENT_ADAPTATION,
        source_references=references,
        transformation_type="meaning_preserving_language_simplification",
        cognitive_demands=_demands(text),
        required_conditions=_conditions(text),
        confidence=.95 if text == official.text else .85,
        review_status=(
            ReviewStatus.VERIFIED
            if text == official.text else ReviewStatus.REVIEW_RECOMMENDED
        ),
    )


def _package_digest(package: StructuredTeachingPackage) -> str:
    return content_digest(package.model_dump(
        mode="json", exclude={"package_digest", "validation"}
    ))


def _meaning_preserved(
    official: GroundedText,
    adapted: GroundedText,
) -> bool:
    return (
        set(official.cognitive_demands) == set(adapted.cognitive_demands)
        and set(official.required_conditions)
        == set(adapted.required_conditions)
    )


class TeachingPackageValidator:
    """Validate synchronization and prevent curriculum-fidelity regressions."""

    def validate(
        self,
        package: StructuredTeachingPackage,
        intelligence: LessonIntelligencePackage,
    ) -> TeachingPackageValidationReport:
        findings: list[TeachingPackageFinding] = []

        def finding(
            code: str,
            severity: ValidationSeverity,
            message: str,
            reference_id: str | None = None,
        ) -> None:
            findings.append(TeachingPackageFinding(
                code=code,
                severity=severity,
                message=message,
                reference_id=reference_id,
            ))

        if [item.official_title.text for item in package.agenda] != [
            phase.title for phase in intelligence.phases
        ]:
            finding(
                "agenda_order_or_coverage_changed",
                ValidationSeverity.ERROR,
                "Teaching package agenda differs from Lesson Intelligence.",
            )
        for item, phase in zip(package.agenda, intelligence.phases):
            if item.duration_minutes != phase.duration_minutes:
                finding(
                    "agenda_timing_changed",
                    ValidationSeverity.ERROR,
                    f"Timing changed for {item.official_title.text}.",
                    item.agenda_item_id,
                )
            if not item.teaching_step_ids:
                finding(
                    "agenda_step_missing",
                    ValidationSeverity.ERROR,
                    "Agenda item has no teaching step.",
                    item.agenda_item_id,
                )
            if not item.teacher_only and not item.slide_ids:
                finding(
                    "agenda_slide_missing",
                    ValidationSeverity.ERROR,
                    "Student-facing agenda item has no slide.",
                    item.agenda_item_id,
                )
        official_by_id = {
            value.objective_id: value for value in intelligence.objectives
        }
        for objective in package.objectives:
            source = official_by_id.get(objective.objective_id)
            if (
                source is None
                or objective.official.text
                != source.publisher_objective.text
            ):
                finding(
                    "official_objective_changed",
                    ValidationSeverity.ERROR,
                    "Official objective is missing or changed.",
                    objective.objective_id,
                )
            if not _meaning_preserved(
                objective.official, objective.student_friendly
            ):
                finding(
                    "objective_meaning_changed",
                    ValidationSeverity.ERROR,
                    "Student-friendly objective removed a cognitive demand "
                    "or required condition.",
                    objective.objective_id,
                )
        if [value.question_id for value in package.questions] != [
            value.question_id for value in intelligence.questions
        ]:
            finding(
                "required_questions_changed",
                ValidationSeverity.ERROR,
                "Required question identity or order changed.",
            )
        slide_ids = {slide.slide_id for slide in package.student_slides}
        for question in package.questions:
            if not question.slide_ids:
                finding(
                    "question_slide_missing",
                    ValidationSeverity.ERROR,
                    "Required question is not represented on a student slide.",
                    question.question_id,
                )
            if not set(question.slide_ids) <= slide_ids:
                finding(
                    "question_slide_reference_invalid",
                    ValidationSeverity.ERROR,
                    "Question points to an unknown slide.",
                    question.question_id,
                )
        slide_types = {slide.slide_type for slide in package.student_slides}
        for required in ("title", "agenda", "objectives"):
            if required not in slide_types:
                finding(
                    "required_structural_slide_missing",
                    ValidationSeverity.ERROR,
                    f"Required {required} slide is missing.",
                )
        answers = [
            question.expected_answer.text.casefold()
            for question in package.questions
            if question.answer_visibility == "teacher_only"
            and question.expected_answer.origin != ContentOrigin.UNAVAILABLE
            and len(question.expected_answer.text) >= 12
        ]
        for slide in package.student_slides:
            visible = " ".join(
                slide.visible_student_content
                + ([slide.student_prompt] if slide.student_prompt else [])
            ).casefold()
            if any(answer in visible for answer in answers):
                finding(
                    "student_visible_answer",
                    ValidationSeverity.ERROR,
                    "Student-visible slide contains expected-answer text.",
                    slide.slide_id,
                )
            if re.search(
                r"(bundle_digest|source_hash|api[_ -]?key|internal provenance)",
                visible,
            ):
                finding(
                    "student_visible_internal_metadata",
                    ValidationSeverity.ERROR,
                    "Student-visible slide contains internal metadata.",
                    slide.slide_id,
                )
            if not slide.visible_student_content and not slide.student_prompt:
                finding(
                    "empty_slide",
                    ValidationSeverity.ERROR,
                    "Slide has no student-visible content.",
                    slide.slide_id,
                )
            word_count = len(visible.split())
            if word_count > 90:
                finding(
                    "dense_slide",
                    ValidationSeverity.WARNING,
                    f"Slide contains {word_count} visible words.",
                    slide.slide_id,
                )
            if slide.page_reference and (
                slide.page_reference
                not in package.dashboard.student_reader_pages
            ):
                finding(
                    "unsupported_reader_page_reference",
                    ValidationSeverity.ERROR,
                    "Slide uses a Reader page reference not present in the "
                    "prepared source package.",
                    slide.slide_id,
                )
            if slide.activity_reference and (
                slide.activity_reference
                not in package.dashboard.activity_book_pages
            ):
                finding(
                    "unsupported_activity_reference",
                    ValidationSeverity.ERROR,
                    "Slide uses an Activity Book reference not present in "
                    "the prepared source package.",
                    slide.slide_id,
                )
        if not package.themes:
            finding(
                "theme_analysis_unavailable",
                ValidationSeverity.WARNING,
                "No source-supported theme analysis was available.",
            )
        if not package.literary_analysis:
            finding(
                "literary_analysis_unavailable",
                ValidationSeverity.WARNING,
                "No source-supported literary analysis was available.",
            )
        if package.package_digest != _package_digest(package):
            finding(
                "package_digest_invalid",
                ValidationSeverity.ERROR,
                "Teaching package digest does not match its content.",
            )
        def citation_keys(value: object):
            if isinstance(value, dict):
                if {
                    "resource_id", "stable_source_id", "pdf_page_number"
                } <= set(value):
                    yield (
                        value["resource_id"],
                        value["stable_source_id"],
                        value["pdf_page_number"],
                    )
                for child in value.values():
                    yield from citation_keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from citation_keys(child)

        approved_sources = set(citation_keys(
            intelligence.model_dump(mode="json")
        ))

        def source_references(value: object):
            if isinstance(value, dict):
                references = value.get("source_references")
                if isinstance(references, list):
                    for reference in references:
                        if isinstance(reference, dict):
                            yield reference
                for child in value.values():
                    yield from source_references(child)
            elif isinstance(value, list):
                for child in value:
                    yield from source_references(child)

        for reference in source_references(
            package.model_dump(mode="json", exclude={"provenance"})
        ):
            key = (
                reference.get("resource_id"),
                reference.get("stable_source_id"),
                reference.get("pdf_page_number"),
            )
            if key not in approved_sources:
                finding(
                    "unsupported_source_reference",
                    ValidationSeverity.ERROR,
                    "Generated content cites a source location outside the "
                    "approved provenance index.",
                    reference.get("stable_source_id"),
                )
        status = (
            "fail"
            if any(value.severity == ValidationSeverity.ERROR
                   for value in findings)
            else (
                "pass_with_warnings"
                if any(value.severity == ValidationSeverity.WARNING
                       for value in findings)
                else "pass"
            )
        )
        return TeachingPackageValidationReport(
            status=status,
            findings=findings,
            package_digest=package.package_digest,
            validator_version=TEACHING_PACKAGE_VALIDATOR_VERSION,
        )


class TeachingPackageBuilder:
    """Build one synchronized package without model or renderer calls."""

    def build(
        self,
        *,
        bundle: PreparedCurriculumSourceBundle,
        intelligence: LessonIntelligencePackage,
    ) -> StructuredTeachingPackage:
        if bundle.bundle_digest != intelligence.bundle_digest:
            raise ValueError(
                "Lesson Intelligence does not match the prepared bundle."
            )
        phase_by_id = {phase.phase_id: phase for phase in intelligence.phases}
        question_phase = {
            question.question_id: question.phase_id
            for question in intelligence.questions
        }
        agenda = []
        steps = []
        for phase in intelligence.phases:
            agenda_id = stable_id(
                "teaching-agenda", bundle.lesson_id, phase.phase_id
            )
            refs = _refs(phase.source_pages)
            official_title = GroundedText(
                id=stable_id("official-agenda-title", agenda_id),
                text=phase.title,
                origin=ContentOrigin.EXACT_PUBLISHER,
                source_references=refs,
                transformation_type="exact_publisher_content",
                cognitive_demands=_demands(phase.title),
                required_conditions=_conditions(phase.title),
                confidence=1,
                review_status=ReviewStatus.VERIFIED,
            )
            friendly_title = _student_adaptation(
                stable_id("student-agenda-title", agenda_id),
                official_title,
            )
            action_values = phase.teacher_actions + phase.student_actions
            phase_text = " ".join(
                value.text for value in action_values
            ).casefold()
            reader_references = [
                value.page_reference
                for value in intelligence.reading_guides
                if (
                    value.title.casefold() in phase_text
                    or value.page_reference.casefold() in phase_text
                    or (
                        "read the story" in phase.title.casefold()
                        and value is intelligence.reading_guides[-1]
                    )
                )
            ]
            activity_references = [
                value.name
                for value in intelligence.activities
                if (
                    value.name.casefold() in phase_text
                    or value.name.casefold().replace(
                        "activity resource", "activity page"
                    ) in phase_text
                )
            ]
            if action_values:
                official_description = _content(
                    stable_id("official-agenda-description", agenda_id),
                    action_values[0],
                )
            else:
                official_description = official_title.model_copy(update={
                    "id": stable_id("official-agenda-description", agenda_id)
                })
            friendly_description = _student_adaptation(
                stable_id("student-agenda-description", agenda_id),
                official_description,
            )
            step_id = stable_id("teaching-step", agenda_id)
            question_ids = [
                value.question_id for value in intelligence.questions
                if value.phase_id == phase.phase_id
            ]
            agenda.append(TeachingAgendaItem(
                agenda_item_id=agenda_id,
                official_order=phase.sequence,
                official_title=official_title,
                student_friendly_title=friendly_title,
                official_description=official_description,
                student_friendly_description=friendly_description,
                duration_minutes=phase.duration_minutes,
                materials=phase.materials,
                teacher_guide_references=refs,
                student_reader_references=reader_references,
                activity_book_references=activity_references,
                required=True,
                teacher_only=False,
                teaching_step_ids=[step_id],
                question_ids=question_ids,
                adaptation_classification=ContentOrigin.STUDENT_ADAPTATION,
                review_status=ReviewStatus.VERIFIED,
            ))
            steps.append(TeachingStep(
                teaching_step_id=step_id,
                agenda_item_id=agenda_id,
                official_title=phase.title,
                student_friendly_title=friendly_title.text,
                duration_minutes=phase.duration_minutes,
                instructional_purpose=_content(
                    stable_id("step-purpose", step_id), phase.purpose
                ),
                materials=phase.materials,
                teacher_actions=[
                    _content(stable_id("teacher-action", step_id, index), value)
                    for index, value in enumerate(phase.teacher_actions, 1)
                ],
                student_actions=[
                    _content(stable_id("student-action", step_id, index), value)
                    for index, value in enumerate(phase.student_actions, 1)
                ],
                suggested_teacher_wording=_generated(
                    stable_id("teacher-wording", step_id),
                    "Clarify the publisher directions in shorter steps "
                    "without changing the task, order, or required evidence.",
                ),
                question_ids=question_ids,
                checks_for_understanding=[_content(
                    stable_id("step-check", step_id),
                    phase.check_for_understanding,
                )],
                misconceptions=[_content(
                    stable_id("step-watch", step_id), phase.watch_for
                )],
                eld_supports=[_content(
                    stable_id("step-language", step_id),
                    phase.language_support,
                )],
                differentiation=[
                    _content(
                        stable_id("step-differentiation", step_id, index),
                        value,
                    )
                    for index, value in enumerate(phase.differentiation, 1)
                ],
                transition=_content(
                    stable_id("step-transition", step_id),
                    phase.transition_out,
                ),
                student_reader_references=reader_references,
                activity_book_references=activity_references,
                source_references=refs,
            ))

        agenda_by_phase = {
            phase.phase_id: agenda[index].agenda_item_id
            for index, phase in enumerate(intelligence.phases)
        }
        objectives = []
        for objective in intelligence.objectives:
            official = _content(
                stable_id("official-objective", objective.objective_id),
                objective.publisher_objective,
            )
            friendly = _student_adaptation(
                stable_id("student-objective", objective.objective_id),
                official,
                objective.student_friendly_interpretation,
            )
            objectives.append(TeachingObjective(
                objective_id=objective.objective_id,
                official=official,
                student_friendly=friendly,
                evidence_of_mastery=_content(
                    stable_id("mastery", objective.objective_id),
                    objective.evidence_of_mastery,
                ),
                objective_type="content",
                meaning_preserved=_meaning_preserved(official, friendly),
            ))

        questions = []
        for question in intelligence.questions:
            answer = (
                _content(
                    stable_id("expected-answer", question.question_id),
                    question.publisher_answer,
                )
                if question.publisher_answer
                else _unavailable(
                    stable_id("expected-answer", question.question_id),
                    "Publisher answer was not located in the verified sources; "
                    "teacher review is required.",
                )
            )
            questions.append(TeachingQuestion(
                question_id=question.question_id,
                sequence=question.sequence,
                agenda_item_id=agenda_by_phase[question.phase_id],
                exact_question=_content(
                    stable_id("exact-question", question.question_id),
                    question.question,
                ),
                expected_answer=answer,
                publisher_answer_guidance=(
                    answer if question.publisher_answer else None
                ),
                text_evidence=(
                    _content(
                        stable_id("question-evidence", question.question_id),
                        question.text_evidence,
                    )
                    if question.text_evidence else None
                ),
                follow_up=_generated(
                    stable_id("question-follow-up", question.question_id),
                    question.follow_up,
                ),
                misconception=_generated(
                    stable_id("question-misconception", question.question_id),
                    question.misconception,
                ),
                eld_sentence_frame=_generated(
                    stable_id("question-frame", question.question_id),
                    question.sentence_frame,
                ),
                answer_visibility=(
                    "teacher_only" if question.publisher_answer
                    else "unavailable"
                ),
            ))

        vocabulary = [
            TeachingVocabulary(
                vocabulary_id=stable_id(
                    "teaching-vocabulary", bundle.lesson_id, value.word
                ),
                word=value.word,
                official_definition=(
                    _content(
                        stable_id("official-definition", value.word),
                        value.publisher_definition,
                    )
                    if value.publisher_definition else None
                ),
                student_friendly_definition=_content(
                    stable_id("student-definition", value.word),
                    value.student_friendly_explanation,
                ),
                pronunciation=value.pronunciation,
                teacher_explanation=_generated(
                    stable_id("vocabulary-explanation", value.word),
                    f"Explain {value.word} in the verified lesson context.",
                ),
                example=_content(
                    stable_id("vocabulary-example", value.word), value.example
                ),
                visual_suggestion=_generated(
                    stable_id("vocabulary-visual", value.word),
                    value.visual_suggestion,
                ),
                gesture_suggestion=_generated(
                    stable_id("vocabulary-gesture", value.word),
                    "Use a simple teacher-selected gesture only if it clarifies "
                    "the meaning without changing it.",
                ),
                eld_support=_generated(
                    stable_id("vocabulary-eld", value.word),
                    value.eld_support,
                ),
                misconception=_generated(
                    stable_id("vocabulary-misconception", value.word),
                    value.misconception,
                ),
            )
            for value in intelligence.vocabulary
        ]

        slide_rows: list[StudentSlide] = []

        def add_slide(
            slide_type: str,
            title: str,
            content: list[str],
            *,
            agenda_item_id: str | None = None,
            prompt: str | None = None,
            notes: list[str] | None = None,
            question_ids: list[str] | None = None,
            references: list[TeachingSourceReference] | None = None,
            visual: str = "Use editable text and simple high-contrast shapes.",
            page_reference: str | None = None,
            activity_reference: str | None = None,
        ) -> None:
            slide_rows.append(StudentSlide(
                slide_id=stable_id(
                    "student-slide", bundle.lesson_id, len(slide_rows) + 1,
                    slide_type, title,
                ),
                slide_number=len(slide_rows) + 1,
                agenda_item_id=agenda_item_id,
                slide_type=slide_type,
                title=title,
                visible_student_content=content,
                student_prompt=prompt,
                page_reference=page_reference,
                activity_reference=activity_reference,
                visual_specification=visual,
                speaker_notes=notes or [],
                source_references=references or [],
                adaptation_classification=ContentOrigin.STUDENT_ADAPTATION,
                question_ids=question_ids or [],
            ))

        add_slide(
            "title",
            intelligence.identity.lesson_title,
            [
                f"Grade {intelligence.identity.grade} · "
                f"Unit {intelligence.identity.unit} · "
                f"Lesson {intelligence.identity.lesson_number}"
            ],
            notes=["Open the lesson and orient students to today’s work."],
            references=_refs(intelligence.provenance_index[:1]),
        )
        add_slide(
            "agenda",
            "Today’s Lesson",
            [
                f"{item.official_order}. {item.student_friendly_title.text}"
                + (
                    f" — {item.duration_minutes} min"
                    if item.duration_minutes is not None else ""
                )
                for item in agenda
            ],
            notes=["Follow this order exactly; timings come from the lesson."],
            references=[
                ref for item in agenda for ref in item.teacher_guide_references
            ],
        )
        add_slide(
            "objectives",
            "Learning Objectives",
            [value.student_friendly.text for value in objectives],
            notes=[
                f"Official: {value.official.text}" for value in objectives
            ],
            references=[
                ref for value in objectives
                for ref in value.official.source_references
            ],
        )
        structural_titles = {
            intelligence.identity.lesson_title.casefold(),
            "learning objectives",
        }
        for source_slide in intelligence.slide_specifications:
            if source_slide.title.casefold() in structural_titles:
                continue
            phase_id = next(
                (
                    question_phase[value]
                    for value in source_slide.question_ids
                    if value in question_phase
                ),
                None,
            )
            if phase_id is None:
                phase_id = next(
                    (
                        phase.phase_id for phase in intelligence.phases
                        if (
                            source_slide.title.casefold().startswith(
                                phase.title.casefold()
                            )
                            or phase.title.casefold().startswith(
                                source_slide.title.casefold()
                            )
                        )
                    ),
                    intelligence.phases[0].phase_id,
                )
            agenda_id = agenda_by_phase[phase_id]
            refs = _refs(phase_by_id[phase_id].source_pages)
            slide_type = (
                "discussion" if source_slide.question_ids
                else (
                    "homework"
                    if "homework" in source_slide.title.casefold()
                    or "take-home" in source_slide.title.casefold()
                    else "activity"
                )
            )
            add_slide(
                slide_type,
                source_slide.title,
                source_slide.student_facing_content,
                agenda_item_id=agenda_id,
                notes=source_slide.teacher_notes
                + source_slide.answer_guidance,
                question_ids=source_slide.question_ids,
                references=refs,
                visual=source_slide.visual_recommendation,
                page_reference=next(
                    (
                        value.page_reference
                        for value in intelligence.reading_guides
                        if value.page_reference in " ".join(
                            source_slide.student_facing_content
                        )
                    ),
                    None,
                ),
                activity_reference=next(
                    (
                        value.name
                        for value in intelligence.activities
                        if value.name.casefold() in " ".join(
                            source_slide.student_facing_content
                        ).casefold()
                    ),
                    None,
                ),
            )

        slide_ids_by_agenda: dict[str, list[str]] = {}
        slide_ids_by_question: dict[str, list[str]] = {}
        for slide in slide_rows:
            if slide.agenda_item_id:
                slide_ids_by_agenda.setdefault(
                    slide.agenda_item_id, []
                ).append(slide.slide_id)
            for question_id in slide.question_ids:
                slide_ids_by_question.setdefault(
                    question_id, []
                ).append(slide.slide_id)
        agenda = [
            item.model_copy(update={
                "slide_ids": slide_ids_by_agenda.get(
                    item.agenda_item_id, []
                )
            })
            for item in agenda
        ]
        steps = [
            item.model_copy(update={
                "slide_ids": slide_ids_by_agenda.get(
                    item.agenda_item_id, []
                )
            })
            for item in steps
        ]
        questions = [
            item.model_copy(update={
                "slide_ids": slide_ids_by_question.get(item.question_id, [])
            })
            for item in questions
        ]

        lesson_purpose = (
            _content(
                stable_id("lesson-purpose", bundle.lesson_id),
                intelligence.objectives[0].publisher_objective,
            )
            if intelligence.objectives else _unavailable(
                stable_id("lesson-purpose", bundle.lesson_id),
                "No official lesson purpose was located.",
            )
        )
        all_materials = list(dict.fromkeys(
            material for phase in intelligence.phases
            for material in phase.materials
        ))
        reader_pages = list(dict.fromkeys(
            value.page_reference for value in intelligence.reading_guides
            if value.page_reference
        ))
        activity_pages = [
            value.name for value in intelligence.activities
        ]
        warnings = [
            value.text for value in intelligence.source_limitations
        ]
        if not intelligence.reading_guides:
            warnings.append("Student Reader guidance is unavailable.")
        package = StructuredTeachingPackage(
            schema_version=TEACHING_PACKAGE_SCHEMA_VERSION,
            builder_version=TEACHING_PACKAGE_BUILDER_VERSION,
            adaptation_prompt_version=ADAPTATION_PROMPT_VERSION,
            deterministic_model_version=DETERMINISTIC_MODEL_VERSION,
            package_digest="pending",
            source_bundle_digest=bundle.bundle_digest,
            lesson_intelligence_digest=intelligence.package_digest,
            dashboard=LessonDashboard(
                curriculum=intelligence.identity.curriculum_program,
                grade=intelligence.identity.grade,
                unit=intelligence.identity.unit,
                lesson_number=intelligence.identity.lesson_number,
                lesson_title=intelligence.identity.lesson_title,
                estimated_duration_minutes=(
                    intelligence.identity.estimated_duration_minutes
                ),
                materials=all_materials,
                student_reader_pages=reader_pages,
                activity_book_pages=activity_pages,
                lesson_purpose=lesson_purpose,
                big_idea=_generated(
                    stable_id("big-idea", bundle.lesson_id),
                    "Use the official objectives and required lesson evidence "
                    "to explain the central learning of this lesson.",
                ),
                why_it_matters=_generated(
                    stable_id("why-it-matters", bundle.lesson_id),
                    "The lesson develops the grade-level reading, discussion, "
                    "and writing work named in the official objectives.",
                ),
                teacher_reminders=[
                    _content(
                        stable_id("teacher-reminder", bundle.lesson_id, index),
                        value,
                    )
                    for index, value in enumerate(
                        intelligence.before_you_teach, 1
                    )
                ],
                missing_resource_warnings=warnings,
            ),
            five_minute_summary=[
                lesson_purpose,
                _generated(
                    stable_id("five-minute-sequence", bundle.lesson_id),
                    "Teach the agenda in its listed order, use the required "
                    "questions, and finish with the official closing or "
                    "homework requirement.",
                ),
            ],
            agenda=agenda,
            objectives=objectives,
            background_knowledge=[
                _content(
                    stable_id("background", bundle.lesson_id, index), value
                )
                for index, value in enumerate(
                    intelligence.before_you_teach, 1
                )
            ],
            vocabulary=vocabulary,
            teaching_steps=steps,
            questions=questions,
            student_reader_guidance=[
                _content(
                    stable_id(
                        "reader-guidance",
                        value.assignment_id,
                        index,
                    ),
                    content,
                )
                for value in intelligence.reading_guides
                for index, content in enumerate(
                    [
                        value.purpose,
                        *value.important_ideas,
                        *value.think_alouds,
                        *value.text_evidence_to_notice,
                        *value.limitations,
                    ],
                    1,
                )
            ],
            activity_book_guidance=[
                _content(
                    stable_id(
                        "activity-guidance",
                        value.assignment_id,
                        index,
                    ),
                    content,
                )
                for value in intelligence.activities
                for index, content in enumerate(
                    [
                        value.purpose,
                        value.teacher_directions,
                        value.student_task,
                        value.expected_product,
                        *(
                            [value.publisher_guidance]
                            if value.publisher_guidance else []
                        ),
                    ],
                    1,
                )
            ],
            assessment=[
                _content(
                    stable_id("assessment", bundle.lesson_id, index), value
                )
                for index, value in enumerate(
                    intelligence.assessment_and_evidence, 1
                )
            ],
            wrap_up=[
                _content(
                    stable_id("wrap-up", bundle.lesson_id, index), value
                )
                for index, value in enumerate(
                    intelligence.homework_and_closing, 1
                )
                if "homework" not in value.text.casefold()
            ],
            homework=[
                _content(
                    stable_id("homework", bundle.lesson_id, index), value
                )
                for index, value in enumerate(
                    intelligence.homework_and_closing, 1
                )
                if "homework" in value.text.casefold()
            ],
            eld_supports=[
                _content(
                    stable_id("eld", bundle.lesson_id, index), value
                )
                for index, value in enumerate(
                    [
                        item for values in
                        intelligence.differentiation_and_eld.values()
                        for item in values
                    ],
                    1,
                )
            ],
            differentiation=[
                _content(
                    stable_id(
                        "package-differentiation",
                        bundle.lesson_id,
                        phase.phase_id,
                        index,
                    ),
                    value,
                )
                for phase in intelligence.phases
                for index, value in enumerate(phase.differentiation, 1)
            ],
            student_slides=slide_rows,
            provenance=_refs(intelligence.provenance_index),
            warnings=warnings,
            validation=TeachingPackageValidationReport(
                status="pass",
                package_digest="pending",
                validator_version=TEACHING_PACKAGE_VALIDATOR_VERSION,
            ),
        )
        package = package.model_copy(
            update={"package_digest": _package_digest(package)}
        )
        report = TeachingPackageValidator().validate(package, intelligence)
        return package.model_copy(update={"validation": report})


def load_cached_teaching_package(
    path: str | Path,
    *,
    bundle_digest: str,
    intelligence_digest: str,
) -> StructuredTeachingPackage | None:
    target = Path(path)
    if not target.is_file():
        return None
    try:
        package = StructuredTeachingPackage.model_validate_json(
            target.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if (
        package.source_bundle_digest != bundle_digest
        or package.lesson_intelligence_digest != intelligence_digest
        or package.builder_version != TEACHING_PACKAGE_BUILDER_VERSION
        or package.adaptation_prompt_version != ADAPTATION_PROMPT_VERSION
        or package.deterministic_model_version
        != DETERMINISTIC_MODEL_VERSION
        or package.validation.validator_version
        != TEACHING_PACKAGE_VALIDATOR_VERSION
        or package.package_digest != _package_digest(package)
    ):
        return None
    return package


__all__ = [
    "ADAPTATION_PROMPT_VERSION", "DETERMINISTIC_MODEL_VERSION",
    "TeachingPackageBuilder", "TeachingPackageValidator",
    "TEACHING_PACKAGE_BUILDER_VERSION",
    "TEACHING_PACKAGE_VALIDATOR_VERSION", "load_cached_teaching_package",
]
