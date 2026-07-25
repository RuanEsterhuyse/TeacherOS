"""Render a Teacher Companion directly from canonical instructional objects."""

from __future__ import annotations

from pathlib import Path

from renderer.lesson_renderer import LessonRenderer
from schemas.canonical_lesson_schema import (
    CanonicalLesson,
    GuidanceEntry,
    TeacherQuestion,
)


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) or "- None recorded."


def _guidance(values: list[GuidanceEntry]) -> str:
    return _bullets([item.text for item in values])


def _questions(values: list[TeacherQuestion]) -> str:
    sections = []
    for question in values:
        answers = [
            answer.answer
            for answer in question.expected_answers
            if answer.answer
        ]
        sections.append("\n".join([
            f"#### {question.question_text}",
            f"- Type: {question.question_type}",
            f"- Bloom level: {question.bloom_level}",
            f"- Difficulty: {question.difficulty}",
            f"- Discussion time: {question.estimated_discussion_time_minutes} minutes",
            f"- Response format: {question.response_format}",
            "- Expected answers:",
            _bullets(answers) if answers else "- Requires available source evidence.",
            "- Common misconceptions:",
            _bullets([
                f"{item.misconception} — {item.correction}"
                for item in question.common_misconceptions
            ]),
            "- Follow-up questions:",
            _bullets(question.follow_up_questions),
            "- Scaffolds:",
            _bullets(question.scaffolds),
            "- Extensions:",
            _bullets(question.extensions),
        ]))
    return "\n\n".join(sections) or "No canonical questions recorded."


