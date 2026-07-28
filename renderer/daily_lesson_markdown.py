"""Human-readable Daily Lesson Generator Markdown renderers."""

from __future__ import annotations

from schemas.daily_lesson_schema import (
    DAILY_GUIDANCE_LABEL,
    DailyLessonPackage,
    DailySpeakerNotes,
    DailyTeacherPlaybook,
)
from schemas.pasted_lesson_schema import SourceReference


DESIGN_LANGUAGE = (
    "Warm cream background: #F7F4EE\n"
    "Aqua: #67C7D8\n"
    "Deep teal: #3B97A8\n"
    "Coral: #E97F7C\n"
    "Charcoal: #2E2E2E\n"
    "Light gray: #D9D9D9\n"
    "Use white rounded cards, soft restrained shadows, generous whitespace, "
    "large readable typography, a modern professional educational design, "
    "and a consistent visual identity. Keep student-facing text concise."
)


def _bullets(values: list[str], fallback: str = "_Not supplied._") -> str:
    return "\n".join(f"- {value}" for value in values) if values else fallback


def format_reference(reference: SourceReference) -> str:
    label = reference.source_type.replace("_", " ").title()
    if reference.page_start is not None:
        label += f" pp. {reference.page_start}"
        if reference.page_end != reference.page_start:
            label += f"–{reference.page_end}"
    if reference.section:
        label += f" · {reference.section}"
    if reference.activity_reference:
        label += f" · {reference.activity_reference}"
    return label


def _references(values: list[SourceReference]) -> str:
    return _bullets([format_reference(value) for value in values])


def render_speaker_notes(notes: DailySpeakerNotes) -> str:
    sections = [
        ("What the teacher says", notes.teacher_says),
        ("What the teacher does", notes.teacher_does),
        ("Discussion prompts", notes.discussion_prompts),
        ("Anticipated responses", notes.anticipated_responses),
        ("Misconception support", notes.misconception_support),
        ("Checks for understanding", notes.checks_for_understanding),
    ]
    output = []
    if notes.timing_minutes is not None:
        output.append(f"**Timing:** {notes.timing_minutes} minutes")
    for heading, values in sections:
        if values:
            output.extend((f"**{heading}:**", _bullets(values)))
    if notes.transition:
        output.append(f"**Transition:** {notes.transition}")
    if notes.source_references:
        output.extend(("**Source references:**", _references(
            notes.source_references
        )))
    return "\n\n".join(output)


