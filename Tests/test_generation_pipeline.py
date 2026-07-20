"""Mock-only tests for Milestone 7 generation contracts and validation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from brain.curriculum_reader import CurriculumReader
from brain.lesson_assembler import LessonAssembler
from brain.lesson_package_parser import parse_lesson_package
from brain.lesson_validator import LessonValidator
from config.settings import Settings
from schemas.analyzer_output_schema import CurriculumAnalyzerOutput
from schemas.generation_common import Finding, GenerationMetadata
from schemas.instruction_design_schema import InstructionDesign, InstructionSegment
from schemas.lesson_package_schema import CKLA_ATTRIBUTION, LessonPackage, LessonPackageMetadata
from schemas.reader_output_schema import CurriculumReaderOutput, LessonSection
from schemas.slide_specification_schema import SlideSpecification, SlideSpecificationItem
from services.openai_client import OpenAIClient
from Tests.test_teacheros import prepared_fixture


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
        if schema is SlideSpecification:
            return SlideSpecification(request_id="ckla-grade-8-unit-1-lesson-1", slides=[slide()])
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
                            "SlideSpecification"]
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
        "slide_specification": SlideSpecification(request_id="r1", slides=[slide()]).model_dump(),
    })
    assert result.lesson_metadata.attribution == CKLA_ATTRIBUTION
    assert result.slide_order == ["S01"]
    assert result.slides[0] == slide()
    client.generate.assert_not_called()
