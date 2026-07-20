"""Deterministically assemble validated stage outputs into a Lesson Package."""

from brain.stage import GenerationStage
from schemas.lesson_package_schema import (
    CKLA_ATTRIBUTION,
    LessonPackage,
    LessonPackageMetadata,
    PackageActivity,
    PackageHomework,
)
from schemas.generation_common import GenerationMetadata
from schemas.reader_output_schema import CurriculumReaderOutput
from schemas.analyzer_output_schema import CurriculumAnalyzerOutput
from schemas.instruction_design_schema import InstructionDesign
from schemas.slide_specification_schema import SlideSpecification


class LessonAssembler(GenerationStage[LessonPackage]):
    schema = LessonPackage
    prompt_filename = "lesson_assembler.md"

    def run(self, input_data):
        """Merge validated outputs without asking a model to reproduce them."""
        required = {"pipeline_input", "reader", "analyzer", "instruction_design", "slide_specification"}
        if not isinstance(input_data, dict) or not required.issubset(input_data):
            return super().run(input_data)

        pipeline = input_data["pipeline_input"]
        reader = CurriculumReaderOutput.model_validate(input_data["reader"])
        analyzer = CurriculumAnalyzerOutput.model_validate(input_data["analyzer"])
        design = InstructionDesign.model_validate(input_data["instruction_design"])
        specification = SlideSpecification.model_validate(input_data["slide_specification"])
        request = pipeline["request"]
        slides = specification.slides

        activities = [
            PackageActivity(activity_id=f"A{position:02d}", title=text, instructions=text)
            for position, text in enumerate(reader.lesson_sequence, start=1) if text.strip()
        ]
        homework = [
            PackageHomework(title=f"Homework {position}", instructions=text)
            for position, text in enumerate(reader.homework, start=1) if text.strip()
        ]
        warnings = list(dict.fromkeys(
            pipeline.get("extraction_warnings", []) + reader.uncertainties + reader.timing_conflicts
            + analyzer.timing_conflicts + analyzer.fidelity_risks + design.timing_warnings
            + specification.warnings
        ))
        source_references = list(dict.fromkeys(
            pipeline.get("source_references", []) + reader.source_references + design.source_references
        ))

        return LessonPackage(
            package_id=request["request_id"],
            lesson_metadata=LessonPackageMetadata(
                title=reader.lesson_title or pipeline.get("lesson_title") or f"Lesson {request['lesson_number']}",
                grade=str(request["grade"]), unit=str(request["unit"]),
                lesson_number=request["lesson_number"], curriculum_name=request["curriculum_name"],
                objectives=reader.objectives, standards=reader.standards, attribution=CKLA_ATTRIBUTION,
            ),
            lesson_overview=analyzer.central_learning_goal.text,
            total_timing=sum(slide.timing or 0 for slide in slides),
            materials=reader.materials,
            slide_order=[slide.slide_id for slide in slides], slides=slides,
            homework=homework, activities=activities,
            activity_references=reader.activity_book_references,
            reader_references=reader.reader_references,
            source_references=source_references,
            unresolved_warnings=warnings,
            generation_metadata=GenerationMetadata(
                request_id=request["request_id"], model=self.client.settings.teacheros_model,
                attribution=CKLA_ATTRIBUTION,
            ),
        )
