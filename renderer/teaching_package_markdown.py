"""Deterministic local renderers for structured teaching packages."""

from __future__ import annotations

import json
from typing import Iterable

from schemas.teaching_package_schema import (
    GroundedText,
    StructuredTeachingPackage,
    TeachingSourceReference,
)


def _label(value: GroundedText) -> str:
    return value.origin.value.replace("_", " ").title()


def _references(values: Iterable[TeachingSourceReference]) -> str:
    rendered = []
    for value in values:
        location = (
            f"PDF p. {value.display_page_number}"
            if value.display_page_number is not None
            else value.printed_page or value.stable_source_id
        )
        rendered.append(f"{value.source_document} ({location})")
    return "; ".join(dict.fromkeys(rendered)) or "No source reference available"


def _grounded(value: GroundedText) -> str:
    lines = [value.text or "_Unavailable_"]
    lines.append(
        f"*Classification: {_label(value)} · "
        f"Review: {value.review_status.value.replace('_', ' ')}*"
    )
    if value.source_references:
        lines.append(f"*Source: {_references(value.source_references)}*")
    return "\n\n".join(lines)


class TeacherCompanionMarkdownRenderer:
    """Render the teacher-facing guide without generating new content."""

    def render(self, package: StructuredTeachingPackage) -> str:
        dashboard = package.dashboard
        lines = [
            f"# Teacher Companion: {dashboard.lesson_title}",
            "",
            "> TeacherOS organizes the verified curriculum. Official, adapted, "
            "generated, and unavailable content is labeled throughout.",
            "",
            "## 1. Lesson Dashboard",
            "",
            f"- **Curriculum:** {dashboard.curriculum}",
            f"- **Grade:** {dashboard.grade}",
            f"- **Unit:** {dashboard.unit}",
            f"- **Lesson:** {dashboard.lesson_number}",
            f"- **Estimated duration:** "
            f"{dashboard.estimated_duration_minutes} minutes",
            f"- **Materials:** {', '.join(dashboard.materials) or 'None located'}",
            f"- **Student Reader pages:** "
            f"{', '.join(dashboard.student_reader_pages) or 'Unavailable'}",
            f"- **Activity Book:** "
            f"{', '.join(dashboard.activity_book_pages) or 'Unavailable'}",
            "",
            "### Lesson purpose",
            "",
            _grounded(dashboard.lesson_purpose),
            "",
            "### Big idea",
            "",
            _grounded(dashboard.big_idea),
            "",
            "### Why this matters",
            "",
            _grounded(dashboard.why_it_matters),
        ]
        if dashboard.teacher_reminders:
            lines.extend(["", "### Teacher reminders", ""])
            lines.extend(
                f"- {value.text} *({_label(value)})*"
                for value in dashboard.teacher_reminders
            )
        if dashboard.missing_resource_warnings:
            lines.extend(["", "### Missing-resource warnings", ""])
            lines.extend(
                f"- {value}" for value in dashboard.missing_resource_warnings
            )

        lines.extend(["", "## 2. Teach This Lesson in Five Minutes", ""])
        for value in package.five_minute_summary:
            lines.extend([f"- {value.text} *({_label(value)})*"])

        lines.extend([
            "",
            "## 3. Lesson at a Glance",
            "",
            "| # | Official title | Student-friendly title | Time | "
            "Materials | Reader / Activity | Slides |",
            "|---:|---|---|---:|---|---|---|",
        ])
        for item in package.agenda:
            resources = ", ".join(
                item.student_reader_references
                + item.activity_book_references
            ) or "—"
            lines.append(
                f"| {item.official_order} | {item.official_title.text} | "
                f"{item.student_friendly_title.text} | "
                f"{item.duration_minutes if item.duration_minutes is not None else '—'} | "
                f"{', '.join(item.materials) or '—'} | {resources} | "
                f"{', '.join(item.slide_ids) or 'Teacher-only'} |"
            )

        lines.extend(["", "## 4. Objectives", ""])
        for objective in package.objectives:
            lines.extend([
                f"### {objective.objective_type.title()} objective",
                "",
                "**Official wording**",
                "",
                _grounded(objective.official),
                "",
                "**Student-friendly wording**",
                "",
                _grounded(objective.student_friendly),
                "",
                "**Evidence of mastery**",
                "",
                _grounded(objective.evidence_of_mastery),
                "",
                f"**Meaning-preservation validation:** "
                f"{'Passed' if objective.meaning_preserved else 'Failed'}",
                "",
            ])

        lines.extend(["## 5. Essential Question", ""])
        lines.append(
            _grounded(package.essential_question)
            if package.essential_question
            else "_No official essential question was located. None was invented._"
        )

        self._grounded_section(lines, "6. Background Knowledge", package.background_knowledge)
        self._grounded_section(lines, "7. Theme Analysis", package.themes)
        self._grounded_section(lines, "8. Literary Analysis", package.literary_analysis)

        lines.extend(["", "## 9. Vocabulary", ""])
        if not package.vocabulary:
            lines.append("_No required vocabulary was located._")
        for value in package.vocabulary:
            lines.extend([
                f"### {value.word}",
                "",
                (
                    f"**Official definition:** {value.official_definition.text}"
                    if value.official_definition
                    else "**Official definition:** Unavailable"
                ),
                "",
                f"**Student-friendly definition:** "
                f"{value.student_friendly_definition.text}",
                "",
                f"**Teacher explanation:** {value.teacher_explanation.text}",
                "",
                f"**Example:** {value.example.text} *({_label(value.example)})*",
                "",
                f"**Visual:** {value.visual_suggestion.text}",
                "",
                f"**Gesture:** {value.gesture_suggestion.text}",
                "",
                f"**ELD support:** {value.eld_support.text}",
                "",
                f"**Watch for:** {value.misconception.text}",
                "",
            ])

        lines.extend(["## 10. Step-by-Step Teaching Walkthrough", ""])
        questions = {value.question_id: value for value in package.questions}
        for step in package.teaching_steps:
            lines.extend([
                f"### {step.official_title}",
                "",
                f"- **Agenda ID:** {step.agenda_item_id}",
                f"- **Student-friendly title:** {step.student_friendly_title}",
                f"- **Duration:** "
                f"{step.duration_minutes if step.duration_minutes is not None else 'Not specified'}",
                f"- **Materials:** {', '.join(step.materials) or 'None located'}",
                f"- **Related slides:** {', '.join(step.slide_ids) or 'None'}",
                "",
                "**Instructional purpose**",
                "",
                _grounded(step.instructional_purpose),
                "",
                "**Teacher actions**",
                "",
            ])
            lines.extend(
                [f"{index}. {value.text} *({_label(value)})*"
                 for index, value in enumerate(step.teacher_actions, 1)]
                or ["_No separate teacher action was located._"]
            )
            lines.extend(["", "**Student actions**", ""])
            lines.extend(
                [f"{index}. {value.text} *({_label(value)})*"
                 for index, value in enumerate(step.student_actions, 1)]
                or ["_No separate student action was located._"]
            )
            lines.extend([
                "",
                "**Suggested teacher wording**",
                "",
                _grounded(step.suggested_teacher_wording),
                "",
                "**Required questions**",
                "",
            ])
            lines.extend(
                f"- {questions[qid].exact_question.text} (`{qid}`)"
                for qid in step.question_ids
            )
            if not step.question_ids:
                lines.append("_No required question was assigned to this step._")
            self._compact_values(lines, "Checks for understanding", step.checks_for_understanding)
            self._compact_values(lines, "Likely misconceptions", step.misconceptions)
            self._compact_values(lines, "ELD supports", step.eld_supports)
            self._compact_values(lines, "Differentiation", step.differentiation)
            lines.extend(["", "**Transition**", "", _grounded(step.transition), ""])

        lines.extend(["## 11. Discussion Guide", ""])
        for question in package.questions:
            lines.extend([
                f"### Question {question.sequence} · `{question.question_id}`",
                "",
                f"**Exact question:** {question.exact_question.text}",
                "",
                f"**Agenda item:** {question.agenda_item_id}",
                "",
                f"**Expected answer:** {question.expected_answer.text}",
                "",
                f"**Answer status:** {question.answer_visibility.replace('_', ' ')}",
                "",
                f"**Text evidence:** "
                f"{question.text_evidence.text if question.text_evidence else 'Unavailable'}",
                "",
                f"**Follow-up:** {question.follow_up.text}",
                "",
                f"**Likely misconception:** {question.misconception.text}",
                "",
                f"**ELD sentence frame:** {question.eld_sentence_frame.text}",
                "",
                f"**Related slides:** {', '.join(question.slide_ids) or 'None'}",
                "",
                f"**Source:** {_references(question.exact_question.source_references)}",
                "",
            ])

        self._grounded_section(lines, "12. Student Reader Guidance", package.student_reader_guidance)
        self._grounded_section(lines, "13. Activity Book Guidance", package.activity_book_guidance)
        self._grounded_section(lines, "14. Assessment", package.assessment)
        self._grounded_section(lines, "15. Wrap-Up", package.wrap_up)
        self._grounded_section(lines, "16. Homework", package.homework)
        self._grounded_section(lines, "17. ELD Supports", package.eld_supports)

        lines.extend([
            "",
            "## 18. Teacher Reflection",
            "",
            "- What worked well?",
            "- Where did students struggle?",
            "- Which misconception appeared?",
            "- Which supports were effective?",
            "- What should be changed next time?",
            "- Which students need follow-up?",
            "- Was the pacing realistic?",
            "",
            "## Validation Summary",
            "",
            f"**Status:** {package.validation.status}",
        ])
        lines.extend(
            f"- **{finding.severity.value}: {finding.code}** — "
            f"{finding.message}"
            for finding in package.validation.findings
        )
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _grounded_section(
        lines: list[str],
        title: str,
        values: list[GroundedText],
    ) -> None:
        lines.extend(["", f"## {title}", ""])
        if not values:
            lines.append(
                "_No source-supported content was available; nothing was invented._"
            )
        for value in values:
            lines.extend([_grounded(value), ""])

    @staticmethod
    def _compact_values(
        lines: list[str],
        title: str,
        values: list[GroundedText],
    ) -> None:
        lines.extend(["", f"**{title}**", ""])
        lines.extend(
            [f"- {value.text} *({_label(value)})*" for value in values]
            or ["- None located"]
        )


