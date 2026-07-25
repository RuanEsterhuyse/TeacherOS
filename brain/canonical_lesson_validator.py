"""Deterministic validation for the canonical instructional graph."""

from __future__ import annotations

from schemas.canonical_lesson_schema import Availability, CanonicalLesson
from schemas.generation_common import ValidationFinding
from schemas.generation_result_schema import LessonValidationReport


class CanonicalLessonValidator:
    def validate(self, lesson: CanonicalLesson) -> LessonValidationReport:
        findings: list[ValidationFinding] = []

        def add(code: str, severity: str, message: str) -> None:
            findings.append(
                ValidationFinding(code=code, severity=severity, message=message)
            )

        for resource in lesson.instructional_resources:
            if resource.availability in {
                Availability.UNAVAILABLE,
                Availability.PARTIAL,
            }:
                add(
                    "instructional_resource_unavailable",
                    "warning",
                    f"{resource.title}: {resource.availability.value}.",
                )
        for block in lesson.lesson_blocks:
            chunk_minutes = sum(
                chunk.timing.duration_minutes for chunk in block.reading_chunks
            )
            if chunk_minutes > block.timing.duration_minutes:
                add(
                    "reading_chunk_timing",
                    "error",
                    f"Reading chunks exceed block timing: {block.id}.",
                )
            for chunk in block.reading_chunks:
                pause_minutes = sum(
                    pause.timing.duration_minutes
                    for pause in chunk.pause_points
                )
                if pause_minutes > chunk.timing.duration_minutes:
                    add(
                        "pause_point_timing",
                        "error",
                        f"Pause points exceed reading time: {chunk.id}.",
                    )
                if chunk.source_availability == Availability.UNAVAILABLE:
                    if chunk.evidence or any(
                        question.answer_availability
                        != Availability.UNAVAILABLE
                        for question in chunk.questions
                    ):
                        add(
                            "unsupported_reading_content",
                            "error",
                            f"Unavailable reading chunk asserts answers or evidence: {chunk.id}.",
                        )
        for task in lesson.activity_book:
            if task.source_availability == Availability.UNAVAILABLE and (
                task.expected_answers or task.common_mistakes
            ):
                add(
                    "unsupported_activity_content",
                    "error",
                    f"Unavailable activity task asserts answers: {task.id}.",
                )
        status = (
            "fail"
            if any(item.severity == "error" for item in findings)
            else (
                "pass_with_warnings"
                if findings
                else "pass"
            )
        )
        mappings = [
            mapping
            for block in lesson.lesson_blocks
            for mapping in (
                block.slide_mappings
                + [
                    mapping
                    for chunk in block.reading_chunks
                    for mapping in chunk.slide_mappings
                ]
            )
        ]
        return LessonValidationReport(
            status=status,
            findings=findings,
            timing_total_minutes=lesson.agenda.selected_duration_minutes,
            slide_count=len(mappings),
        )


__all__ = ["CanonicalLessonValidator"]
