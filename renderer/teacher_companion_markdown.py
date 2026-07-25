"""Deterministic Markdown rendering for Teacher Companion Guides."""

from __future__ import annotations

from schemas.teacher_companion_schema import TeacherCompanionGuide


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def render_teacher_companion_markdown(guide: TeacherCompanionGuide) -> str:
    """Render a validated structured guide without changing its content."""
    basis = guide.source_basis
    sections = [
        f"# Teacher Companion Guide: {basis.lesson_title}",
        "## Lesson Source",
        "\n".join(
            [
                f"- Curriculum: {basis.curriculum_name}",
                f"- Grade: {basis.grade}",
                f"- Unit: {basis.unit}",
                f"- Lesson: {basis.lesson_number}",
                f"- Student Reader text available: {'Yes' if basis.student_reader_text_available else 'No'}",
                f"- Source references: {', '.join(basis.source_references)}",
            ]
        ),
        "## Teaching Overview",
        guide.teaching_overview,
        "## Why This Lesson Matters",
        guide.why_this_lesson_matters,
        "## Curriculum Facts",
        "\n\n".join(
            f"- {item.fact}\n  - Sources: {', '.join(item.source_references)}"
            for item in guide.curriculum_facts
        ),
        "## Generated Instructional Guidance",
        _bullets(guide.generated_instructional_guidance),
        "## Required Concepts and Terminology",
        "\n\n".join(
            "\n".join(
                [
                    f"### {item.name}",
                    f"**What to teach:** {item.what_to_teach}",
                    f"**Why it matters:** {item.why_it_matters}",
                    f"**How to teach it:** {item.how_to_teach}",
                    f"**Terminology:** {', '.join(item.educational_terminology)}",
                ]
            )
            for item in guide.required_concepts
        ),
        "## Background Knowledge",
        _bullets(guide.background_knowledge),
        "## Vocabulary Guidance",
        "\n\n".join(
            "\n".join(
                [
                    f"### {item.term}",
                    f"**Meaning for the teacher:** {item.meaning_for_teacher}",
                    f"**Student-friendly explanation:** {item.student_friendly_explanation}",
                    f"**How to teach it:** {item.how_to_teach}",
                    f"**Listen for:** {item.what_to_listen_for}",
                ]
            )
            for item in guide.vocabulary_guidance
        ),
        "## Teacher Coaching",
        _bullets(guide.teacher_coaching),
        "## Misconceptions and Corrections",
        "\n\n".join(
            "\n".join(
                [
                    f"### {item.misconception}",
                    f"**Why students may think this:** {item.why_students_may_have_it}",
                    f"**Exact correction language:** {item.exact_teacher_correction}",
                ]
            )
            for item in guide.misconceptions_and_corrections
        ),
        "## Student Supports",
        _bullets(guide.student_supports),
        "## Student Questions",
        "\n\n".join(_render_question(index, item) for index, item in enumerate(guide.student_questions, 1)),
        "## What Mastery Looks Like",
        "\n".join(
            [
                guide.mastery.mastery_statement,
                "",
                "### Observable Indicators",
                _bullets(guide.mastery.observable_indicators),
                "",
                "### Evidence to Collect",
                _bullets(guide.mastery.evidence_to_collect),
            ]
        ),
        "## Grounding Notes",
        _bullets(guide.grounding_notes) if guide.grounding_notes else "- None.",
    ]
    return "\n\n".join(sections).rstrip() + "\n"


def _render_question(index, question) -> str:
    misconceptions = "\n".join(
        "\n".join(
            [
                f"- **Misconception:** {item.misconception}",
                f"  - **Why:** {item.why_students_may_have_it}",
                f"  - **Exact teacher correction:** {item.exact_teacher_correction}",
            ]
        )
        for item in question.likely_misconceptions
    )
    return "\n".join(
        [
            f"### {index}. {question.exact_question}",
            f"**Why ask it:** {question.why_the_question_is_asked}",
            f"**Answer basis:** {question.answer_basis}",
            f"**Sources:** {', '.join(question.source_references) or 'Generated guidance only'}",
            "",
            "**Possible student answers:**",
            _bullets(question.possible_student_answers),
            "",
            f"**Excellent model answer:** {question.excellent_model_answer}",
            f"**Why it is correct:** {question.why_the_model_answer_is_correct}",
            "",
            "**Listen for:**",
            _bullets(question.what_the_teacher_should_listen_for),
            "",
            "**Likely misconceptions and corrections:**",
            misconceptions,
            "",
            "**Scaffolded follow-up questions:**",
            _bullets(question.scaffolded_follow_up_questions),
            "",
            f"**Extension question:** {question.extension_question}",
        ]
    )


__all__ = ["render_teacher_companion_markdown"]