class StudentSlidesMarkdownRenderer:
    """Render a copyable student-slide storyboard with separate notes."""

    def render(self, package: StructuredTeachingPackage) -> str:
        lines = [
            f"# Student Slides: {package.dashboard.lesson_title}",
            "",
            f"Validation: **{package.validation.status}**",
            "",
        ]
        for slide in package.student_slides:
            lines.extend([
                f"## Slide {slide.slide_number}: {slide.title}",
                "",
                f"**Type:** {slide.slide_type}",
                "",
            ])
            lines.extend(f"- {value}" for value in slide.visible_student_content)
            if slide.student_prompt:
                lines.extend(["", f"**Prompt:** {slide.student_prompt}"])
            if slide.page_reference:
                lines.extend(["", f"**Reader:** {slide.page_reference}"])
            if slide.activity_reference:
                lines.extend(["", f"**Activity:** {slide.activity_reference}"])
            lines.extend([
                "",
                f"**Visual specification:** {slide.visual_specification}",
                "",
                "**Speaker notes:**",
                "",
            ])
            lines.extend(
                [f"- {value}" for value in slide.speaker_notes]
                or ["- No additional teacher notes."]
            )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def validation_markdown(package: StructuredTeachingPackage) -> str:
    report = package.validation
    lines = [
        "# Teaching Package Validation",
        "",
        f"- **Status:** {report.status}",
        f"- **Package digest:** `{report.package_digest}`",
        f"- **Validator version:** `{report.validator_version}`",
        "",
        "## Findings",
        "",
    ]
    lines.extend(
        f"- **{value.severity.value}: {value.code}**"
        f"{f' (`{value.reference_id}`)' if value.reference_id else ''} — "
        f"{value.message}"
        for value in report.findings
    )
    if not report.findings:
        lines.append("- No findings.")
    return "\n".join(lines).rstrip() + "\n"


def deterministic_json(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [
            item.model_dump(mode="json")
            if hasattr(item, "model_dump")
            else item
            for item in value
        ]
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


__all__ = [
    "StudentSlidesMarkdownRenderer",
    "TeacherCompanionMarkdownRenderer",
    "deterministic_json",
    "validation_markdown",
]