class CanonicalTeacherCompanionRenderer(LessonRenderer[str]):
    def render(self, lesson: CanonicalLesson) -> str:
        info = lesson.lesson_information
        lines = [
            f"# Teacher Companion Guide: {info.lesson_title}",
            "",
            "## Lesson Information",
            "",
            f"- Curriculum: {info.curriculum}",
            f"- Grade: {info.grade}",
            f"- Unit: {info.unit}",
            f"- Lesson: {info.lesson_number}",
            f"- Duration: {info.duration_minutes} minutes",
            (
                f"- Essential question: {info.essential_question.text}"
                if info.essential_question.text
                else "- Essential question: Unavailable in validated sources."
            ),
            "",
            "## Learning Target",
            "",
            lesson.learning_target.text or "Unavailable in validated sources.",
            "",
            "## Language Objective",
            "",
            lesson.language_objective.text or "Unavailable in validated sources.",
            "",
            "## Standards",
            "",
            _bullets(lesson.standards),
            "",
            "## Success Criteria",
            "",
            _bullets(lesson.success_criteria),
            "",
            "## Master Agenda",
            "",
        ]
        lines.extend(
            f"{item.sequence}. **{item.title}** — "
            f"{item.start_offset_minutes}–{item.end_offset_minutes} min "
            f"({item.status})"
            for item in lesson.agenda.items
        )
        lines.extend(["", "## Materials", "", _bullets(lesson.materials)])
        for block in lesson.lesson_blocks:
            guidance = block.teacher_guidance
            lines.extend([
                "",
                f"## {block.title}",
                "",
                f"- Block ID: `{block.id}`",
                f"- Type: {block.block_type}",
                f"- Duration: {block.timing.duration_minutes} minutes",
                f"- Objective: {block.objective.text or 'Unavailable'}",
                "",
                "### Teacher Guidance",
                "",
                "#### Introduction",
                _guidance(guidance.introduction),
                "#### Modeling",
                _guidance(guidance.modeling),
                "#### Directions",
                _guidance(guidance.directions),
                "#### Questioning",
                _guidance(guidance.questioning),
                "#### Monitoring Notes",
                _guidance(guidance.monitoring_notes),
                "#### Transition",
                _guidance(guidance.transition),
                "#### Closure",
                _guidance(guidance.closure),
                "",
                "### Student Tasks",
                "",
                _bullets([
                    f"{task.task_type}: {task.instruction}"
                    for task in block.student_tasks
                ]),
                "",
                "### Teacher Questions",
                "",
                _questions(block.questions),
            ])
            for chunk in block.reading_chunks:
                lines.extend([
                    "",
                    f"### Reading Chunk: {chunk.title}",
                    "",
                    f"- Purpose: {chunk.purpose}",
                    f"- Reading mode: {chunk.reading_mode}",
                    f"- Time: {chunk.timing.duration_minutes} minutes",
                    "- Resource pages: "
                    + (
                        ", ".join(chunk.reader_page_references)
                        or "Unavailable"
                    ),
                    f"- Source availability: {chunk.source_availability.value}",
                    "",
                    "#### Annotations",
                    _bullets([
                        f"{item.type.value}: {item.student_instruction}"
                        for item in chunk.annotations
                    ]),
                    "",
                    "#### Questions",
                    _questions(chunk.questions),
                ])
                for pause in chunk.pause_points:
                    lines.extend([
                        "",
                        f"#### Pause Point: {pause.id}",
                        f"- Stop location: {pause.stop_location or 'Unavailable'}",
                        f"- Time: {pause.timing.duration_minutes} minutes",
                        f"- Teacher prompt: {pause.teacher_prompt}",
                        f"- Student action: {pause.student_action.instruction}",
                        f"- Discussion format: {pause.discussion_format}",
                        _questions(pause.questions),
                    ])
        lines.extend(["", "## Vocabulary", ""])
        for item in lesson.vocabulary:
            lines.extend([
                f"### {item.word}",
                f"- Pronunciation: {item.pronunciation or 'Unavailable'}",
                f"- Definition: {item.definition.text or 'Unavailable'}",
                "- Student-friendly definition: "
                + (item.student_friendly_definition.text or "Unavailable"),
                f"- Example: {item.example.text or 'Unavailable'}",
                f"- Visual suggestion: {item.visual_suggestion or 'None'}",
                "- ELL support: "
                + (", ".join(item.ell_support) or "None recorded"),
            ])
        lines.extend(["", "## Activity Resources", ""])
        for item in lesson.activity_book:
            lines.extend([
                f"### {item.page}",
                f"- Source availability: {item.source_availability.value}",
                "- Teacher directions:",
                _bullets([value.text for value in item.teacher_directions]),
                "- Expected answers:",
                _bullets([
                    answer.answer for answer in item.expected_answers
                    if answer.answer
                ]),
                "- Common mistakes:",
                _bullets([
                    value.misconception for value in item.common_mistakes
                ]),
            ])
        lines.extend(["", "## Assessment", ""])
        for item in lesson.assessment:
            lines.extend([
                f"### {item.title}",
                f"- Purpose: {item.purpose.text or 'Unavailable'}",
                "- Success criteria:",
                _bullets(item.success_criteria),
            ])
        lines.extend([
            "",
            "## Exit Ticket",
            "",
            (
                lesson.exit_ticket.prompt.text
                or "Unavailable in validated sources."
            ),
            "",
            "### Exit Ticket Success Criteria",
            _bullets(lesson.exit_ticket.success_criteria),
        ])
        lines.extend(["", "## Homework", "", _bullets([
            f"{item.title}: {item.directions}" for item in lesson.homework
        ])])
        lines.extend(["", "## Teacher Reflection", "", _bullets(
            lesson.teacher_reflection.prompts
        )])
        if lesson.warnings:
            lines.extend(["", "## Source and Validation Warnings", "", _bullets(
                lesson.warnings
            )])
        return "\n".join(lines).strip() + "\n"

    def write(self, lesson: CanonicalLesson, directory: str | Path) -> Path:
        path = Path(directory) / "teacher_companion.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(lesson), encoding="utf-8")
        return path


__all__ = ["CanonicalTeacherCompanionRenderer"]
