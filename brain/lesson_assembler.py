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
from schemas.presentation_design_schema import PresentationDesignOutput


_SUPPORTED_SLIDE_TYPES = {"title", "objective", "agenda", "background knowledge", "vocabulary",
    "instructions", "reading", "discussion", "activity", "check for understanding", "writing",
    "homework", "closure", "assessment", "day divider"}


def _presentation_to_specification(presentation: PresentationDesignOutput) -> SlideSpecification:
    """Compatibility adapter: rich design in, stable renderer contract out."""
    from schemas.slide_specification_schema import SlideSpecificationItem

    items = []
    for rich in presentation.slides:
        slide_type = rich.slide_type.lower().replace("_", " ")
        if slide_type not in _SUPPORTED_SLIDE_TYPES:
            slide_type = "activity"
        student = rich.student_view
        content_parts = [student.subtitle, student.body_text, student.prompt, student.quotation,
                         *student.vocabulary_terms, *student.sentence_frames, *student.directions]
        visual_parts = [rich.visuals.visual_description, rich.visuals.diagram_description,
                        rich.design.notes_for_renderer]
        items.append(SlideSpecificationItem(
            slide_id=rich.slide_id, sequence_number=rich.sequence_number, slide_type=slide_type,
            title=student.title or rich.slide_type.replace("_", " ").title(),
            student_facing_content="\n".join(part for part in content_parts if part),
            bullet_points=student.bullet_points, speaker_notes=rich.teacher_notes.as_text(),
            # The legacy renderer model requires positive integers. ``None`` is
            # its semantic representation for an informational divider.
            timing=None if slide_type == "day divider" else rich.timing,
            interaction=None if rich.interaction.interaction_type.value == "none" else rich.interaction.interaction_type.value,
            teacher_directions="\n".join(rich.teacher_notes.teacher_directions),
            materials="; ".join(rich.materials) or None,
            visual_direction="; ".join(part for part in visual_parts if part) or None,
            image_prompt=rich.visuals.image_prompt, source_references=rich.source_references,
            fidelity_classification="source_derived" if rich.fidelity_classification == "source_adapted" else rich.fidelity_classification,
        ))
    return SlideSpecification(request_id=presentation.request_id, slides=items, warnings=presentation.warnings)


class LessonAssembler(GenerationStage[LessonPackage]):
    schema = LessonPackage
    prompt_filename = "lesson_assembler.md"

    def run(self, input_data):
        """Merge validated outputs without asking a model to reproduce them."""
        common = {"pipeline_input", "reader", "analyzer", "instruction_design"}
        required = common | ({"presentation_design"} if isinstance(input_data, dict) and "presentation_design" in input_data else {"slide_specification"})
        if not isinstance(input_data, dict) or not required.issubset(input_data):
            return super().run(input_data)

        pipeline = input_data["pipeline_input"]
        reader = CurriculumReaderOutput.model_validate(input_data["reader"])
        analyzer = CurriculumAnalyzerOutput.model_validate(input_data["analyzer"])
        design = InstructionDesign.model_validate(input_data["instruction_design"])
        if "presentation_design" in input_data:
            presentation = PresentationDesignOutput.model_validate(input_data["presentation_design"])
            specification = _presentation_to_specification(presentation)
        else:
            presentation = None
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
            total_timing=sum(slide.timing or 0 for slide in slides if slide.slide_type != "day divider"),
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
