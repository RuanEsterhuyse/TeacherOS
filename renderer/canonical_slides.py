"""Project canonical lesson slide mappings without instructional invention."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from renderer.lesson_renderer import LessonRenderer
from schemas.canonical_lesson_schema import CanonicalLesson, LessonBlock
from schemas.presentation_design_schema import (
    ImagePlacement,
    InteractionPlan,
    InteractionType,
    PresentationDesignOutput,
    PresentationSlide,
    ResponseMode,
    SlideDesign,
    SlideLayout,
    StudentView,
    TeacherNotes,
    TextDensity,
    VisualPlan,
)


def _mappings(lesson: CanonicalLesson):
    values = []
    for block in lesson.lesson_blocks:
        values.extend((mapping, block, None) for mapping in block.slide_mappings)
        for chunk in block.reading_chunks:
            values.extend(
                (mapping, block, chunk) for mapping in chunk.slide_mappings
            )
    return sorted(values, key=lambda item: item[0].sequence)


def _guidance_text(block: LessonBlock, name: str) -> list[str]:
    return [item.text for item in getattr(block.teacher_guidance, name)]


def speaker_notes_for(lesson: CanonicalLesson) -> dict[str, Any]:
    notes = []
    for mapping, block, chunk in _mappings(lesson):
        questions = list(block.questions)
        if chunk:
            questions.extend(chunk.questions)
        notes.append({
            "slide_id": mapping.slide_id,
            "lesson_block_id": block.id,
            "reading_chunk_id": chunk.id if chunk else None,
            "instructional_purpose": block.objective.text,
            "introduction": _guidance_text(block, "introduction"),
            "modeling": _guidance_text(block, "modeling"),
            "directions": _guidance_text(block, "directions"),
            "questioning": [item.question_text for item in questions],
            "expected_answers": [
                answer.answer
                for question in questions
                for answer in question.expected_answers
                if answer.answer
            ],
            "monitoring_notes": _guidance_text(block, "monitoring_notes"),
            "wida_supports": block.wida_supports,
            "transition": _guidance_text(block, "transition"),
            "closure": _guidance_text(block, "closure"),
            "materials": block.materials,
        })
    return {
        "schema_version": lesson.schema_version,
        "source_digest": lesson.source_digest,
        "speaker_notes": notes,
    }


def slides_for(lesson: CanonicalLesson) -> dict[str, Any]:
    return {
        "schema_version": lesson.schema_version,
        "source_digest": lesson.source_digest,
        "slides": [
            {
                **mapping.model_dump(mode="json"),
                "block_title": block.title,
                "reading_chunk_title": chunk.title if chunk else None,
            }
            for mapping, block, chunk in _mappings(lesson)
        ],
    }


def canonical_to_presentation_design(
    lesson: CanonicalLesson,
) -> PresentationDesignOutput:
    notes_by_id = {
        item["slide_id"]: item
        for item in speaker_notes_for(lesson)["speaker_notes"]
    }
    slides = []
    for mapping, block, chunk in _mappings(lesson):
        try:
            layout = SlideLayout(mapping.layout)
        except ValueError as error:
            raise ValueError(
                f"Canonical slide uses unsupported layout: {mapping.layout}"
            ) from error
        try:
            interaction_type = InteractionType(
                mapping.interaction or "none"
            )
        except ValueError as error:
            raise ValueError(
                f"Canonical slide uses unsupported interaction: {mapping.interaction}"
            ) from error
        note = notes_by_id[mapping.slide_id]
        questions = note["questioning"]
        slides.append(PresentationSlide(
            slide_id=mapping.slide_id,
            sequence_number=mapping.sequence,
            slide_type=mapping.slide_type,
            student_view=StudentView(
                title=mapping.title,
                body_text=(
                    mapping.student_content[0]
                    if mapping.student_content
                    else None
                ),
                bullet_points=list(mapping.student_content[1:]),
            ),
            teacher_notes=TeacherNotes(
                instructional_purpose=note["instructional_purpose"],
                teacher_script="\n".join(
                    note["introduction"] + note["modeling"]
                ) or None,
                teacher_directions=note["directions"],
                questions=questions,
                anticipated_responses=note["expected_answers"],
                checks_for_understanding=note["monitoring_notes"],
                eld_supports=note["wida_supports"],
                transition="\n".join(note["transition"]) or None,
            ),
            design=SlideDesign(
                layout=layout,
                text_density=TextDensity.LIGHT,
                image_position=(
                    ImagePlacement.RIGHT
                    if mapping.visual_direction
                    else ImagePlacement.NONE
                ),
            ),
            visuals=VisualPlan(
                visual_required=bool(mapping.visual_direction),
                visual_description=mapping.visual_direction,
                image_prompt=mapping.image_prompt,
                alt_text=mapping.accessibility_text,
                placement=(
                    ImagePlacement.RIGHT
                    if mapping.visual_direction
                    else ImagePlacement.NONE
                ),
            ),
            interaction=InteractionPlan(
                interaction_type=interaction_type,
                duration_minutes=(
                    mapping.timing.duration_minutes
                    if mapping.timing
                    else None
                ),
                response_mode=ResponseMode.NONE,
            ),
            timing=(
                mapping.timing.duration_minutes
                if mapping.timing
                and mapping.timing.duration_minutes > 0
                else (
                    0 if layout == SlideLayout.DAY_DIVIDER else None
                )
            ),
            materials=list(block.materials),
            source_references=[
                reference.source_id
                for provenance in mapping.source_provenance
                for reference in provenance.references
            ],
            fidelity_classification=(
                "teacheros_added"
                if any(
                    provenance.origin.value
                    == "generated_instructional_guidance"
                    for provenance in mapping.source_provenance
                )
                else "source_adapted"
            ),
        ))
    return PresentationDesignOutput(
        request_id=(
            f"{lesson.lesson_information.curriculum.casefold().replace(' ', '-')}"
            f"-grade-{lesson.lesson_information.grade}"
            f"-unit-{lesson.lesson_information.unit}"
            f"-lesson-{lesson.lesson_information.lesson_number}"
        ),
        lesson_title=lesson.lesson_information.lesson_title,
        slides=slides,
        warnings=list(lesson.warnings),
    )


class CanonicalSlidesRenderer(LessonRenderer[dict[str, Any]]):
    def render(self, lesson: CanonicalLesson) -> dict[str, Any]:
        return slides_for(lesson)

    def write(self, lesson: CanonicalLesson, directory: str | Path) -> Path:
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        slides_path = target / "slides.json"
        notes_path = target / "speaker_notes.json"
        slides_path.write_text(
            json.dumps(slides_for(lesson), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        notes_path.write_text(
            json.dumps(
                speaker_notes_for(lesson), indent=2, ensure_ascii=False
            ) + "\n",
            encoding="utf-8",
        )
        return slides_path


__all__ = [
    "CanonicalSlidesRenderer",
    "canonical_to_presentation_design",
    "slides_for",
    "speaker_notes_for",
]
