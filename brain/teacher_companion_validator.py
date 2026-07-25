"""Deterministic validation for generated Teacher Companion Guides."""

from __future__ import annotations

from typing import TYPE_CHECKING

from schemas.generation_common import ValidationFinding
from schemas.teacher_companion_schema import (
    SOURCE_EVIDENCE_MARKER,
    TeacherCompanionGuide,
    TeacherCompanionValidationReport,
)

if TYPE_CHECKING:
    from app.teacheros import LessonPipelineInput


class TeacherCompanionValidator:
    """Validate identity, grounding, and complete student-question coaching."""

    def validate(
        self,
        guide: TeacherCompanionGuide,
        pipeline_input: "LessonPipelineInput",
    ) -> TeacherCompanionValidationReport:
        findings: list[ValidationFinding] = []

        def add(code: str, severity: str, message: str) -> None:
            findings.append(
                ValidationFinding(
                    code=code,
                    severity=severity,
                    message=message,
                )
            )

        request = pipeline_input.request
        if guide.request_id != request.request_id:
            add(
                "request_identity",
                "error",
                "Companion request ID does not match the prepared lesson.",
            )
        basis = guide.source_basis
        expected_identity = (
            request.curriculum_name,
            request.grade,
            request.unit,
            request.lesson_number,
        )
        actual_identity = (
            basis.curriculum_name,
            basis.grade,
            basis.unit,
            basis.lesson_number,
        )
        if actual_identity != expected_identity:
            add(
                "lesson_identity",
                "error",
                "Companion source identity does not match the prepared lesson.",
            )
        if basis.lesson_title != (pipeline_input.lesson_title or ""):
            add(
                "lesson_title",
                "error",
                "Companion lesson title does not match the prepared lesson.",
            )
        if basis.student_reader_text_available:
            add(
                "student_reader_availability",
                "error",
                "Companion v1 must not claim Student Reader text is available.",
            )
        source_fields = (
            "objectives",
            "standards",
            "materials",
            "homework",
            "reader_page_references",
            "activity_book_references",
            "source_references",
        )
        for field in source_fields:
            if getattr(basis, field) != getattr(pipeline_input, field):
                add(
                    "source_basis_mismatch",
                    "error",
                    f"Companion source basis changed prepared field: {field}.",
                )

        allowed_references = set(
            [
                *pipeline_input.source_references,
                *pipeline_input.reader_page_references,
                *pipeline_input.activity_book_references,
            ]
        )
        for fact in guide.curriculum_facts:
            unsupported = set(fact.source_references) - allowed_references
            if unsupported:
                add(
                    "unsupported_curriculum_fact_source",
                    "error",
                    "Curriculum fact uses a source reference not present in "
                    f"the prepared lesson: {', '.join(sorted(unsupported))}",
                )

        for index, question in enumerate(guide.student_questions, start=1):
            unsupported = set(question.source_references) - allowed_references
            if unsupported:
                add(
                    "unsupported_question_source",
                    "error",
                    f"Student question {index} uses an unavailable source reference.",
                )
            if question.answer_basis == "requires_student_reader_evidence":
                if SOURCE_EVIDENCE_MARKER not in question.excellent_model_answer:
                    add(
                        "unanswered_source_dependent_question",
                        "error",
                        f"Student question {index} must be marked as requiring "
                        "source evidence rather than answered by guessing.",
                    )
            elif SOURCE_EVIDENCE_MARKER in question.excellent_model_answer:
                add(
                    "answer_basis_mismatch",
                    "error",
                    f"Student question {index} uses the source-evidence marker "
                    "without the matching answer basis.",
                )

        status = (
            "fail"
            if any(item.severity == "error" for item in findings)
            else (
                "pass_with_warnings"
                if any(item.severity == "warning" for item in findings)
                else "pass"
            )
        )
        return TeacherCompanionValidationReport(
            status=status,
            findings=findings,
            question_count=len(guide.student_questions),
        )


__all__ = ["TeacherCompanionValidator"]
