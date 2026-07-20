"""Deterministic fidelity and renderer-handoff validation."""

from __future__ import annotations

from schemas.generation_common import ValidationFinding
from schemas.generation_result_schema import LessonValidationReport
from schemas.instruction_design_schema import InstructionDesign
from schemas.lesson_package_schema import LessonPackage
from schemas.reader_output_schema import CurriculumReaderOutput


class LessonValidator:
    instructional_types = {"instructions", "reading", "discussion", "activity", "check for understanding", "writing", "assessment"}

    def validate(self, package: LessonPackage, reader: CurriculumReaderOutput, design: InstructionDesign) -> LessonValidationReport:
        findings: list[ValidationFinding] = []
        slides = package.slides
        ids = [s.slide_id for s in slides]

        def add(code: str, severity: str, message: str, slide_id: str | None = None):
            findings.append(ValidationFinding(code=code, severity=severity, message=message, slide_id=slide_id))

        if len(ids) != len(set(ids)):
            add("duplicate_slide_id", "error", "Every slide ID must be unique.")
        if package.slide_order != ids:
            add("slide_order", "error", "slide_order must exactly match the ordered slide records.")
        if [s.sequence_number for s in slides] != list(range(1, len(slides) + 1)):
            add("slide_sequence", "error", "Slide sequence numbers must be continuous.")
        for slide in slides:
            if slide.slide_type in self.instructional_types and not slide.speaker_notes.strip():
                add("missing_speaker_notes", "error", "Instructional slide has no speaker notes.", slide.slide_id)
            if not slide.source_references and slide.fidelity_classification != "teacheros_added":
                add("missing_source_reference", "warning", "Source-derived slide has no source reference.", slide.slide_id)
            if ("\"" in slide.student_facing_content or "“" in slide.student_facing_content) and slide.fidelity_classification == "teacheros_added":
                add("possible_invented_quotation", "warning", "TeacherOS-added content contains quotation marks; verify against the source.", slide.slide_id)
        package_text = "\n".join([str(package.model_dump()), *package.reader_references, *package.activity_references])
        for label, values in (("objective", reader.objectives), ("required activity", reader.lesson_sequence),
                              ("homework", reader.homework), ("Activity Book reference", reader.activity_book_references),
                              ("Reader reference", reader.reader_references)):
            for value in values:
                if value and value not in package_text:
                    add(f"missing_{label.lower().replace(' ', '_')}", "error", f"Required {label} was not preserved: {value}")
        if not package.source_references:
            add("missing_package_sources", "error", "Lesson Package has no source references.")
        for warning in package.unresolved_warnings + design.timing_warnings:
            add("unresolved_warning", "warning", warning)
        timing = sum(slide.timing or 0 for slide in slides)
        if timing != package.total_timing:
            add("timing_total", "warning", f"Slide timing totals {timing} minutes but package reports {package.total_timing}.")
        status = "fail" if any(f.severity == "error" for f in findings) else (
            "pass_with_warnings" if any(f.severity == "warning" for f in findings) else "pass"
        )
        return LessonValidationReport(status=status, findings=findings, timing_total_minutes=timing, slide_count=len(slides))
