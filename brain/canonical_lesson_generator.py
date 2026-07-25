"""Build the curriculum-agnostic canonical lesson from validated stage data."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from schemas.analyzer_output_schema import CurriculumAnalyzerOutput
from schemas.canonical_lesson_schema import (
    ActivityBookTask,
    Agenda,
    AgendaItem,
    AssessmentPlan,
    Availability,
    CanonicalLesson,
    CurriculumReference,
    ExpectedAnswer,
    ExitTicket,
    GroundedStatement,
    GuidanceEntry,
    GuidanceOrigin,
    HomeworkAssignment,
    InstructionalResource,
    LessonBlock,
    LessonInformation,
    LessonSlideMapping,
    ReadingChunk,
    SourceProvenance,
    StudentTask,
    TeacherGuidance,
    TeacherQuestion,
    TeacherReflection,
    TimingMetadata,
    VocabularyEntry,
)
from schemas.instruction_design_schema import InstructionDesign
from schemas.lesson_package_schema import LessonPackage
from schemas.presentation_design_schema import PresentationDesignOutput
from schemas.reader_output_schema import CurriculumReaderOutput
from schemas.student_reader_source_schema import StudentReaderSource


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"


def _digest(values: list[Any]) -> str:
    payload = [
        value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for value in values
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _availability_from_reader(
    source: StudentReaderSource | None,
) -> Availability:
    if source is None or not source.source_available:
        return Availability.UNAVAILABLE
    if source.extraction_status in {"completed", "completed_with_warnings"}:
        return Availability.AVAILABLE
    if source.extraction_status == "partial":
        return Availability.PARTIAL
    return Availability.UNAVAILABLE


def _reference(
    source_id: str,
    source_type: str,
    *,
    printed: list[str] | None = None,
    pdf: list[int] | None = None,
    sections: list[str] | None = None,
    availability: Availability = Availability.AVAILABLE,
    warnings: list[str] | None = None,
) -> CurriculumReference:
    return CurriculumReference(
        source_id=source_id,
        source_type=source_type,
        printed_page_references=printed or [],
        pdf_page_numbers=pdf or [],
        section_references=sections or [],
        availability=availability,
        warnings=warnings or [],
    )


def _provenance(
    reference: CurriculumReference,
    *,
    origin: GuidanceOrigin = GuidanceOrigin.SOURCE_DERIVED,
) -> list[SourceProvenance]:
    return [
        SourceProvenance(
            references=[reference],
            origin=origin,
            availability=reference.availability,
        )
    ]


def _guidance_entry(
    text: str,
    provenance: list[SourceProvenance],
    *,
    origin: GuidanceOrigin = GuidanceOrigin.SOURCE_DERIVED,
) -> GuidanceEntry:
    return GuidanceEntry(
        text=text,
        origin=origin,
        source_provenance=provenance,
    )


def _question(
    slide_id: str,
    position: int,
    text: str,
    responses: list[str],
    standards: list[str],
    provenance: list[SourceProvenance],
    minutes: int,
) -> TeacherQuestion:
    available = bool(responses)
    return TeacherQuestion(
        id=f"{slide_id}-question-{position}",
        question_text=text,
        question_type="discussion",
        bloom_level="understand",
        difficulty="grade_level",
        estimated_discussion_time_minutes=minutes,
        response_format="whole_class_discussion",
        expected_answers=(
            [
                ExpectedAnswer(
                    answer=response,
                    availability=Availability.AVAILABLE,
                    source_provenance=provenance,
                )
                for response in responses
            ]
            if available
            else [
                ExpectedAnswer(
                    availability=Availability.UNAVAILABLE,
                    source_provenance=provenance,
                )
            ]
        ),
        standard_references=standards,
        source_provenance=provenance,
        answer_availability=(
            Availability.AVAILABLE if available else Availability.UNAVAILABLE
        ),
    )


def _question_without_source_answer(
    question: TeacherQuestion,
) -> TeacherQuestion:
    payload = question.model_dump(mode="json")
    payload["answer_availability"] = Availability.UNAVAILABLE.value
    payload["expected_answers"] = [
        {
            "answer": None,
            "availability": Availability.UNAVAILABLE.value,
            "evidence": [],
            "source_provenance": payload["source_provenance"],
        }
    ]
    payload["text_evidence"] = []
    return TeacherQuestion.model_validate(payload)


def build_canonical_lesson(
    *,
    pipeline_input: Any,
    reader: CurriculumReaderOutput,
    analyzer: CurriculumAnalyzerOutput,
    instruction_design: InstructionDesign,
    presentation: PresentationDesignOutput,
    package: LessonPackage,
    curriculum: Any,
    student_resource_source: StudentReaderSource | None = None,
) -> CanonicalLesson:
    """Consolidate validated decisions without adding curriculum claims."""
    request = pipeline_input.request
    teacher_source_id = "teacher-guide"
    teacher_reference = _reference(
        teacher_source_id,
        "Teacher Guide",
        pdf=list(pipeline_input.pdf_page_references),
        sections=list(pipeline_input.source_references),
    )
    teacher_provenance = _provenance(teacher_reference)

    resources = [
        InstructionalResource(
            id=teacher_source_id,
            title="Teacher Guide",
            resource_type="Teacher Guide",
            source_identifier=getattr(curriculum, "teacher_guide_path", None),
            availability=Availability.AVAILABLE,
            references=[teacher_reference],
        )
    ]
    student_resource_id = "instructional-text"
    reader_availability = _availability_from_reader(student_resource_source)
    if getattr(curriculum, "student_reader_path", None) or reader.reader_references:
        reader_reference = _reference(
            student_resource_id,
            "Instructional Text",
            printed=list(reader.reader_references),
            pdf=(
                list(student_resource_source.matched_pdf_page_numbers)
                if student_resource_source
                else []
            ),
            availability=reader_availability,
            warnings=(
                list(student_resource_source.warnings)
                if student_resource_source
                else ["Instructional text was not retrieved."]
            ),
        )
        resources.append(InstructionalResource(
            id=student_resource_id,
            title="Instructional Text",
            resource_type="Instructional Text",
            source_identifier=getattr(curriculum, "student_reader_path", None),
            availability=reader_availability,
            references=[reader_reference],
            warnings=list(reader_reference.warnings),
        ))
    else:
        reader_reference = None

    activity_resource_id = "activity-resource"
    activity_availability = (
        Availability.UNAVAILABLE
        if reader.activity_book_references
        else Availability.NOT_REQUIRED
    )
    if getattr(curriculum, "activity_book_path", None) or reader.activity_book_references:
        activity_reference = _reference(
            activity_resource_id,
            "Activity Resource",
            printed=list(reader.activity_book_references),
            availability=activity_availability,
            warnings=(
                ["Activity resource content was not retrieved."]
                if reader.activity_book_references
                else []
            ),
        )
        resources.append(InstructionalResource(
            id=activity_resource_id,
            title="Activity Resource",
            resource_type="Activity Resource",
            source_identifier=getattr(curriculum, "activity_book_path", None),
            availability=activity_availability,
            references=[activity_reference],
            warnings=list(activity_reference.warnings),
        ))
    else:
        activity_reference = None

    segments = instruction_design.segments
    slides = presentation.slides
    blocks: list[LessonBlock] = []
    agenda_items: list[AgendaItem] = []
    offset = 0
    for index, slide in enumerate(slides, start=1):
        segment = segments[min(index - 1, len(segments) - 1)] if segments else None
        block_id = f"block-{index:02d}"
        minutes = slide.timing or 0
        provenance = [
            SourceProvenance(
                references=[
                    _reference(
                        teacher_source_id,
                        "Teacher Guide",
                        sections=list(slide.source_references),
                    )
                ],
                origin=(
                    GuidanceOrigin.GENERATED_GUIDANCE
                    if slide.fidelity_classification == "teacheros_added"
                    else GuidanceOrigin.SOURCE_DERIVED
                ),
            )
        ]
        notes = slide.teacher_notes
        guidance = TeacherGuidance(
            introduction=(
                [_guidance_entry(notes.instructional_purpose, provenance)]
                if notes.instructional_purpose
                else []
            ),
            modeling=(
                [_guidance_entry(notes.teacher_script, provenance)]
                if notes.teacher_script
                else []
            ),
            directions=[
                _guidance_entry(value, provenance)
                for value in notes.teacher_directions
            ],
            questioning=[
                _guidance_entry(value, provenance)
                for value in notes.questions
            ],
            monitoring_notes=[
                _guidance_entry(value, provenance)
                for value in (
                    notes.checks_for_understanding
                    + notes.misconceptions
                    + notes.differentiation
                )
            ],
            transition=(
                [_guidance_entry(notes.transition, provenance)]
                if notes.transition
                else []
            ),
            closure=[],
        )
        directions = list(slide.student_view.directions)
        student_tasks = [
            StudentTask(
                id=f"{block_id}-task-{position}",
                task_type=(
                    "discuss"
                    if slide.interaction.interaction_type.value
                    in {
                        "think_pair_share",
                        "turn_and_talk",
                        "small_group_discussion",
                    }
                    else "respond_independently"
                ),
                instruction=value,
                grouping=(
                    slide.interaction.grouping.value
                    if slide.interaction.grouping
                    else None
                ),
                response_format=slide.interaction.response_mode.value,
                materials=list(slide.materials),
                source_provenance=provenance,
            )
            for position, value in enumerate(directions, start=1)
        ]
        question_values = list(notes.questions)
        if slide.student_view.prompt:
            question_values.insert(0, slide.student_view.prompt)
        questions = [
            _question(
                slide.slide_id,
                position,
                value,
                list(notes.anticipated_responses),
                list(package.lesson_metadata.standards),
                provenance,
                slide.interaction.duration_minutes or 0,
            )
            for position, value in enumerate(
                dict.fromkeys(question_values), start=1
            )
        ]
        mapping = LessonSlideMapping(
            slide_id=slide.slide_id,
            sequence=slide.sequence_number,
            lesson_block_id=block_id,
            slide_type=slide.slide_type,
            layout=slide.design.layout.value,
            title=slide.student_view.title or slide.slide_type.replace("_", " ").title(),
            student_content=[
                value
                for value in (
                    slide.student_view.subtitle,
                    slide.student_view.body_text,
                    slide.student_view.prompt,
                    slide.student_view.quotation,
                    *slide.student_view.bullet_points,
                    *slide.student_view.vocabulary_terms,
                    *slide.student_view.sentence_frames,
                    *slide.student_view.directions,
                )
                if value
            ],
            question_references=[item.id for item in questions],
            task_references=[item.id for item in student_tasks],
            timing=TimingMetadata(duration_minutes=minutes),
            interaction=slide.interaction.interaction_type.value,
            visual_direction=slide.visuals.visual_description,
            image_prompt=slide.visuals.image_prompt,
            accessibility_text=slide.visuals.alt_text,
            source_provenance=provenance,
        )
        reader_refs = (
            list(segment.reader_references)
            if segment and segment.reader_references
            else []
        )
        is_reading = bool(reader_refs) or "read" in slide.slide_type.casefold()
        reading_chunks = []
        block_mappings = [mapping]
        if is_reading:
            chunk_provenance = (
                _provenance(reader_reference) if reader_reference else provenance
            )
            chunk_questions = (
                [
                    _question_without_source_answer(question)
                    for question in questions
                ]
                if reader_availability == Availability.UNAVAILABLE
                else questions
            )
            chunk = ReadingChunk(
                id=f"{block_id}-reading-01",
                title=slide.student_view.title or "Reading",
                purpose=notes.instructional_purpose or slide.slide_type,
                instructional_resource_ids=(
                    [student_resource_id] if reader_reference else []
                ),
                reader_page_references=(
                    reader_refs or list(reader.reader_references)
                ),
                paragraph_or_section_references=[],
                reading_mode=(
                    "unavailable"
                    if reader_availability == Availability.UNAVAILABLE
                    else (
                        "teacher_read_aloud"
                        if "read_aloud" in slide.slide_type
                        or "read-aloud" in slide.student_view.title.casefold()
                        else "student_silent_reading"
                    )
                ),
                timing=TimingMetadata(duration_minutes=minutes),
                questions=chunk_questions,
                expected_answers=[
                    answer
                    for question in chunk_questions
                    for answer in question.expected_answers
                ],
                follow_up_support=list(notes.eld_supports),
                extensions=[],
                slide_mappings=[
                    mapping.model_copy(
                        update={"reading_chunk_id": f"{block_id}-reading-01"}
                    )
                ],
                source_provenance=chunk_provenance,
                source_availability=reader_availability,
            )
            reading_chunks = [chunk]
            block_mappings = []
        block = LessonBlock(
            id=block_id,
            title=slide.student_view.title or slide.slide_type.replace("_", " ").title(),
            block_type=slide.slide_type,
            timing=TimingMetadata(duration_minutes=minutes),
            objective=GroundedStatement(
                text=analyzer.central_learning_goal.text,
                source_provenance=teacher_provenance,
            ),
            teacher_guidance=guidance,
            student_tasks=student_tasks,
            questions=[] if is_reading else questions,
            reading_chunks=reading_chunks,
            materials=list(slide.materials),
            standards=list(package.lesson_metadata.standards),
            wida_supports=list(notes.eld_supports),
            slide_mappings=block_mappings,
            source_provenance=provenance,
        )
        blocks.append(block)
        agenda_items.append(AgendaItem(
            id=f"agenda-{index:02d}",
            sequence=index,
            title=block.title,
            start_offset_minutes=offset,
            end_offset_minutes=offset + minutes,
            duration_minutes=minutes,
            lesson_block_reference=block_id,
            slide_references=[slide.slide_id],
            materials=list(slide.materials),
            objectives=[analyzer.central_learning_goal.text],
            status="required",
        ))
        offset += minutes

    activity_tasks = [
        ActivityBookTask(
            id=f"activity-{_slug(reference)}",
            resource_id=activity_resource_id if activity_reference else None,
            page=reference,
            source_provenance=(
                _provenance(activity_reference)
                if activity_reference
                else teacher_provenance
            ),
            source_availability=Availability.UNAVAILABLE,
        )
        for reference in reader.activity_book_references
    ]
    assessments = [
        AssessmentPlan(
            title=f"Assessment {position}",
            purpose=GroundedStatement(
                text=finding.text,
                source_provenance=[
                    SourceProvenance(
                        references=[
                            _reference(
                                teacher_source_id,
                                "Teacher Guide",
                                sections=list(finding.source_references),
                            )
                        ],
                        origin=(
                            GuidanceOrigin.GENERATED_GUIDANCE
                            if finding.is_inference
                            else GuidanceOrigin.SOURCE_DERIVED
                        ),
                    )
                ],
            ),
            source_provenance=teacher_provenance,
        )
        for position, finding in enumerate(
            analyzer.assessment_opportunities, start=1
        )
    ]
    homework = [
        HomeworkAssignment(
            title=f"Homework {position}",
            directions=value,
            source_provenance=teacher_provenance,
        )
        for position, value in enumerate(reader.homework, start=1)
    ]
    vocabulary = [
        VocabularyEntry(
            word=value,
            definition=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            student_friendly_definition=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            example=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            source_provenance=teacher_provenance,
        )
        for value in reader.vocabulary
    ]
    warnings = list(dict.fromkeys(
        package.unresolved_warnings
        + presentation.warnings
        + (
            list(student_resource_source.warnings)
            if student_resource_source
            else []
        )
        + (
            ["Activity resource content was unavailable; answers were not generated."]
            if activity_tasks
            else []
        )
    ))
    unavailable = GroundedStatement(availability=Availability.UNAVAILABLE)
    return CanonicalLesson(
        lesson_information=LessonInformation(
            curriculum=request.curriculum_name,
            grade=request.grade,
            unit=request.unit,
            lesson_number=request.lesson_number,
            lesson_title=reader.lesson_title or pipeline_input.lesson_title or f"Lesson {request.lesson_number}",
            duration_minutes=offset,
            essential_question=unavailable,
        ),
        standards=list(package.lesson_metadata.standards),
        learning_target=GroundedStatement(
            text=analyzer.central_learning_goal.text,
            source_provenance=teacher_provenance,
        ),
        language_objective=unavailable.model_copy(deep=True),
        success_criteria=[
            criterion
            for assessment in package.assessments
            for criterion in assessment.success_criteria
        ],
        materials=list(reader.materials),
        instructional_resources=resources,
        agenda=Agenda(selected_duration_minutes=offset, items=agenda_items),
        lesson_blocks=blocks,
        vocabulary=vocabulary,
        activity_book=activity_tasks,
        assessment=assessments,
        exit_ticket=ExitTicket(
            prompt=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            timing=TimingMetadata(duration_minutes=0),
        ),
        homework=homework,
        teacher_reflection=TeacherReflection(prompts=[
            "What evidence showed that students met the learning target?",
            "Which support or transition should be adjusted before reteaching?",
        ]),
        source_provenance=teacher_provenance,
        warnings=warnings,
        source_digest=_digest([
            pipeline_input,
            reader,
            analyzer,
            instruction_design,
            presentation,
            package,
            student_resource_source.model_dump(mode="json")
            if student_resource_source
            else None,
        ]),
    )


__all__ = ["build_canonical_lesson"]
