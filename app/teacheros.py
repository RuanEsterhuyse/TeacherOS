"""Deterministic orchestration for preparing curriculum lessons for TeacherOS."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError

from curriculum.lesson_locator import CKLALessonLocator
from curriculum.library import CurriculumLibrary
from schemas.curriculum_schema import CurriculumIndex, LessonIndexEntry, LessonSource
from schemas.generation_result_schema import GenerationResult, LessonValidationReport
from schemas.teacher_companion_schema import TeacherCompanionGenerationResult


PreparationStatus = Literal["completed", "completed_with_warnings", "failed"]


class LessonRequest(BaseModel):
    """The stable identity of one requested curriculum lesson."""

    request_id: str
    curriculum_name: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)


class TeacherGuidePageRange(BaseModel):
    """Both machine-oriented and human-oriented PDF page coordinates."""

    start_pdf_page: int = Field(ge=0)
    end_pdf_page: int = Field(ge=0)
    display_start_page: int = Field(ge=1)
    display_end_page: int = Field(ge=1)
    printed_start_page: Optional[int] = Field(default=None, ge=1)
    printed_end_page: Optional[int] = Field(default=None, ge=1)


class LessonMetadata(BaseModel):
    """Metadata copied verbatim from the saved curriculum index."""

    objectives: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    duration: Optional[int] = Field(default=None, ge=0)
    reader_page_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    assessment_references: list[str] = Field(default_factory=list)
    pdf_page_references: list[int] = Field(default_factory=list)


class LessonPipelineInput(BaseModel):
    """Validated handoff to the existing instructional pipeline."""

    request: LessonRequest
    lesson_title: Optional[str] = None
    teacher_guide_lesson_text: str
    objectives: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    duration: Optional[int] = Field(default=None, ge=0)
    reader_page_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    assessment_references: list[str] = Field(default_factory=list)
    pdf_page_references: list[int] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)


class LessonPreparationResult(BaseModel):
    """Outcome of deterministic lesson preparation."""

    request_id: str
    curriculum_name: str
    grade: str
    unit: str
    lesson_number: int
    lesson_title: Optional[str] = None
    status: PreparationStatus
    lesson_source: Optional[LessonSource] = None
    lesson_metadata: Optional[LessonMetadata] = None
    teacher_guide_page_range: Optional[TeacherGuidePageRange] = None
    student_reader_references: list[str] = Field(default_factory=list)
    activity_book_references: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    next_required_stage: Optional[str] = None


class TeacherOS:
    """Connect the curriculum library and locator to the instructional handoff."""

    def __init__(
        self,
        *,
        project_root: Optional[Union[str, Path]] = None,
        database_path: Union[str, Path] = "data/curriculum/library.sqlite3",
        index_directory: Union[str, Path] = "data/indexes",
        output_directory: Union[str, Path] = "output/pipeline_inputs",
        library: Optional[CurriculumLibrary] = None,
        locator: Optional[CKLALessonLocator] = None,
        generation_output_directory: Union[str, Path] = "output/generation_runs",
        openai_client: Any = None,
    ) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.library = library or CurriculumLibrary(database_path, self.project_root)
        index_path = Path(index_directory)
        if not index_path.is_absolute():
            index_path = self.project_root / index_path
        self.locator = locator or CKLALessonLocator(index_directory=index_path)
        output_path = Path(output_directory)
        self.output_directory = output_path if output_path.is_absolute() else self.project_root / output_path
        generation_path = Path(generation_output_directory)
        self.generation_output_directory = generation_path if generation_path.is_absolute() else self.project_root / generation_path
        self.openai_client = openai_client

    @staticmethod
    def _slug(value: str | int) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")

    def create_lesson_request(
        self, *, curriculum_name: str = "CKLA", grade: Union[str, int], unit: Union[str, int],
        lesson_number: int,
    ) -> LessonRequest:
        curriculum = curriculum_name.strip()
        request_id = f"{self._slug(curriculum)}-grade-{grade}-unit-{unit}-lesson-{lesson_number}"
        return LessonRequest(request_id=request_id, curriculum_name=curriculum, grade=str(grade),
                             unit=str(unit), lesson_number=lesson_number)

    def _load_index(self, request: LessonRequest, curriculum) -> CurriculumIndex:
        path = self.locator.default_index_path(curriculum)
        if not path.is_file():
            raise FileNotFoundError(f"Curriculum index not found: {path}")
        index = self.locator.load_index(path)
        identity = index.curriculum
        if (identity.curriculum_name, identity.grade, identity.unit) != (
            request.curriculum_name, request.grade, request.unit
        ):
            raise ValueError(f"Curriculum index identity does not match request: {path}")
        return index

    def prepare_lesson_source(
        self, request: LessonRequest, index: CurriculumIndex, teacher_guide_path: Union[str, Path],
    ) -> LessonSource:
        return self.locator.extract_lesson_source(index, request.lesson_number, teacher_guide_path)

    @staticmethod
    def _metadata(entry: LessonIndexEntry) -> LessonMetadata:
        return LessonMetadata(
            objectives=entry.lesson_objective, standards=entry.standards, materials=entry.materials,
            homework=entry.homework, duration=entry.lesson_duration,
            reader_page_references=entry.reader_pages,
            activity_book_references=entry.activity_book_pages,
            assessment_references=entry.assessment_references,
            pdf_page_references=entry.source_page_numbers,
        )

    def build_pipeline_input(
        self, request: LessonRequest, lesson_source: LessonSource, lesson_metadata: LessonMetadata,
        warnings: Optional[list[str]] = None,
    ) -> LessonPipelineInput:
        return LessonPipelineInput(
            request=request, lesson_title=lesson_source.lesson_title,
            teacher_guide_lesson_text=lesson_source.extracted_text,
            objectives=lesson_metadata.objectives, standards=lesson_metadata.standards,
            materials=lesson_metadata.materials, homework=lesson_metadata.homework,
            duration=lesson_metadata.duration,
            reader_page_references=lesson_metadata.reader_page_references,
            activity_book_references=lesson_metadata.activity_book_references,
            assessment_references=lesson_metadata.assessment_references,
            pdf_page_references=lesson_metadata.pdf_page_references,
            source_references=lesson_source.source_references,
            extraction_warnings=list(warnings or []),
        )

    @staticmethod
    def validate_pipeline_input(value: Union[LessonPipelineInput, dict]) -> LessonPipelineInput:
        return LessonPipelineInput.model_validate(value)

    @staticmethod
    def get_creation_status(result: LessonPreparationResult) -> PreparationStatus:
        return result.status

    def _output_path(self, request: LessonRequest) -> Path:
        filename = (
            f"{self._slug(request.curriculum_name)}_grade_{self._slug(request.grade)}_"
            f"unit_{self._slug(request.unit)}_lesson_{request.lesson_number}_pipeline_input.json"
        )
        return self.output_directory / filename

    def prepare_lesson(
        self, *, curriculum_name: str = "CKLA", grade: Union[str, int] = 8,
        unit: Union[str, int] = 1, lesson_number: int = 1,
    ) -> LessonPreparationResult:
        """Prepare and persist one exact lesson source, returning failures as data."""
        try:
            request = self.create_lesson_request(curriculum_name=curriculum_name, grade=grade,
                                                 unit=unit, lesson_number=lesson_number)
        except ValidationError as error:
            request_id = f"invalid-lesson-request-{self._slug(lesson_number)}"
            return LessonPreparationResult(request_id=request_id, curriculum_name=str(curriculum_name),
                grade=str(grade), unit=str(unit), lesson_number=lesson_number, status="failed",
                errors=[f"request validation failed: {error}"], next_required_stage="correct_lesson_request")

        base = dict(request_id=request.request_id, curriculum_name=request.curriculum_name,
                    grade=request.grade, unit=request.unit, lesson_number=request.lesson_number)
        try:
            curriculum = self.library.get_unit(request.curriculum_name, request.grade, request.unit)
        except (KeyError, ValueError) as error:
            return LessonPreparationResult(**base, status="failed",
                errors=[f"curriculum lookup failed: {error}"], next_required_stage="register_curriculum")

        guide = self.library.resolve_path(curriculum.teacher_guide_path)
        if not guide.is_file():
            return LessonPreparationResult(**base, status="failed",
                errors=[f"source file validation failed: Teacher Guide PDF not found: {guide}"],
                next_required_stage="restore_curriculum_files")
        try:
            index = self._load_index(request, curriculum)
        except FileNotFoundError as error:
            return LessonPreparationResult(**base, status="failed", errors=[f"index loading failed: {error}"],
                                           next_required_stage="build_curriculum_index")
        except ValueError as error:
            return LessonPreparationResult(**base, status="failed", errors=[f"index loading failed: {error}"],
                                           next_required_stage="rebuild_curriculum_index")
        try:
            entry = self.locator.get_lesson_entry(index, request.lesson_number)
        except KeyError as error:
            return LessonPreparationResult(**base, status="failed", errors=[f"lesson selection failed: {error}"],
                                           next_required_stage="select_valid_lesson")
        try:
            source = self.prepare_lesson_source(request, index, guide)
        except (FileNotFoundError, ValueError) as error:
            return LessonPreparationResult(**base, lesson_title=entry.lesson_title, status="failed",
                errors=[f"lesson text extraction failed: {error}"], next_required_stage="repair_source_or_index")

        metadata = self._metadata(entry)
        warnings = list(dict.fromkeys(index.extraction_warnings + source.warnings))
        missing = []
        for field, value in (
            ("lesson title", entry.lesson_title), ("objectives", metadata.objectives),
            ("standards", metadata.standards), ("materials", metadata.materials),
            ("homework", metadata.homework), ("duration", metadata.duration),
            ("reader page references", metadata.reader_page_references),
            ("activity book references", metadata.activity_book_references),
            ("assessment references", metadata.assessment_references),
        ):
            if value is None or value == []:
                missing.append(field)
        if missing:
            warnings.append(f"Incomplete indexed metadata; unavailable fields: {', '.join(missing)}.")
        for label, stored_path in (("Student Reader", curriculum.student_reader_path),
                                   ("Activity Book", curriculum.activity_book_path)):
            if stored_path and not self.library.resolve_path(stored_path).is_file():
                warnings.append(f"{label} file not found: {self.library.resolve_path(stored_path)}")

        pipeline_input = self.build_pipeline_input(request, source, metadata, warnings)
        try:
            pipeline_input = self.validate_pipeline_input(pipeline_input)
            target = self._output_path(request)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.parent.is_dir():
                raise OSError(f"Output path is not a directory: {target.parent}")
            target.write_text(pipeline_input.model_dump_json(indent=2) + "\n", encoding="utf-8")
        except (OSError, ValidationError, ValueError) as error:
            return LessonPreparationResult(**base, lesson_title=entry.lesson_title, status="failed",
                lesson_source=source, lesson_metadata=metadata,
                errors=[f"pipeline input output failed: {error}"], warnings=warnings,
                next_required_stage="repair_pipeline_output")

        page_range = TeacherGuidePageRange(
            start_pdf_page=entry.start_pdf_page, end_pdf_page=entry.end_pdf_page,
            display_start_page=entry.start_pdf_page + 1, display_end_page=entry.end_pdf_page + 1,
            printed_start_page=entry.start_printed_page, printed_end_page=entry.end_printed_page,
        )
        return LessonPreparationResult(
            **base, lesson_title=entry.lesson_title,
            status="completed_with_warnings" if warnings else "completed",
            lesson_source=source, lesson_metadata=metadata, teacher_guide_page_range=page_range,
            student_reader_references=metadata.reader_page_references,
            activity_book_references=metadata.activity_book_references,
            source_references=source.source_references, warnings=warnings,
            output_files=[str(target)], next_required_stage="curriculum_reader",
        )

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def _read_model(path: Path, schema):
        return schema.model_validate_json(path.read_text(encoding="utf-8"))

    def generate_teacher_companion(
        self,
        pipeline_input: LessonPipelineInput | dict,
        *,
        resume: bool = True,
        output_directory: str | Path | None = None,
    ) -> TeacherCompanionGenerationResult:
        """Generate an optional guide from one already prepared lesson input."""
        try:
            prepared = self.validate_pipeline_input(pipeline_input)
        except (ValidationError, TypeError, ValueError) as error:
            return TeacherCompanionGenerationResult(
                request_id="invalid-teacher-companion-request",
                status="failed",
                output_directory=str(output_directory or self.generation_output_directory),
                failed_stage="validate_pipeline_input",
                errors=[f"prepared lesson input is invalid: {error}"],
            )

        request_id = prepared.request.request_id
        target_directory = (
            Path(output_directory)
            if output_directory is not None
            else self.generation_output_directory / request_id
        )
        if not target_directory.is_absolute():
            target_directory = self.project_root / target_directory
        guide_path = target_directory / "teacher_companion.json"
        markdown_path = target_directory / "teacher_companion.md"
        validation_path = target_directory / "teacher_companion_validation.json"
        base = {
            "request_id": request_id,
            "output_directory": str(target_directory),
        }

        missing_sources = []
        if not (prepared.lesson_title or "").strip():
            missing_sources.append("lesson title")
        if not prepared.teacher_guide_lesson_text.strip():
            missing_sources.append("prepared Teacher Guide lesson text")
        if not prepared.source_references:
            missing_sources.append("source references")
        if missing_sources:
            return TeacherCompanionGenerationResult(
                **base,
                status="failed",
                failed_stage="source_validation",
                errors=[
                    "required prepared source material is missing: "
                    + ", ".join(missing_sources)
                ],
            )

        from brain.teacher_companion_generator import TeacherCompanionGenerator
        from brain.teacher_companion_validator import TeacherCompanionValidator
        from config.settings import get_settings
        from renderer.teacher_companion_markdown import (
            render_teacher_companion_markdown,
        )
        from schemas.teacher_companion_schema import TeacherCompanionGuide
        from services.openai_client import OpenAIClient

        validator = TeacherCompanionValidator()
        if resume and guide_path.is_file():
            try:
                saved_guide = self._read_model(guide_path, TeacherCompanionGuide)
                saved_report = validator.validate(saved_guide, prepared)
                if saved_report.status != "fail":
                    target_directory.mkdir(parents=True, exist_ok=True)
                    markdown_path.write_text(
                        render_teacher_companion_markdown(saved_guide),
                        encoding="utf-8",
                    )
                    self._write_json(validation_path, saved_report)
                    return TeacherCompanionGenerationResult(
                        **base,
                        status=(
                            "completed_with_warnings"
                            if saved_report.status == "pass_with_warnings"
                            else "completed"
                        ),
                        completed_stages=[
                            "teacher_companion_resume",
                            "teacher_companion_validator",
                            "teacher_companion_markdown",
                        ],
                        output_files=[
                            str(guide_path),
                            str(markdown_path),
                            str(validation_path),
                        ],
                        validation_result=saved_report.status,
                        resumed=True,
                    )
            except (OSError, ValidationError, ValueError):
                pass

        try:
            client = self.openai_client or OpenAIClient(settings=get_settings())
            guide = TeacherCompanionGenerator(client).run(prepared)
            target_directory.mkdir(parents=True, exist_ok=True)
            self._write_json(guide_path, guide)
        except Exception as error:
            return TeacherCompanionGenerationResult(
                **base,
                status="failed",
                failed_stage="teacher_companion_generator",
                errors=[f"teacher companion generation failed: {error}"],
            )

        report = validator.validate(guide, prepared)
        self._write_json(validation_path, report)
        completed = ["teacher_companion_generator", "teacher_companion_validator"]
        if report.status == "fail":
            return TeacherCompanionGenerationResult(
                **base,
                status="failed",
                completed_stages=completed,
                failed_stage="teacher_companion_validator",
                errors=[
                    f"{finding.code}: {finding.message}"
                    for finding in report.findings
                    if finding.severity == "error"
                ],
                output_files=[str(guide_path), str(validation_path)],
                validation_result=report.status,
                usage=getattr(client, "last_usage", {}),
            )

        markdown_path.write_text(
            render_teacher_companion_markdown(guide),
            encoding="utf-8",
        )
        completed.append("teacher_companion_markdown")
        warnings = [
            finding.message
            for finding in report.findings
            if finding.severity == "warning"
        ]
        return TeacherCompanionGenerationResult(
            **base,
            status="completed_with_warnings" if warnings else "completed",
            completed_stages=completed,
            warnings=warnings,
            output_files=[
                str(guide_path),
                str(markdown_path),
                str(validation_path),
            ],
            validation_result=report.status,
            usage=getattr(client, "last_usage", {}),
        )

    def generate_lesson(self, *, curriculum_name: str = "CKLA", grade: Union[str, int] = 8,
                        unit: Union[str, int] = 1, lesson_number: int = 1,
                        dry_run: bool = False, resume: bool = True) -> GenerationResult:
        """Run or plan the presentation-aware instructional generation pipeline."""
        preparation = self.prepare_lesson(curriculum_name=curriculum_name, grade=grade, unit=unit,
                                          lesson_number=lesson_number)
        run_dir = self.generation_output_directory / preparation.request_id
        stages = ["curriculum_reader", "curriculum_analyzer", "instruction_designer",
                  "presentation_designer", "lesson_assembler", "lesson_validator",
                  "presentation_renderer_prompt_generator", "gamma_handoff_prompt_generator",
                  "lesson_package_parser"]
        if preparation.status == "failed":
            return GenerationResult(request_id=preparation.request_id, status="failed",
                output_directory=str(run_dir), failed_stage="prepare_lesson", errors=preparation.errors,
                warnings=preparation.warnings)
        if dry_run:
            return GenerationResult(request_id=preparation.request_id, status="dry_run",
                output_directory=str(run_dir), warnings=preparation.warnings,
                completed_stages=["prepare_lesson"], usage={"planned_stages": stages})

        from brain.curriculum_reader import CurriculumReader
        from brain.curriculum_analyzer import CurriculumAnalyzer
        from brain.instruction_designer import InstructionDesigner
        from brain.presentation_designer import PresentationDesigner
        from brain.lesson_assembler import LessonAssembler
        from brain.lesson_validator import LessonValidator
        from brain.lesson_package_parser import parse_lesson_package
        from renderer.prompt_bundle import RendererType
        from renderer.prompt_generator import generate_prompt_bundle
        from renderer.gamma_prompt import (
            build_gamma_authoritative_facts,
            write_gamma_deck_prompt,
        )
        from config.settings import get_settings
        from schemas.reader_output_schema import CurriculumReaderOutput
        from schemas.analyzer_output_schema import CurriculumAnalyzerOutput
        from schemas.instruction_design_schema import InstructionDesign
        from schemas.presentation_design_schema import PresentationDesignOutput
        from schemas.lesson_package_schema import LessonPackage
        from services.openai_client import OpenAIClient

        settings = get_settings()
        try:
            client = self.openai_client or OpenAIClient(settings=settings)
        except Exception as error:
            return GenerationResult(request_id=preparation.request_id, status="failed",
                output_directory=str(run_dir), completed_stages=["prepare_lesson"], failed_stage="configuration",
                warnings=preparation.warnings, errors=[str(error)])
        pipeline_input = LessonPipelineInput.model_validate_json(Path(preparation.output_files[0]).read_text(encoding="utf-8"))
        completed = ["prepare_lesson"]
        usage: dict[str, Any] = {}

        definitions = [
            ("curriculum_reader", "01_reader_output.json", CurriculumReaderOutput, CurriculumReader, lambda values: pipeline_input),
            ("curriculum_analyzer", "02_analyzer_output.json", CurriculumAnalyzerOutput, CurriculumAnalyzer, lambda values: values[0]),
            ("instruction_designer", "03_instruction_design.json", InstructionDesign, InstructionDesigner, lambda values: {"reader": values[0].model_dump(), "analyzer": values[1].model_dump()}),
            ("presentation_designer", "04_presentation_design.json", PresentationDesignOutput, PresentationDesigner,
             lambda values: {"instruction_design": values[2].model_dump(), "analyzer": values[1].model_dump(), "reader": values[0].model_dump()}),
            ("lesson_assembler", "05_lesson_package.json", LessonPackage, LessonAssembler, lambda values: {"pipeline_input": pipeline_input.model_dump(), "reader": values[0].model_dump(), "analyzer": values[1].model_dump(), "instruction_design": values[2].model_dump(), "presentation_design": values[3].model_dump()}),
        ]
        values: list[BaseModel] = []
        for stage_name, filename, schema, stage_class, input_builder in definitions:
            target = run_dir / filename
            try:
                if resume and target.is_file():
                    output = self._read_model(target, schema)
                else:
                    output = stage_class(client).run(input_builder(values))
                    self._write_json(target, output)
                values.append(output)
                completed.append(stage_name)
                if getattr(client, "last_usage", None):
                    usage[stage_name] = client.last_usage
            except Exception as error:
                return GenerationResult(request_id=preparation.request_id, status="failed",
                    output_directory=str(run_dir), completed_stages=completed, failed_stage=stage_name,
                    warnings=preparation.warnings, errors=[f"{stage_name} failed: {error}"], usage=usage)

        reader, analyzer, design, presentation, package = values
        try:
            report: LessonValidationReport = LessonValidator().validate(package, reader, design, presentation)
            self._write_json(run_dir / "06_validation_report.json", report)
            completed.append("lesson_validator")
            if report.status == "fail":
                return GenerationResult(request_id=preparation.request_id, status="failed",
                    output_directory=str(run_dir), completed_stages=completed, failed_stage="lesson_validator",
                    warnings=preparation.warnings, errors=["Lesson validation failed"], usage=usage,
                    validation_result=report.status, slide_count=report.slide_count)
        except Exception as error:
            return GenerationResult(request_id=preparation.request_id, status="failed",
                output_directory=str(run_dir), completed_stages=completed, failed_stage="lesson_validator",
                warnings=preparation.warnings, errors=[str(error)], usage=usage,
                validation_result=getattr(locals().get("report"), "status", None))
        try:
            prompt_bundle = generate_prompt_bundle(
                presentation,
                renderer_type=RendererType.GENERIC,
            )
            prompt_bundle.write(run_dir)
            completed.append("presentation_renderer_prompt_generator")
        except Exception as error:
            return GenerationResult(request_id=preparation.request_id, status="failed",
                output_directory=str(run_dir), completed_stages=completed,
                failed_stage="presentation_renderer_prompt_generator",
                warnings=preparation.warnings, errors=[str(error)], usage=usage,
                validation_result=report.status, slide_count=report.slide_count)
        try:
            curriculum = preparation.lesson_source.curriculum
            authoritative_facts = build_gamma_authoritative_facts(
                presentation,
                curriculum,
                activity_page_references=pipeline_input.activity_book_references,
                assigned_reading_pages=pipeline_input.reader_page_references,
            )
            write_gamma_deck_prompt(
                presentation,
                run_dir,
                authoritative_facts=authoritative_facts,
            )
            completed.append("gamma_handoff_prompt_generator")
        except Exception as error:
            return GenerationResult(request_id=preparation.request_id, status="failed",
                output_directory=str(run_dir), completed_stages=completed,
                failed_stage="gamma_handoff_prompt_generator",
                warnings=preparation.warnings, errors=[str(error)], usage=usage,
                validation_result=report.status, slide_count=report.slide_count)
        try:
            lesson = parse_lesson_package(package.model_dump(mode="json"))
            self._write_json(run_dir / "07_validated_lesson.json", lesson)
            completed.append("lesson_package_parser")
        except Exception as error:
            return GenerationResult(request_id=preparation.request_id, status="failed",
                output_directory=str(run_dir), completed_stages=completed, failed_stage="lesson_package_parser",
                warnings=preparation.warnings, errors=[str(error)], usage=usage,
                validation_result=getattr(locals().get("report"), "status", None))
        report_warnings = [f.message for f in report.findings if f.severity == "warning"]
        return GenerationResult(request_id=preparation.request_id,
            status="completed_with_warnings" if preparation.warnings or report_warnings else "completed",
            output_directory=str(run_dir), completed_stages=completed,
            warnings=preparation.warnings + report_warnings, usage=usage,
            validation_result=report.status, slide_count=report.slide_count, lesson=lesson)


__all__ = [
    "LessonMetadata", "LessonPipelineInput", "LessonPreparationResult", "LessonRequest",
    "TeacherGuidePageRange", "TeacherOS",
]
