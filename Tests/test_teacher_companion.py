"""Tests for optional Teacher Companion Guide v1 generation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.teacheros import LessonPipelineInput, LessonRequest, TeacherOS
from brain.teacher_companion_validator import TeacherCompanionValidator
from schemas.teacher_companion_schema import (
    SOURCE_EVIDENCE_MARKER,
    CompanionConcept,
    CompanionSourceBasis,
    GroundedCurriculumFact,
    MasteryDescription,
    MisconceptionGuidance,
    StudentQuestionGuide,
    TeacherCompanionGuide,
    VocabularyGuidance,
)


def pipeline_input() -> LessonPipelineInput:
    return LessonPipelineInput(
        request=LessonRequest(
            request_id="ckla-grade-8-unit-1-lesson-1",
            curriculum_name="CKLA",
            grade="8",
            unit="1",
            lesson_number=1,
        ),
        lesson_title="Close Reading: First Story",
        teacher_guide_lesson_text=(
            "Teach students to cite textual evidence. Ask what makes evidence "
            "relevant and sufficient."
        ),
        objectives=["Cite textual evidence."],
        standards=["RL.8.1"],
        materials=["Student Reader", "Activity Page 1.1"],
        homework=["Read pages 12–18."],
        reader_page_references=["12–18"],
        activity_book_references=["1.1"],
        source_references=["TG pp. 1–2"],
    )


def misconception() -> MisconceptionGuidance:
    return MisconceptionGuidance(
        misconception="Any detail counts as strong evidence.",
        why_students_may_have_it=(
            "Students may select the first related detail they notice."
        ),
        exact_teacher_correction=(
            "A detail is strong evidence only when it directly supports the claim."
        ),
    )


def question(**changes) -> StudentQuestionGuide:
    values = {
        "exact_question": "What makes evidence relevant and sufficient?",
        "why_the_question_is_asked": (
            "It checks whether students can evaluate evidence, not merely locate it."
        ),
        "possible_student_answers": [
            "It directly supports the claim.",
            "It includes enough information to justify the reasoning.",
            "It is connected to the exact idea being discussed.",
        ],
        "excellent_model_answer": (
            "Evidence is relevant when it directly supports the claim and "
            "sufficient when there is enough of it to justify the reasoning."
        ),
        "why_the_model_answer_is_correct": (
            "It distinguishes the relationship of evidence from the amount needed."
        ),
        "what_the_teacher_should_listen_for": [
            "A direct connection between evidence and claim.",
            "Recognition that one weak detail may not be sufficient.",
        ],
        "likely_misconceptions": [misconception()],
        "scaffolded_follow_up_questions": [
            "What claim are you trying to support?",
            "How does this detail connect to that claim?",
        ],
        "extension_question": (
            "How could two relevant details be stronger than one?"
        ),
        "answer_basis": "teacher_guide",
        "source_references": ["TG pp. 1–2"],
    }
    values.update(changes)
    return StudentQuestionGuide(**values)


def guide(prepared: LessonPipelineInput | None = None, **changes) -> TeacherCompanionGuide:
    prepared = prepared or pipeline_input()
    request = prepared.request
    values = {
        "request_id": request.request_id,
        "source_basis": CompanionSourceBasis(
            curriculum_name=request.curriculum_name,
            grade=request.grade,
            unit=request.unit,
            lesson_number=request.lesson_number,
            lesson_title=prepared.lesson_title,
            objectives=prepared.objectives,
            standards=prepared.standards,
            materials=prepared.materials,
            homework=prepared.homework,
            reader_page_references=prepared.reader_page_references,
            activity_book_references=prepared.activity_book_references,
            source_references=prepared.source_references,
            student_reader_text_available=False,
        ),
        "teaching_overview": (
            "Prepare students to select and explain evidence in relation to a claim."
        ),
        "why_this_lesson_matters": (
            "Evidence-based reasoning supports reading, discussion, and writing."
        ),
        "curriculum_facts": [
            GroundedCurriculumFact(
                fact="The lesson requires students to cite textual evidence.",
                source_references=[prepared.source_references[0]],
            )
        ],
        "generated_instructional_guidance": [
            "Model the difference between a related detail and direct support."
        ],
        "required_concepts": [
            CompanionConcept(
                name="Textual evidence",
                what_to_teach="Evidence must support a specific claim.",
                why_it_matters="Students need evidence to justify interpretations.",
                how_to_teach="Think aloud while matching a detail to a claim.",
                educational_terminology=["claim", "relevant", "sufficient"],
            )
        ],
        "background_knowledge": [
            "A claim is an idea that requires support."
        ],
        "vocabulary_guidance": [
            VocabularyGuidance(
                term="relevant",
                meaning_for_teacher="Directly connected to the claim.",
                student_friendly_explanation="It helps prove the exact point.",
                how_to_teach="Compare a connected detail with an unrelated detail.",
                what_to_listen_for="Students explain the connection to the claim.",
            )
        ],
        "teacher_coaching": [
            "Ask students to explain why evidence supports the claim."
        ],
        "misconceptions_and_corrections": [misconception()],
        "student_supports": [
            "Use the frame: This evidence supports the claim because ___."
        ],
        "student_questions": [
            question(source_references=[prepared.source_references[0]])
        ],
        "mastery": MasteryDescription(
            mastery_statement=(
                "Students select relevant evidence and explain how it supports a claim."
            ),
            observable_indicators=[
                "The selected detail directly relates to the claim."
            ],
            evidence_to_collect=[
                "A spoken or written explanation connecting evidence to the claim."
            ],
        ),
        "grounding_notes": [
            "Student Reader text was unavailable; no story evidence was generated."
        ],
    }
    values.update(changes)
    return TeacherCompanionGuide(**values)


class CompanionClient:
    def __init__(self, output: TeacherCompanionGuide):
        self.output = output
        self.calls = 0
        self.last_usage = {"total_tokens": 10}

    def generate(self, *, schema, instructions, input_data):
        self.calls += 1
        assert schema is TeacherCompanionGuide
        assert "Never leave a student question unanswered" in instructions
        assert isinstance(input_data, LessonPipelineInput)
        return self.output


def teacheros(tmp_path, output: TeacherCompanionGuide) -> tuple[TeacherOS, CompanionClient]:
    client = CompanionClient(output)
    service = TeacherOS(
        project_root=tmp_path,
        database_path=tmp_path / "library.sqlite3",
        generation_output_directory=tmp_path / "runs",
        openai_client=client,
    )
    return service, client


def test_schema_requires_complete_question_and_answer_fields() -> None:
    restored = TeacherCompanionGuide.model_validate_json(guide().model_dump_json())
    assert restored.student_questions[0].excellent_model_answer
    assert len(restored.student_questions[0].possible_student_answers) == 3

    with pytest.raises(ValidationError):
        question(possible_student_answers=["Only one answer"])
    with pytest.raises(ValidationError):
        question(excellent_model_answer="")


def test_schema_rejects_unanswered_source_dependent_question() -> None:
    with pytest.raises(ValidationError, match="REQUIRES SOURCE EVIDENCE"):
        question(
            answer_basis="requires_student_reader_evidence",
            excellent_model_answer="The story proves the character is brave.",
        )

    valid = question(
        answer_basis="requires_student_reader_evidence",
        excellent_model_answer=(
            f"{SOURCE_EVIDENCE_MARKER} Locate details in the assigned text and "
            "verify the claim against those details."
        ),
    )
    assert valid.answer_basis == "requires_student_reader_evidence"


def test_missing_prepared_source_fails_before_generation(tmp_path) -> None:
    prepared = pipeline_input().model_copy(
        update={"teacher_guide_lesson_text": "", "source_references": []}
    )
    service, client = teacheros(tmp_path, guide())

    result = service.generate_teacher_companion(prepared)

    assert result.status == "failed"
    assert result.failed_stage == "source_validation"
    assert "prepared Teacher Guide lesson text" in result.errors[0]
    assert "source references" in result.errors[0]
    assert client.calls == 0


def test_generation_saves_json_markdown_and_validation(tmp_path) -> None:
    prepared = pipeline_input()
    service, client = teacheros(tmp_path, guide(prepared))

    result = service.generate_teacher_companion(prepared)

    assert result.status == "completed"
    assert result.validation_result == "pass"
    assert client.calls == 1
    assert [path.split("/")[-1] for path in result.output_files] == [
        "teacher_companion.json",
        "teacher_companion.md",
        "teacher_companion_validation.json",
    ]
    for path in result.output_files:
        assert (tmp_path / "runs" / prepared.request.request_id / path.split("/")[-1]).is_file()
    markdown = (
        tmp_path
        / "runs"
        / prepared.request.request_id
        / "teacher_companion.md"
    ).read_text(encoding="utf-8")
    assert "## Student Questions" in markdown
    assert "**Excellent model answer:**" in markdown
    report = json.loads(
        (
            tmp_path
            / "runs"
            / prepared.request.request_id
            / "teacher_companion_validation.json"
        ).read_text(encoding="utf-8")
    )
    assert report["status"] == "pass"


def test_resume_uses_existing_valid_guide_without_regeneration(tmp_path) -> None:
    prepared = pipeline_input()
    service, client = teacheros(tmp_path, guide(prepared))
    first = service.generate_teacher_companion(prepared)

    second = service.generate_teacher_companion(prepared)

    assert first.status == "completed"
    assert second.status == "completed"
    assert second.resumed is True
    assert client.calls == 1


def test_validation_failure_blocks_markdown_output(tmp_path) -> None:
    prepared = pipeline_input()
    invalid = guide(prepared)
    invalid.curriculum_facts[0].source_references = ["Invented Reader p. 99"]
    service, _ = teacheros(tmp_path, invalid)

    result = service.generate_teacher_companion(prepared)

    assert result.status == "failed"
    assert result.failed_stage == "teacher_companion_validator"
    assert result.validation_result == "fail"
    assert any("unsupported_curriculum_fact_source" in item for item in result.errors)
    run = tmp_path / "runs" / prepared.request.request_id
    assert (run / "teacher_companion.json").is_file()
    assert (run / "teacher_companion_validation.json").is_file()
    assert not (run / "teacher_companion.md").exists()


def test_validator_rejects_guide_for_a_different_prepared_lesson() -> None:
    prepared = pipeline_input()
    value = guide(prepared).model_copy(update={"request_id": "different"})

    report = TeacherCompanionValidator().validate(value, prepared)

    assert report.status == "fail"
    assert "request_identity" in {finding.code for finding in report.findings}


def test_generator_stamps_exact_prepared_source_basis(tmp_path) -> None:
    prepared = pipeline_input()
    drifted = guide(prepared)
    drifted.request_id = "invented"
    drifted.source_basis.objectives = ["Invented objective"]
    drifted.source_basis.reader_page_references = ["999"]
    drifted.source_basis.student_reader_text_available = True
    service, _ = teacheros(tmp_path, drifted)

    result = service.generate_teacher_companion(prepared)

    assert result.status == "completed"
    saved = TeacherCompanionGuide.model_validate_json(
        (
            tmp_path
            / "runs"
            / prepared.request.request_id
            / "teacher_companion.json"
        ).read_text(encoding="utf-8")
    )
    assert saved.request_id == prepared.request.request_id
    assert saved.source_basis.objectives == prepared.objectives
    assert (
        saved.source_basis.reader_page_references
        == prepared.reader_page_references
    )
    assert saved.source_basis.student_reader_text_available is False


def test_existing_lesson_generation_pipeline_remains_independent(tmp_path) -> None:
    from Tests.test_generation_pipeline import PipelineClient
    from Tests.test_teacheros import prepared_fixture

    service, _ = prepared_fixture(tmp_path)
    preparation = service.prepare_lesson(grade=8, unit=1, lesson_number=1)
    prepared = LessonPipelineInput.model_validate_json(
        open(preparation.output_files[0], encoding="utf-8").read()
    )
    service.openai_client = CompanionClient(guide(prepared))
    companion_result = service.generate_teacher_companion(prepared)
    assert companion_result.status == "completed"

    service.openai_client = PipelineClient()
    lesson_result = service.generate_lesson(grade=8, unit=1, lesson_number=1)

    assert lesson_result.status in {"completed", "completed_with_warnings"}
    assert "gamma_handoff_prompt_generator" in lesson_result.completed_stages
