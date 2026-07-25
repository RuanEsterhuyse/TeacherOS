"""Curriculum-agnostic, instruction-first canonical lesson contract."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Availability(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NOT_REQUIRED = "not_required"


class GuidanceOrigin(str, Enum):
    CURRICULUM_REQUIRED = "curriculum_required"
    SOURCE_DERIVED = "source_derived"
    GENERATED_GUIDANCE = "generated_instructional_guidance"


class CurriculumReference(StrictModel):
    source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    printed_page_references: list[str] = Field(default_factory=list)
    pdf_page_numbers: list[int] = Field(default_factory=list)
    section_references: list[str] = Field(default_factory=list)
    availability: Availability = Availability.AVAILABLE
    warnings: list[str] = Field(default_factory=list)


class InstructionalResource(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    resource_type: str = Field(
        min_length=1,
        description=(
            "Curriculum-defined role such as Student Reader, Novel, Article, "
            "Poem, Primary Source, Video Transcript, or Teacher-created text."
        ),
    )
    source_identifier: Optional[str] = None
    availability: Availability
    references: list[CurriculumReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceProvenance(StrictModel):
    references: list[CurriculumReference] = Field(default_factory=list)
    origin: GuidanceOrigin = GuidanceOrigin.SOURCE_DERIVED
    availability: Availability = Availability.AVAILABLE
    notes: list[str] = Field(default_factory=list)


class TimingMetadata(StrictModel):
    duration_minutes: int = Field(ge=0)
    start_offset_minutes: Optional[int] = Field(default=None, ge=0)
    end_offset_minutes: Optional[int] = Field(default=None, ge=0)
    flexibility: Literal["fixed", "recommended", "flexible"] = "recommended"
    pacing_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def offsets_match_duration(self) -> "TimingMetadata":
        if (self.start_offset_minutes is None) != (
            self.end_offset_minutes is None
        ):
            raise ValueError("timing offsets must be supplied together")
        if self.start_offset_minutes is not None:
            if self.end_offset_minutes < self.start_offset_minutes:
                raise ValueError("timing end offset precedes start offset")
            if (
                self.end_offset_minutes - self.start_offset_minutes
                != self.duration_minutes
            ):
                raise ValueError("timing offsets must match duration")
        return self


class GroundedStatement(StrictModel):
    text: Optional[str] = None
    availability: Availability = Availability.AVAILABLE
    source_provenance: list[SourceProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def unavailable_statements_have_no_text(self) -> "GroundedStatement":
        if self.availability == Availability.UNAVAILABLE and self.text:
            raise ValueError("unavailable statements cannot assert text")
        if self.availability == Availability.AVAILABLE and not self.text:
            raise ValueError("available statements require text")
        return self


class AnnotationType(str, Enum):
    HIGHLIGHT = "highlight"
    CIRCLE = "circle"
    UNDERLINE = "underline"
    STAR = "star"
    MARGIN_NOTE = "margin_note"
    QUESTION_MARK = "question_mark"
    SEQUENCE_MARKER = "sequence_marker"
    CAUSE_AND_EFFECT = "cause_and_effect"
    CHARACTER_EVIDENCE = "character_evidence"
    THEME_EVIDENCE = "theme_evidence"


class Annotation(StrictModel):
    id: str = Field(min_length=1)
    type: AnnotationType
    exact_location: Optional[str] = None
    student_instruction: str = Field(min_length=1)
    instructional_purpose: str = Field(min_length=1)
    teacher_explanation: str = Field(min_length=1)
    symbol: Optional[str] = None
    source_reference: Optional[CurriculumReference] = None
    source_availability: Availability = Availability.AVAILABLE

    @model_validator(mode="after")
    def location_requires_source(self) -> "Annotation":
        if self.source_availability == Availability.AVAILABLE:
            if not self.exact_location or self.source_reference is None:
                raise ValueError(
                    "available annotations require an exact location and source"
                )
        elif self.exact_location:
            raise ValueError(
                "unavailable annotations cannot assert an exact location"
            )
        return self


class ExpectedAnswer(StrictModel):
    answer: Optional[str] = None
    availability: Availability = Availability.AVAILABLE
    evidence: list["TextEvidence"] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def answer_matches_availability(self) -> "ExpectedAnswer":
        if self.availability == Availability.UNAVAILABLE and self.answer:
            raise ValueError("unavailable answers cannot assert content")
        if self.availability == Availability.AVAILABLE and not self.answer:
            raise ValueError("available answers require content")
        return self


class TextEvidence(StrictModel):
    description: Optional[str] = None
    quotation: Optional[str] = None
    location: Optional[str] = None
    availability: Availability = Availability.AVAILABLE
    source_provenance: list[SourceProvenance] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_matches_availability(self) -> "TextEvidence":
        if self.availability == Availability.UNAVAILABLE:
            if self.description or self.quotation or self.location:
                raise ValueError("unavailable evidence cannot assert content")
        elif not (self.description or self.quotation):
            raise ValueError("available evidence requires supported content")
        return self


class MisconceptionResponse(StrictModel):
    misconception: str = Field(min_length=1)
    correction: str = Field(min_length=1)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class TeacherQuestion(StrictModel):
    id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    question_type: Literal[
        "literal",
        "inferential",
        "vocabulary",
        "theme",
        "authors_craft",
        "discussion",
        "writing_preparation",
        "formative_check",
    ]
    bloom_level: Literal[
        "remember", "understand", "apply", "analyze", "evaluate", "create"
    ]
    difficulty: Literal[
        "foundational", "developing", "grade_level", "advanced"
    ]
    estimated_discussion_time_minutes: int = Field(ge=0)
    response_format: Literal[
        "oral",
        "written",
        "partner_discussion",
        "small_group_discussion",
        "whole_class_discussion",
        "annotation",
        "selected_response",
        "constructed_response",
        "nonverbal",
        "independent_reflection",
    ]
    expected_answers: list[ExpectedAnswer] = Field(default_factory=list)
    text_evidence: list[TextEvidence] = Field(default_factory=list)
    common_misconceptions: list[MisconceptionResponse] = Field(
        default_factory=list
    )
    follow_up_questions: list[str] = Field(default_factory=list)
    scaffolds: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)
    standard_references: list[str] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    answer_availability: Availability = Availability.AVAILABLE

    @model_validator(mode="after")
    def answers_obey_source_availability(self) -> "TeacherQuestion":
        if self.answer_availability == Availability.UNAVAILABLE:
            if any(
                answer.availability != Availability.UNAVAILABLE
                for answer in self.expected_answers
            ) or any(
                evidence.availability != Availability.UNAVAILABLE
                for evidence in self.text_evidence
            ):
                raise ValueError(
                    "source-dependent unavailable questions cannot assert answers"
                )
        elif not self.expected_answers:
            raise ValueError("available questions require expected answers")
        return self


class GuidanceEntry(StrictModel):
    text: str = Field(min_length=1)
    timing: Optional[TimingMetadata] = None
    origin: GuidanceOrigin
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class TeacherGuidance(StrictModel):
    introduction: list[GuidanceEntry] = Field(default_factory=list)
    modeling: list[GuidanceEntry] = Field(default_factory=list)
    directions: list[GuidanceEntry] = Field(default_factory=list)
    questioning: list[GuidanceEntry] = Field(default_factory=list)
    monitoring_notes: list[GuidanceEntry] = Field(default_factory=list)
    transition: list[GuidanceEntry] = Field(default_factory=list)
    closure: list[GuidanceEntry] = Field(default_factory=list)


class StudentTask(StrictModel):
    id: str = Field(min_length=1)
    task_type: Literal[
        "read",
        "listen",
        "discuss",
        "annotate",
        "write",
        "share",
        "reflect",
        "complete_activity_book",
        "respond_independently",
    ]
    instruction: str = Field(min_length=1)
    timing: Optional[TimingMetadata] = None
    grouping: Optional[str] = None
    response_format: Optional[str] = None
    materials: list[str] = Field(default_factory=list)
    completion_evidence: Optional[str] = None
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    status: Literal["required", "optional"] = "required"


class InstructionalTransition(StrictModel):
    instruction: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    timing: TimingMetadata
    from_reference: str = Field(min_length=1)
    to_reference: str = Field(min_length=1)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class LessonSlideMapping(StrictModel):
    slide_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    lesson_block_id: str = Field(min_length=1)
    reading_chunk_id: Optional[str] = None
    pause_point_id: Optional[str] = None
    slide_type: str = Field(min_length=1)
    layout: str = Field(min_length=1)
    title: str = Field(min_length=1)
    student_content: list[str] = Field(default_factory=list)
    question_references: list[str] = Field(default_factory=list)
    annotation_references: list[str] = Field(default_factory=list)
    task_references: list[str] = Field(default_factory=list)
    timing: Optional[TimingMetadata] = None
    interaction: Optional[str] = None
    visual_direction: Optional[str] = None
    image_prompt: Optional[str] = None
    accessibility_text: Optional[str] = None
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class PausePoint(StrictModel):
    id: str = Field(min_length=1)
    stop_location: Optional[str] = None
    timing: TimingMetadata
    teacher_prompt: str = Field(min_length=1)
    student_action: StudentTask
    discussion_format: str = Field(min_length=1)
    questions: list[TeacherQuestion] = Field(default_factory=list)
    expected_answers: list[ExpectedAnswer] = Field(default_factory=list)
    evidence: list[TextEvidence] = Field(default_factory=list)
    annotation_instruction: Optional[Annotation] = None
    scaffold: list[str] = Field(default_factory=list)
    extension: list[str] = Field(default_factory=list)
    transition: Optional[InstructionalTransition] = None
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    source_availability: Availability = Availability.AVAILABLE

    @model_validator(mode="after")
    def stop_location_obeys_availability(self) -> "PausePoint":
        if self.source_availability == Availability.AVAILABLE:
            if not self.stop_location:
                raise ValueError("available pause points require a stop location")
        elif self.stop_location:
            raise ValueError(
                "unavailable pause points cannot assert a stop location"
            )
        return self


class ReadingChunk(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    instructional_resource_ids: list[str] = Field(default_factory=list)
    reader_page_references: list[str] = Field(default_factory=list)
    paragraph_or_section_references: list[str] = Field(default_factory=list)
    reading_mode: Literal[
        "teacher_read_aloud",
        "student_silent_reading",
        "partner_reading",
        "choral_reading",
        "shared_reading",
        "echo_reading",
        "small_group_reading",
        "independent_rereading",
        "teacher_modeling",
        "unavailable",
    ]
    timing: TimingMetadata
    pause_points: list[PausePoint] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    questions: list[TeacherQuestion] = Field(default_factory=list)
    expected_answers: list[ExpectedAnswer] = Field(default_factory=list)
    evidence: list[TextEvidence] = Field(default_factory=list)
    misconceptions: list[MisconceptionResponse] = Field(default_factory=list)
    follow_up_support: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)
    transition: Optional[InstructionalTransition] = None
    slide_mappings: list[LessonSlideMapping] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    source_availability: Availability = Availability.AVAILABLE


class LessonBlock(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    timing: TimingMetadata
    objective: GroundedStatement
    teacher_guidance: TeacherGuidance = Field(default_factory=TeacherGuidance)
    student_tasks: list[StudentTask] = Field(default_factory=list)
    questions: list[TeacherQuestion] = Field(default_factory=list)
    reading_chunks: list[ReadingChunk] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    wida_supports: list[str] = Field(default_factory=list)
    transitions: list[InstructionalTransition] = Field(default_factory=list)
    slide_mappings: list[LessonSlideMapping] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    availability: Availability = Availability.AVAILABLE


class AgendaItem(StrictModel):
    id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    title: str = Field(min_length=1)
    start_offset_minutes: int = Field(ge=0)
    end_offset_minutes: int = Field(ge=0)
    duration_minutes: int = Field(ge=0)
    lesson_block_reference: str = Field(min_length=1)
    slide_references: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    status: Literal["required", "optional"] = "required"

    @model_validator(mode="after")
    def item_timing_is_consistent(self) -> "AgendaItem":
        if self.end_offset_minutes - self.start_offset_minutes != self.duration_minutes:
            raise ValueError("agenda offsets must match duration")
        return self


class Agenda(StrictModel):
    selected_duration_minutes: int = Field(ge=0)
    items: list[AgendaItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def is_contiguous_master_timeline(self) -> "Agenda":
        if [item.sequence for item in self.items] != list(
            range(1, len(self.items) + 1)
        ):
            raise ValueError("agenda sequences must be continuous")
        offset = 0
        for item in self.items:
            if item.start_offset_minutes != offset:
                raise ValueError("agenda items must be contiguous and ordered")
            offset = item.end_offset_minutes
        if offset != self.selected_duration_minutes:
            raise ValueError("agenda timing must total selected lesson duration")
        return self


class VocabularyEntry(StrictModel):
    word: str = Field(min_length=1)
    pronunciation: Optional[str] = None
    definition: GroundedStatement
    student_friendly_definition: GroundedStatement
    example: GroundedStatement
    visual_suggestion: Optional[str] = None
    ell_support: list[str] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class ActivityBookTask(StrictModel):
    id: str = Field(min_length=1)
    resource_id: Optional[str] = None
    page: str = Field(min_length=1)
    timing: Optional[TimingMetadata] = None
    teacher_directions: list[GuidanceEntry] = Field(default_factory=list)
    student_tasks: list[StudentTask] = Field(default_factory=list)
    expected_answers: list[ExpectedAnswer] = Field(default_factory=list)
    common_mistakes: list[MisconceptionResponse] = Field(default_factory=list)
    slide_mappings: list[LessonSlideMapping] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    source_availability: Availability = Availability.UNAVAILABLE


class AssessmentPlan(StrictModel):
    title: str = Field(min_length=1)
    purpose: GroundedStatement
    timing: Optional[TimingMetadata] = None
    student_tasks: list[StudentTask] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    availability: Availability = Availability.AVAILABLE


class ExitTicket(StrictModel):
    prompt: GroundedStatement
    timing: TimingMetadata
    expected_answers: list[ExpectedAnswer] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    slide_mappings: list[LessonSlideMapping] = Field(default_factory=list)


class HomeworkAssignment(StrictModel):
    title: str = Field(min_length=1)
    directions: str = Field(min_length=1)
    timing: Optional[TimingMetadata] = None
    resource_references: list[CurriculumReference] = Field(default_factory=list)
    source_provenance: list[SourceProvenance] = Field(default_factory=list)


class TeacherReflection(StrictModel):
    prompts: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class LessonInformation(StrictModel):
    curriculum: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    duration_minutes: int = Field(ge=0)
    essential_question: GroundedStatement


class CanonicalLesson(StrictModel):
    schema_version: str = "1.0"
    lesson_information: LessonInformation
    standards: list[str] = Field(default_factory=list)
    learning_target: GroundedStatement
    language_objective: GroundedStatement
    success_criteria: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    instructional_resources: list[InstructionalResource] = Field(
        default_factory=list
    )
    agenda: Agenda
    lesson_blocks: list[LessonBlock] = Field(default_factory=list)
    vocabulary: list[VocabularyEntry] = Field(default_factory=list)
    activity_book: list[ActivityBookTask] = Field(default_factory=list)
    assessment: list[AssessmentPlan] = Field(default_factory=list)
    exit_ticket: ExitTicket
    homework: list[HomeworkAssignment] = Field(default_factory=list)
    teacher_reflection: TeacherReflection
    source_provenance: list[SourceProvenance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_instructional_graph(self) -> "CanonicalLesson":
        if (
            self.lesson_information.duration_minutes
            != self.agenda.selected_duration_minutes
        ):
            raise ValueError("lesson duration must equal agenda duration")
        blocks = {block.id: block for block in self.lesson_blocks}
        if len(blocks) != len(self.lesson_blocks):
            raise ValueError("lesson block IDs must be unique")
        agenda_by_block = {
            item.lesson_block_reference: item for item in self.agenda.items
        }
        if len(agenda_by_block) != len(self.agenda.items):
            raise ValueError("each lesson block may appear only once in agenda")
        if set(agenda_by_block) != set(blocks):
            raise ValueError("agenda and lesson blocks must reference each other")
        resources = {item.id for item in self.instructional_resources}
        slide_ids: list[str] = []
        question_ids: list[str] = []
        task_ids: list[str] = []
        annotation_ids: list[str] = []
        chunk_ids: list[str] = []
        pause_ids: list[str] = []
        all_mappings: list[LessonSlideMapping] = []
        for block in self.lesson_blocks:
            if (
                block.timing.duration_minutes
                != agenda_by_block[block.id].duration_minutes
            ):
                raise ValueError("block timing must equal its agenda item")
            slide_ids.extend(item.slide_id for item in block.slide_mappings)
            all_mappings.extend(block.slide_mappings)
            question_ids.extend(item.id for item in block.questions)
            task_ids.extend(item.id for item in block.student_tasks)
            for chunk in block.reading_chunks:
                chunk_ids.append(chunk.id)
                if not set(chunk.instructional_resource_ids) <= resources:
                    raise ValueError("reading chunk references an unknown resource")
                slide_ids.extend(item.slide_id for item in chunk.slide_mappings)
                all_mappings.extend(chunk.slide_mappings)
                question_ids.extend(item.id for item in chunk.questions)
                annotation_ids.extend(item.id for item in chunk.annotations)
                for pause in chunk.pause_points:
                    pause_ids.append(pause.id)
                    task_ids.append(pause.student_action.id)
                    question_ids.extend(item.id for item in pause.questions)
                    if pause.annotation_instruction:
                        annotation_ids.append(pause.annotation_instruction.id)
        agenda_slides = [
            slide for item in self.agenda.items for slide in item.slide_references
        ]
        if set(agenda_slides) != set(slide_ids):
            raise ValueError("agenda slide references must match lesson mappings")
        for label, values in (
            ("slide", slide_ids),
            ("question", question_ids),
            ("task", task_ids),
            ("annotation", annotation_ids),
            ("reading chunk", chunk_ids),
            ("pause point", pause_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} IDs must be unique")
        if sorted(item.sequence for item in all_mappings) != list(
            range(1, len(all_mappings) + 1)
        ):
            raise ValueError("slide sequences must be continuous")
        return self


__all__ = [
    "ActivityBookTask",
    "Agenda",
    "AgendaItem",
    "Annotation",
    "AnnotationType",
    "AssessmentPlan",
    "Availability",
    "CanonicalLesson",
    "CurriculumReference",
    "ExpectedAnswer",
    "GroundedStatement",
    "GuidanceEntry",
    "GuidanceOrigin",
    "HomeworkAssignment",
    "InstructionalResource",
    "InstructionalTransition",
    "LessonBlock",
    "LessonInformation",
    "LessonSlideMapping",
    "PausePoint",
    "ReadingChunk",
    "SourceProvenance",
    "StudentTask",
    "TeacherGuidance",
    "TeacherQuestion",
    "TeacherReflection",
    "TextEvidence",
    "TimingMetadata",
    "VocabularyEntry",
]
