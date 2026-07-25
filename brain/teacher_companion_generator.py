"""Prompt-backed generation for an optional Teacher Companion Guide."""

from brain.stage import GenerationStage
from schemas.teacher_companion_schema import (
    CompanionSourceBasis,
    TeacherCompanionGuide,
)


class TeacherCompanionGenerator(GenerationStage[TeacherCompanionGuide]):
    schema = TeacherCompanionGuide
    prompt_filename = "teacher_companion_generator.md"

    def run(self, input_data):
        """Generate guidance while stamping exact prepared source metadata."""
        guide = super().run(input_data)
        request = input_data.request
        guide.request_id = request.request_id
        guide.source_basis = CompanionSourceBasis(
            curriculum_name=request.curriculum_name,
            grade=request.grade,
            unit=request.unit,
            lesson_number=request.lesson_number,
            lesson_title=input_data.lesson_title,
            objectives=input_data.objectives,
            standards=input_data.standards,
            materials=input_data.materials,
            homework=input_data.homework,
            reader_page_references=input_data.reader_page_references,
            activity_book_references=input_data.activity_book_references,
            source_references=input_data.source_references,
            student_reader_text_available=False,
        )
        return guide


__all__ = ["TeacherCompanionGenerator"]
