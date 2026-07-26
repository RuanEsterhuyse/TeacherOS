"""Deterministic Google Slides adapter for structured teaching packages."""

from __future__ import annotations

from typing import Any

from models.lesson import Lesson
from models.slide import Slide
from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.teaching_package_schema import (
    StructuredTeachingPackage,
    TeachingSourceReference,
)


LAYOUT_BY_TYPE = {
    "title": "title",
    "agenda": "agenda",
    "objectives": "objective",
    "essential question": "discussion",
    "warm-up": "activity",
    "background knowledge": "background knowledge",
    "vocabulary": "vocabulary",
    "reading purpose": "reading",
    "reading directions": "reading",
    "reading questions": "discussion",
    "discussion": "discussion",
    "activity": "activity",
    "writing": "writing",
    "assessment": "assessment",
    "wrap-up": "closure",
    "homework": "homework",
    "transition": "instructions",
}


def _source_label(value: TeachingSourceReference) -> str:
    location = (
        f"PDF p. {value.display_page_number}"
        if value.display_page_number is not None
        else value.printed_page or value.stable_source_id
    )
    return f"{value.source_document} ({location})"


def package_to_google_lesson(
    package: StructuredTeachingPackage,
) -> Lesson:
    """Map exactly one structured slide to exactly one editable Google slide."""
    slides = []
    agenda = {
        value.agenda_item_id: value for value in package.agenda
    }
    steps = {
        value.agenda_item_id: value for value in package.teaching_steps
    }
    questions = {
        value.question_id: value for value in package.questions
    }
    for value in package.student_slides:
        notes = list(value.speaker_notes)
        if value.agenda_item_id in steps:
            step = steps[value.agenda_item_id]
            notes.extend(
                f"Teacher action: {item.text}"
                for item in step.teacher_actions
            )
            notes.append(f"Transition: {step.transition.text}")
        for question_id in value.question_ids:
            question = questions[question_id]
            notes.extend([
                f"Question {question_id}: {question.exact_question.text}",
                f"Expected answer (teacher only): "
                f"{question.expected_answer.text}",
                f"Follow-up: {question.follow_up.text}",
                f"ELD sentence frame: {question.eld_sentence_frame.text}",
            ])
        if value.agenda_item_id in agenda:
            duration = agenda[value.agenda_item_id].duration_minutes
        else:
            duration = None
        slides.append(Slide(
            slide_id=value.slide_id,
            title=value.title,
            student_content=value.student_prompt or "",
            bullet_points=value.visible_student_content,
            speaker_notes="\n".join(notes),
            timing=duration if duration and duration > 0 else None,
            interaction=(
                "Use the Teacher Companion directions. Do not reveal "
                "teacher-only answers."
            ),
            layout_type=LAYOUT_BY_TYPE.get(
                value.slide_type.casefold(), "content"
            ),
            visual_instructions=value.visual_specification,
            source_references=[
                _source_label(item) for item in value.source_references
            ],
        ))
    return Lesson(
        grade=package.dashboard.grade,
        unit=package.dashboard.unit,
        lesson_number=package.dashboard.lesson_number,
        slides=slides,
    )


class TeachingPackageGoogleSlidesPublisher:
    """Publish approved student slides through the existing renderer."""

    def __init__(
        self,
        *,
        renderer: GoogleSlidesRenderer | None = None,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
    ) -> None:
        self.renderer = renderer or GoogleSlidesRenderer(
            credentials_path=credentials_path,
            token_path=token_path,
        )

    def publish(self, package: StructuredTeachingPackage) -> dict[str, Any]:
        if package.validation.status == "fail":
            raise ValueError("Cannot publish a failed teaching package.")
        return self.renderer.create_presentation(
            package_to_google_lesson(package)
        )


__all__ = [
    "LAYOUT_BY_TYPE",
    "TeachingPackageGoogleSlidesPublisher",
    "package_to_google_lesson",
]
