"""Mock-only tests for Milestone 7 generation contracts and validation."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from brain.curriculum_reader import CurriculumReader
from brain.lesson_assembler import LessonAssembler
from brain.lesson_package_parser import parse_lesson_package
from brain.lesson_validator import LessonValidator
from brain.presentation_designer import PresentationDesigner
from config.settings import Settings
from schemas.analyzer_output_schema import CurriculumAnalyzerOutput
from schemas.generation_common import Finding, GenerationMetadata
from schemas.instruction_design_schema import InstructionDesign, InstructionSegment
from schemas.lesson_package_schema import CKLA_ATTRIBUTION, LessonPackage, LessonPackageMetadata
from schemas.reader_output_schema import CurriculumReaderOutput, LessonSection
from schemas.slide_specification_schema import SlideSpecification, SlideSpecificationItem
from schemas.presentation_design_schema import (PresentationDesignOutput, PresentationSlide, StudentView,
    TeacherNotes, SlideDesign, VisualPlan, InteractionPlan)
from schemas.generation_result_schema import LessonValidationReport
from services.openai_client import OpenAIClient
from Tests.test_teacheros import prepared_fixture
from pydantic import ValidationError


def reader() -> CurriculumReaderOutput:
    return CurriculumReaderOutput(request_id="r1", lesson_title="Lesson",
        lesson_sequence=["Required discussion"],
        sections=[LessonSection(section_id="one", day=1, sequence=1, title="Required discussion",
            source_references=["TG p. 1"])], objectives=["Analyze evidence"], standards=["RL.8.1"],
        homework=["Read pp. 2-3"], reader_references=["Reader pp. 2-3"],
        activity_book_references=["Activity Page 1.1"], source_references=["TG p. 1"])


def design() -> InstructionDesign:
    return InstructionDesign(request_id="r1", lesson_title="Lesson", objectives=["Analyze evidence"],
        standards=["RL.8.1"], segments=[InstructionSegment(segment_id="one", day=1, sequence=1,
        title="Required discussion", timing_minutes=10, source_references=["TG p. 1"])],
        homework=["Read pp. 2-3"], total_timing_minutes=10, source_references=["TG p. 1"])


def slide(notes="Notes") -> SlideSpecificationItem:
    return SlideSpecificationItem(slide_id="S01", sequence_number=1, slide_type="discussion",
        title="Required discussion", student_facing_content="Analyze evidence", speaker_notes=notes,
        timing=10, teacher_directions="Discuss.", source_references=["TG p. 1"],
        fidelity_classification="source_required")


def presentation() -> PresentationDesignOutput:
    return PresentationDesignOutput(request_id="r1", lesson_title="Lesson", slides=[PresentationSlide(
        slide_id="S01", sequence_number=1, slide_type="discussion",
        student_view=StudentView(title="Required discussion", prompt="How does evidence shape your view?",
            sentence_frames=["This is a window because …", "This is a mirror because …"],
            directions=["Discuss with a partner."]),
        teacher_notes=TeacherNotes(instructional_purpose="Connect identity and perspective.",
            teacher_script="Introduce windows and mirrors.", questions=["What feels familiar?"],
            anticipated_responses=["Experiences may be familiar or new."], eld_supports=["Rehearse with a partner."],
            pacing_notes="Allow two minutes.", transition="Invite two responses."),
        design=SlideDesign(layout="question_focus", max_words=45),
        visuals=VisualPlan(visual_required=True, visual_type="illustration",
            visual_description="A conceptual window beside a mirror", image_prompt="Editorial illustration of a window and mirror, no text",
            alt_text="A window beside a mirror, representing new and reflected experiences", placement="right"),
        interaction=InteractionPlan(interaction_type="turn_and_talk", duration_minutes=2,
            grouping="partners", response_mode="oral"), timing=10, source_references=["TG p. 1"],
        fidelity_classification="source_required")])


def package(notes="Notes") -> LessonPackage:
    return LessonPackage(package_id="r1", lesson_metadata=LessonPackageMetadata(title="Lesson", grade="8",
        unit="1", lesson_number=1, objectives=["Analyze evidence"], standards=["RL.8.1"],
        attribution=CKLA_ATTRIBUTION), lesson_overview="Analyze evidence", total_timing=10,
        slide_order=["S01"], slides=[slide(notes)], homework=[{"title": "Homework", "instructions": "Read pp. 2-3"}],
        activities=[{"activity_id": "A1", "title": "Required discussion", "instructions": "Discuss."}],
        activity_references=["Activity Page 1.1"], reader_references=["Reader pp. 2-3"],
        source_references=["TG p. 1"], generation_metadata=GenerationMetadata(request_id="r1",
        model="test-model", attribution=CKLA_ATTRIBUTION))


def test_stage_schemas_and_parser_handoff_preserve_references() -> None:
    specification = SlideSpecification(request_id="r1", slides=[slide()])
    assert specification.slides[0].source_references == ["TG p. 1"]
    lesson = parse_lesson_package(package().model_dump(mode="json"))
    assert lesson.slides[0].source_references == ["TG p. 1"]
    assert lesson.homework[0].instructions == "Read pp. 2-3"


def test_validator_reports_missing_notes_timing_and_unsupported_quote() -> None:
    item = slide("")
    item.fidelity_classification = "teacheros_added"
    item.student_facing_content = 'Say “invented words.”'
    value = package("")
    value.slides = [item]
    value.total_timing = 12
    report = LessonValidator().validate(value, reader(), design())
    codes = {finding.code for finding in report.findings}
    assert {"missing_speaker_notes", "possible_invented_quotation", "timing_total"} <= codes
    assert report.status == "fail"


def test_prompt_loading_and_structured_response_parsing_are_mockable() -> None:
    output = reader()
    sdk = MagicMock()
    sdk.responses.parse.return_value = SimpleNamespace(output_parsed=output, usage=None)
    client = OpenAIClient(settings=Settings(openai_api_key="test", teacheros_model="test-model"), client=sdk)
    result = CurriculumReader(client).run({"request": "r1"})
    assert result == output
    assert "Never invent" in CurriculumReader(client).load_prompt()
    assert sdk.responses.parse.call_args.kwargs["text_format"] is CurriculumReaderOutput


def test_presentation_prompt_and_structured_response_parsing_are_mockable() -> None:
    output = presentation()
    sdk = MagicMock()
    sdk.responses.parse.return_value = SimpleNamespace(output_parsed=output, usage=None)
    client = OpenAIClient(settings=Settings(openai_api_key="test", teacheros_model="test-model"), client=sdk)
    result = PresentationDesigner(client).run({"instruction_design": design().model_dump()})
    assert result == output
    assert "Student slides" not in PresentationDesigner(client).load_prompt()  # prompt uses the schema's Student View language
    assert "STUDENT VIEW" in PresentationDesigner(client).load_prompt()
    assert sdk.responses.parse.call_args.kwargs["text_format"] is PresentationDesignOutput


def test_analyzer_inferences_are_explicit() -> None:
    result = CurriculumAnalyzerOutput(request_id="r1",
        central_learning_goal=Finding(text="Analyze evidence", source_references=["TG p. 1"]),
        likely_misconceptions=[Finding(text="May confuse inference and fact", is_inference=True)])
    assert result.likely_misconceptions[0].is_inference is True


class PipelineClient:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.calls = []
        self.last_usage = {}
        self.settings = SimpleNamespace(teacheros_model="test-model")

    def generate(self, *, schema, instructions, input_data):
        self.calls.append(schema.__name__)
        if len(self.calls) == self.fail_at:
            raise RuntimeError("synthetic stage failure")
        if schema is CurriculumReaderOutput:
            return CurriculumReaderOutput(request_id="ckla-grade-8-unit-1-lesson-1", lesson_title="Lesson",
                objectives=[], standards=[], homework=[], reader_references=[], activity_book_references=[],
                source_references=["TG p. 1"])
        if schema is CurriculumAnalyzerOutput:
            return CurriculumAnalyzerOutput(request_id="ckla-grade-8-unit-1-lesson-1",
                central_learning_goal=Finding(text="Source-aligned goal", source_references=["TG p. 1"]))
        if schema is InstructionDesign:
            return InstructionDesign(request_id="ckla-grade-8-unit-1-lesson-1", total_timing_minutes=5,
                source_references=["TG p. 1"])
        if schema is PresentationDesignOutput:
            value = presentation()
            value.request_id = "ckla-grade-8-unit-1-lesson-1"
            return value
        if schema is LessonPackage:
            value = package()
            value.package_id = value.generation_metadata.request_id = "ckla-grade-8-unit-1-lesson-1"
            value.lesson_metadata.objectives = []
            value.lesson_metadata.standards = []
            value.homework = []
            value.activity_references = []
            value.reader_references = []
            return value
        raise AssertionError(schema)


def test_orchestration_order_and_resume_avoid_repeat_calls(tmp_path) -> None:
    teacheros, _ = prepared_fixture(tmp_path)
    client = PipelineClient()
    teacheros.openai_client = client
    teacheros.generation_output_directory = tmp_path / "runs"
    first = teacheros.generate_lesson(grade=8, unit=1, lesson_number=1)
    assert first.status in {"completed", "completed_with_warnings"}
    assert client.calls == ["CurriculumReaderOutput", "CurriculumAnalyzerOutput", "InstructionDesign",
                            "PresentationDesignOutput"]
    run = tmp_path / "runs/ckla-grade-8-unit-1-lesson-1"
    assert (run / "04_presentation_design.json").is_file()
    assert not (run / "04_slide_specification.json").exists()
    assert (run / "RendererPromptBundle.json").is_file()
    assert (run / "RendererPromptBundle.md").is_file()
    prompt_bundle = json.loads((run / "RendererPromptBundle.json").read_text(encoding="utf-8"))
    assert prompt_bundle["metadata"]["request_id"] == "ckla-grade-8-unit-1-lesson-1"
    assert prompt_bundle["metadata"]["slide_ids"] == ["S01"]
    assert "presentation_renderer_prompt_generator" in first.completed_stages
    client.calls.clear()
    second = teacheros.generate_lesson(grade=8, unit=1, lesson_number=1)
    assert second.status in {"completed", "completed_with_warnings"}
    assert client.calls == []


def test_stage_failure_preserves_completed_outputs(tmp_path) -> None:
    teacheros, _ = prepared_fixture(tmp_path)
    teacheros.generation_output_directory = tmp_path / "runs"
    teacheros.openai_client = PipelineClient(fail_at=3)
    result = teacheros.generate_lesson(grade=8, unit=1, lesson_number=1)
    assert result.status == "failed"
    assert result.failed_stage == "instruction_designer"
    run = tmp_path / "runs/ckla-grade-8-unit-1-lesson-1"
    assert (run / "01_reader_output.json").is_file()
    assert (run / "02_analyzer_output.json").is_file()
    assert not (run / "03_instruction_design.json").exists()


def test_prompt_bundle_is_not_written_when_validation_fails(tmp_path, monkeypatch) -> None:
    teacheros, _ = prepared_fixture(tmp_path)
    teacheros.generation_output_directory = tmp_path / "runs"
    teacheros.openai_client = PipelineClient()
    monkeypatch.setattr(
        LessonValidator,
        "validate",
        lambda *args, **kwargs: LessonValidationReport(
            status="fail",
            timing_total_minutes=0,
            slide_count=1,
        ),
    )

    result = teacheros.generate_lesson(grade=8, unit=1, lesson_number=1)
    run = tmp_path / "runs/ckla-grade-8-unit-1-lesson-1"
    assert result.status == "failed"
    assert result.failed_stage == "lesson_validator"
    assert not (run / "RendererPromptBundle.json").exists()
    assert not (run / "RendererPromptBundle.md").exists()


def test_assembler_merges_validated_outputs_without_api_or_attribution_drift() -> None:
    client = MagicMock()
    client.settings.teacheros_model = "test-model"
    result = LessonAssembler(client).run({
        "pipeline_input": {"request": {"request_id": "r1", "curriculum_name": "CKLA", "grade": "8",
            "unit": "1", "lesson_number": 1}, "lesson_title": "Lesson", "source_references": ["TG p. 1"],
            "extraction_warnings": []},
        "reader": reader().model_dump(),
        "analyzer": CurriculumAnalyzerOutput(request_id="r1",
            central_learning_goal=Finding(text="Analyze evidence", source_references=["TG p. 1"])).model_dump(),
        "instruction_design": design().model_dump(),
        "presentation_design": presentation().model_dump(),
    })
    assert result.lesson_metadata.attribution == CKLA_ATTRIBUTION
    assert result.slide_order == ["S01"]
    assert result.slides[0].title == "Required discussion"
    assert "How does evidence" in result.slides[0].student_facing_content
    assert "Instructional Purpose" in result.slides[0].speaker_notes
    assert result.slides[0].source_references == ["TG p. 1"]
    client.generate.assert_not_called()


def test_presentation_schema_round_trip_and_separation() -> None:
    value = presentation()
    restored = PresentationDesignOutput.model_validate_json(value.model_dump_json())
    assert restored == value
    assert "Introduce windows" not in restored.slides[0].student_view.all_text()
    assert "Introduce windows" in restored.slides[0].teacher_notes.as_text()


def test_presentation_quality_and_day_divider_timing() -> None:
    value = presentation()
    value.slides[0].student_view.body_text = " ".join(["word"] * 50)
    value.slides[0].visuals.alt_text = None
    findings = LessonValidator().presentation_findings(value)
    assert {item.code for item in findings} >= {"student_word_count", "visual_alt_text"}

    divider = value.slides[0].model_copy(deep=True)
    divider.slide_id = "S00"
    divider.sequence_number = 1
    divider.slide_type = "day_divider"
    divider.timing = 45
    value.slides[0].sequence_number = 2
    value.slides = [divider, value.slides[0]]
    client = MagicMock(); client.settings.teacheros_model = "test-model"
    result = LessonAssembler(client).run({
        "pipeline_input": {"request": {"request_id": "r1", "curriculum_name": "CKLA", "grade": "8", "unit": "1", "lesson_number": 1}, "source_references": ["TG p. 1"]},
        "reader": reader().model_dump(), "analyzer": CurriculumAnalyzerOutput(request_id="r1", central_learning_goal=Finding(text="Analyze evidence", source_references=["TG p. 1"])).model_dump(),
        "instruction_design": design().model_dump(), "presentation_design": value.model_dump()})
    assert result.total_timing == 10
    assert result.slides[0].timing is None


def test_presentation_timing_is_semantic_by_slide_type() -> None:
    divider = presentation().slides[0].model_dump()
    divider.update(slide_type="day_divider", timing=0)
    divider["design"]["layout"] = "day_divider"
    assert PresentationSlide.model_validate(divider).timing == 0
    divider["timing"] = None
    assert PresentationSlide.model_validate(divider).timing is None
    divider["timing"] = 25
    assert PresentationSlide.model_validate(divider).timing == 0

    normal = presentation().slides[0].model_dump()
    normal["timing"] = 0
    with pytest.raises(ValidationError, match="timing must be positive"):
        PresentationSlide.model_validate(normal)
    normal["timing"] = -1
    with pytest.raises(ValidationError):
        PresentationSlide.model_validate(normal)


def test_day_dividers_are_excluded_from_daily_and_package_totals() -> None:
    value = presentation()
    divider_data = value.slides[0].model_dump()
    divider_data.update(slide_id="D01", sequence_number=1, slide_type="day_divider", timing=25, day=1)
    divider_data["design"]["layout"] = "day_divider"
    divider = PresentationSlide.model_validate(divider_data)
    value.slides[0].sequence_number = 2
    value.slides[0].day = 1
    value.slides = [divider, value.slides[0]]
    client = MagicMock(); client.settings.teacheros_model = "test-model"
    assembled = LessonAssembler(client).run({
        "pipeline_input": {"request": {"request_id":"r1","curriculum_name":"CKLA","grade":"8","unit":"1","lesson_number":1}, "source_references":["TG p. 1"]},
        "reader": reader().model_dump(), "analyzer": CurriculumAnalyzerOutput(request_id="r1", central_learning_goal=Finding(text="Analyze evidence", source_references=["TG p. 1"])).model_dump(),
        "instruction_design": design().model_dump(), "presentation_design": value.model_dump()})
    assert divider.timing == 0
    assert assembled.slides[0].timing is None
    assert assembled.total_timing == 10
    report = LessonValidator().validate(assembled, reader(), design(), value)
    assert report.timing_total_minutes == 10
    assert not any(f.code == "day_timing_total" for f in report.findings)
