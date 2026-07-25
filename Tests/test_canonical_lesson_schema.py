"""Contract tests for the curriculum-agnostic canonical lesson."""

import pytest
from pydantic import ValidationError

from schemas.canonical_lesson_schema import (
    Agenda,
    AgendaItem,
    Availability,
    CanonicalLesson,
    ExpectedAnswer,
    ExitTicket,
    GroundedStatement,
    InstructionalResource,
    LessonBlock,
    LessonInformation,
    LessonSlideMapping,
    ReadingChunk,
    TeacherQuestion,
    TeacherReflection,
    TimingMetadata,
)


def canonical_lesson() -> CanonicalLesson:
    mapping = LessonSlideMapping(
        slide_id="slide-1",
        sequence=1,
        lesson_block_id="block-1",
        slide_type="discussion",
        layout="question_focus",
        title="Discuss the text",
        student_content=["What do you notice?"],
        timing=TimingMetadata(duration_minutes=10),
        interaction="none",
    )
    block = LessonBlock(
        id="block-1",
        title="Discuss the text",
        block_type="discussion",
        timing=TimingMetadata(duration_minutes=10),
        objective=GroundedStatement(text="Analyze evidence."),
        slide_mappings=[mapping],
    )
    return CanonicalLesson(
        lesson_information=LessonInformation(
            curriculum="Example Humanities",
            grade="8",
            unit="Identity",
            lesson_number=2,
            lesson_title="Interpreting Perspective",
            duration_minutes=10,
            essential_question=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
        ),
        learning_target=GroundedStatement(text="Analyze evidence."),
        language_objective=GroundedStatement(
            availability=Availability.UNAVAILABLE
        ),
        instructional_resources=[
            InstructionalResource(
                id="novel",
                title="Class Novel",
                resource_type="Novel",
                availability=Availability.UNAVAILABLE,
            )
        ],
        agenda=Agenda(
            selected_duration_minutes=10,
            items=[
                AgendaItem(
                    id="agenda-1",
                    sequence=1,
                    title="Discuss the text",
                    start_offset_minutes=0,
                    end_offset_minutes=10,
                    duration_minutes=10,
                    lesson_block_reference="block-1",
                    slide_references=["slide-1"],
                )
            ],
        ),
        lesson_blocks=[block],
        exit_ticket=ExitTicket(
            prompt=GroundedStatement(
                availability=Availability.UNAVAILABLE
            ),
            timing=TimingMetadata(duration_minutes=0),
        ),
        teacher_reflection=TeacherReflection(),
        source_digest="digest",
    )


def test_schema_is_curriculum_agnostic_and_supports_generic_resources() -> None:
    lesson = canonical_lesson()
    schema = CanonicalLesson.model_json_schema()

    assert lesson.lesson_information.curriculum == "Example Humanities"
    assert lesson.instructional_resources[0].resource_type == "Novel"
    assert "ckla" not in str(schema).casefold()


def test_agenda_is_contiguous_and_totals_selected_duration() -> None:
    with pytest.raises(ValidationError, match="agenda timing must total"):
        Agenda(
            selected_duration_minutes=20,
            items=[
                AgendaItem(
                    id="one",
                    sequence=1,
                    title="One",
                    start_offset_minutes=0,
                    end_offset_minutes=10,
                    duration_minutes=10,
                    lesson_block_reference="block",
                )
            ],
        )


def test_unavailable_question_rejects_asserted_answers() -> None:
    with pytest.raises(ValidationError, match="cannot assert answers"):
        TeacherQuestion(
            id="q1",
            question_text="What does the text reveal?",
            question_type="inferential",
            bloom_level="analyze",
            difficulty="grade_level",
            estimated_discussion_time_minutes=2,
            response_format="oral",
            expected_answers=[
                ExpectedAnswer(answer="Unsupported answer")
            ],
            answer_availability=Availability.UNAVAILABLE,
        )


def test_reading_chunk_preserves_unavailable_resource_boundary() -> None:
    chunk = ReadingChunk(
        id="chunk-1",
        title="Assigned reading",
        purpose="Analyze perspective.",
        instructional_resource_ids=["novel"],
        reader_page_references=["12–18"],
        reading_mode="unavailable",
        timing=TimingMetadata(duration_minutes=8),
        source_availability=Availability.UNAVAILABLE,
    )

    assert chunk.reader_page_references == ["12–18"]
    assert chunk.evidence == []
    assert chunk.expected_answers == []


def test_agenda_slide_references_must_match_instructional_mappings() -> None:
    lesson = canonical_lesson().model_copy(deep=True)
    lesson.agenda.items[0].slide_references = ["invented-slide"]

    with pytest.raises(ValidationError, match="agenda slide references"):
        CanonicalLesson.model_validate(lesson.model_dump())
