"""Deterministic fidelity and renderer-handoff validation."""

from __future__ import annotations

from schemas.generation_common import ValidationFinding
from schemas.generation_result_schema import LessonValidationReport
from schemas.instruction_design_schema import InstructionDesign
from schemas.lesson_package_schema import LessonPackage
from schemas.reader_output_schema import CurriculumReaderOutput
from schemas.presentation_design_schema import PresentationDesignOutput
import re
from collections import Counter
from typing import Any, Iterator


_CONTAINMENT_TRANSLATION = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
})


def normalize_containment_text(value: str) -> str:
    """Canonicalize harmless typography differences for fidelity containment."""
    normalized = value.translate(_CONTAINMENT_TRANSLATION)
    normalized = re.sub(r"(?<!\w)'([^'\n]+)'(?!\w)", r'"\1"', normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contained_text_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _contained_text_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _contained_text_values(item)


class LessonValidator:
    instructional_types = {"instructions", "reading", "discussion", "activity", "check for understanding", "writing", "assessment"}

    teacher_action = re.compile(r"\b(project|distribute|ask students|teacher circulates|teacher should)\b", re.I)
    file_path = re.compile(r"(?:[A-Za-z]:\\|/[^\s]+/|\\\\|\.(?:pdf|docx?|pptx?)\b)", re.I)

    def presentation_findings(self, presentation: PresentationDesignOutput) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        def add(code, message, slide_id=None):
            findings.append(ValidationFinding(code=code, severity="warning", message=message, slide_id=slide_id))
        titles, layouts, interactions = [], [], []
        for slide in presentation.slides:
            text = slide.student_view.all_text()
            titles.append(slide.student_view.title.strip().lower())
            layouts.append(slide.design.layout.value)
            interactions.append(slide.interaction.interaction_type.value)
            if len(text.split()) > slide.design.max_words:
                add("student_word_count", f"Student view has {len(text.split())} words; maximum is {slide.design.max_words}.", slide.slide_id)
            if len(slide.student_view.bullet_points) > 3:
                add("maximum_bullet_count", "Student view has more than three bullets.", slide.slide_id)
            if not slide.teacher_notes.as_text().strip() and slide.slide_type not in {"title", "day_divider", "day divider"}:
                add("missing_teacher_notes", "Instructional slide has no teacher notes.", slide.slide_id)
            if self.teacher_action.search(text):
                add("teacher_direction_in_student_view", "Teacher directions appear in student-facing content.", slide.slide_id)
            if self.file_path.search(text):
                add("student_file_path", "A file path or unsupported filename appears in student-facing content.", slide.slide_id)
            if slide.visuals.visual_required and not (slide.visuals.alt_text or "").strip():
                add("visual_alt_text", "A required visual has no alt text.", slide.slide_id)
            if not slide.visuals.visual_required and slide.visuals.image_prompt:
                add("unneeded_image_prompt", "image_prompt is present while visual_required is false.", slide.slide_id)
            if ("vocab" in slide.slide_type.lower() or "vocab" in text.lower()) and not slide.student_view.vocabulary_terms:
                add("empty_vocabulary", "Vocabulary activity has no structured vocabulary terms.", slide.slide_id)
        for title, count in Counter(t for t in titles if t).items():
            if count > 1: add("duplicate_title", f'Title "{title}" is repeated {count} times.')
        for layout, count in Counter(layouts).items():
            if len(layouts) >= 4 and count / len(layouts) > .6:
                add("excessive_layout_reuse", f'Layout "{layout}" is used on {count} of {len(layouts)} slides.')
        for index in range(1, len(interactions)):
            if interactions[index] != "none" and interactions[index] == interactions[index - 1]:
                add("repeated_interaction", "Adjacent slides repeat the same interaction.", presentation.slides[index].slide_id)
        closure = [s for s in presentation.slides if s.slide_type.lower().replace("_", " ") in {"closure", "exit ticket"}]
        if len(closure) > 1:
            add("duplicate_closure", "Multiple closure or exit-ticket segments may duplicate instructional time.")
        return findings

    def validate(self, package: LessonPackage, reader: CurriculumReaderOutput, design: InstructionDesign,
                 presentation: PresentationDesignOutput | None = None) -> LessonValidationReport:
        findings: list[ValidationFinding] = []
        slides = package.slides
        ids = [s.slide_id for s in slides]
        if presentation is not None:
            findings.extend(self.presentation_findings(presentation))

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
        package_text = normalize_containment_text(
            "\n".join([
                *_contained_text_values(package.model_dump()),
                *package.reader_references,
                *package.activity_references,
            ])
        )
        for label, values in (("objective", reader.objectives), ("required activity", reader.lesson_sequence),
                              ("homework", reader.homework), ("Activity Book reference", reader.activity_book_references),
                              ("Reader reference", reader.reader_references)):
            for value in values:
                if value and normalize_containment_text(value) not in package_text:
                    add(f"missing_{label.lower().replace(' ', '_')}", "error", f"Required {label} was not preserved: {value}")
        if not package.source_references:
            add("missing_package_sources", "error", "Lesson Package has no source references.")
        for warning in package.unresolved_warnings + design.timing_warnings:
            add("unresolved_warning", "warning", warning)
        if presentation is not None:
            expected_by_day: dict[int, int] = {}
            actual_by_day: dict[int, int] = {}
            for segment in design.segments:
                expected_by_day[segment.day] = expected_by_day.get(segment.day, 0) + segment.timing_minutes
            for rich in presentation.slides:
                if rich.slide_type.lower().replace("_", " ") == "day divider":
                    continue
                day = rich.day or 1
                actual_by_day[day] = actual_by_day.get(day, 0) + (rich.timing or 0)
                if rich.timing and expected_by_day.get(day) and rich.timing > expected_by_day[day]:
                    add("slide_exceeds_day_timing", "warning",
                        f"Slide timing ({rich.timing}) exceeds Day {day} instructional timing ({expected_by_day[day]}).", rich.slide_id)
            for day, minutes in actual_by_day.items():
                if minutes > 120:
                    add("unrealistic_day_timing", "warning", f"Day {day} totals {minutes} minutes; verify the schedule.")
                if expected_by_day.get(day) is not None and minutes != expected_by_day[day]:
                    add("day_timing_total", "warning",
                        f"Day {day} presentation totals {minutes} minutes; instruction design totals {expected_by_day[day]}.")
        timing = sum(slide.timing or 0 for slide in slides if slide.slide_type != "day divider")
        if timing != package.total_timing:
            add("timing_total", "warning", f"Slide timing totals {timing} minutes but package reports {package.total_timing}.")
        status = "fail" if any(f.severity == "error" for f in findings) else (
            "pass_with_warnings" if any(f.severity == "warning" for f in findings) else "pass"
        )
        return LessonValidationReport(status=status, findings=findings, timing_total_minutes=timing, slide_count=len(slides))