def render_teacher_playbook(playbook: DailyTeacherPlaybook) -> str:
    identity = playbook.lesson_information
    output = [
        f"# {identity.lesson_title}",
        "",
        f"Grade {identity.grade} · Unit {identity.unit} · "
        f"Lesson {identity.lesson_number}",
    ]
    if identity.teacher_guide_page_start is not None:
        output.append(
            f"Teacher Guide pp. {identity.teacher_guide_page_start}"
            f"–{identity.teacher_guide_page_end}"
        )
    output.extend([
        "",
        "> Curriculum facts and exact references come from the pasted source. "
        f"Instructional coaching is labeled {DAILY_GUIDANCE_LABEL}.",
        "",
        "## What This Lesson Is Really About",
        "",
        playbook.lesson_meaning,
        "",
        "## What Students Should Leave Understanding",
        "",
        _bullets(playbook.leave_understanding),
    ])
    for heading, value in (
        ("Essential Question", playbook.essential_question),
        ("Content Objective", playbook.content_objective),
        ("Language Objective", playbook.language_objective),
    ):
        if value:
            output.extend(("", f"## {heading}", "", value))
    output.extend((
        "",
        "## Success Criteria",
        "",
        _bullets(playbook.success_criteria),
        "",
        "## Lesson Agenda and Timing",
        "",
    ))
    if playbook.agenda:
        for item in playbook.agenda:
            timing = (
                f" — {item.duration_minutes} min"
                if item.duration_minutes is not None else ""
            )
            output.append(f"- **{item.title}**{timing}")
            if item.purpose:
                output.append(f"  - {item.purpose}")
    else:
        output.append("_Not supplied._")
    output.extend(("", "## Materials", "", _bullets(playbook.materials)))
    if playbook.vocabulary:
        output.extend(("", "## Vocabulary", ""))
        for word in playbook.vocabulary:
            definition = word.student_friendly_definition or "Definition unavailable."
            output.append(f"- **{word.term}:** {definition}")
            if word.teacher_guidance:
                output.append(f"  - {DAILY_GUIDANCE_LABEL} {word.teacher_guidance}")
    output.extend((
        "",
        "## Teacher Survival Guide",
        "",
        _bullets([
            f"{DAILY_GUIDANCE_LABEL} {value}"
            for value in playbook.teacher_survival_guide
        ]),
        "",
        "## Activity-by-Activity Guide",
    ))
    for index, activity in enumerate(playbook.activities, 1):
        timing = (
            f" · {activity.duration_minutes} min"
            if activity.duration_minutes is not None else ""
        )
        output.extend((
            "",
            f"### {index}. {activity.title}{timing}",
            "",
            f"**Purpose:** {activity.purpose}",
            "",
            f"**Teacher goal:** {DAILY_GUIDANCE_LABEL} {activity.teacher_goal}",
            "",
            "**What to say:**",
            "",
            _bullets([
                f"{DAILY_GUIDANCE_LABEL} {value}"
                for value in activity.what_to_say
            ]),
        ))
        for question in activity.questions:
            output.extend((
                "",
                f"**Question:** {question.question}",
                "",
                f"**Why ask it:** {DAILY_GUIDANCE_LABEL} {question.why_ask}",
                "",
                "**Possible strong responses:**",
                "",
                _bullets(question.strong_responses),
                "",
                "**Possible typical responses:**",
                "",
                _bullets(question.typical_responses),
                "",
                "**Possible weak responses:**",
                "",
                _bullets(question.weak_responses),
                "",
                f"**How to respond:** {DAILY_GUIDANCE_LABEL} "
                f"{question.teacher_response}",
            ))
            if question.misconceptions:
                output.extend((
                    "",
                    "**Common misconceptions:**",
                    "",
                    _bullets(question.misconceptions),
                ))
        for heading, values in (
            ("Examples and analogies", activity.examples_and_analogies),
            ("ELD supports", activity.eld_supports),
            ("Sentence frames", activity.sentence_frames),
            ("Checks for understanding", activity.checks_for_understanding),
            ("Look-fors", activity.look_fors),
            ("Ready-to-move-on criteria", activity.ready_to_move_on_criteria),
        ):
            if values:
                output.extend(("", f"**{heading}:**", "", _bullets(values)))
        if activity.transition:
            output.extend((
                "",
                f"**Transition:** {DAILY_GUIDANCE_LABEL} {activity.transition}",
            ))
        if activity.source_references:
            output.extend((
                "",
                "**Source references:**",
                "",
                _references(activity.source_references),
            ))
    for heading, values in (
        ("Exit Ticket", playbook.exit_ticket),
        ("Homework", playbook.homework),
        ("End-of-Day Teacher Reflection", playbook.teacher_reflection),
        ("Unavailable Information", playbook.unavailable_information),
    ):
        if values:
            output.extend(("", f"## {heading}", "", _bullets(values)))
    if playbook.source_references:
        output.extend((
            "",
            "## Source References",
            "",
            _references(playbook.source_references),
        ))
    return "\n".join(output).rstrip() + "\n"


def build_gemini_prompt(slide, *, include_speaker_notes: bool = True) -> str:
    student_text = "\n".join(
        f"- {value}" for value in slide.exact_student_facing_text
    )
    references = "\n".join(
        f"- {format_reference(value)}" for value in slide.source_references
    ) or "- No specific source reference supplied."
    notes = render_speaker_notes(slide.speaker_notes)
    prompt = f"""Create exactly one editable presentation slide.

SLIDE {slide.slide_number}
Title: {slide.title}
Instructional purpose: {slide.instructional_purpose}
Related activity: {slide.related_activity or "Lesson-level"}

DESIGN LANGUAGE — APPLY IN FULL
{DESIGN_LANGUAGE}

EXACT STUDENT-FACING TEXT
Use only the following visible text. Do not rewrite it or add lesson content.
{student_text}

LAYOUT
{slide.suggested_layout}

VISUAL DIRECTION
{slide.suggested_visual or "Use simple editable shapes only; do not invent factual visuals."}
Do not invent lesson facts, quotations, page numbers, answer keys, maps, covers,
or source-document images. Do not place teacher guidance on the slide.

SOURCE REFERENCES
{references}
"""
    if include_speaker_notes:
        prompt += f"""
SPEAKER NOTES — PLACE IN SPEAKER NOTES, NEVER ON THE SLIDE
{notes or "No speaker notes supplied."}
"""
    return prompt.rstrip() + "\n"


def render_slide_prompts(package: DailyLessonPackage) -> str:
    output = [
        f"# Gemini Slide Prompts — {package.source_identity.lesson_title}",
        "",
        "Copy one prompt at a time into Gemini inside your presentation editor.",
    ]
    for item in package.gemini_slide_prompts:
        output.extend((
            "",
            "==============================",
            f"SLIDE {item.slide_number}",
            "==============================",
            "",
            item.prompt.rstrip(),
            "",
            "## Speaker Notes",
            "",
            item.speaker_notes_markdown or "_No notes supplied._",
        ))
    return "\n".join(output).rstrip() + "\n"


__all__ = [
    "DESIGN_LANGUAGE",
    "build_gemini_prompt",
    "format_reference",
    "render_slide_prompts",
    "render_speaker_notes",
    "render_teacher_playbook",
]
