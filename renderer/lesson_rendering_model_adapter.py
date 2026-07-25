"""Strict one-to-one adapter from Phase 5A models to slide instructions."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from curriculum.intelligence.ids import content_digest
from schemas.lesson_rendering_model_schema import (
    AnswerRevealBehavior,
    ContentOrigin,
    LessonRenderingModel,
    LessonRenderingValidationReport,
    RenderingReadinessStatus,
    SlideScope,
    SlideType,
)


ADAPTER_VERSION = "1.0"
RENDER_INSTRUCTION_SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RenderLayout(str, Enum):
    TITLE = "title"
    TWO_COLUMN = "two_column"
    SIMPLE_CONTENT = "simple_content"
    DIVIDER = "divider"
    VOCABULARY_CARDS = "vocabulary_cards"
    READING_CHECKPOINT = "reading_checkpoint"
    QUESTION = "question"
    DISCUSSION = "discussion"
    ACTIVITY_STEPS = "activity_steps"
    EXIT_TICKET = "exit_ticket"
    HOMEWORK = "homework"


SLIDE_TYPE_LAYOUTS: dict[SlideType, RenderLayout] = {
    SlideType.TITLE: RenderLayout.TITLE,
    SlideType.OBJECTIVES: RenderLayout.TWO_COLUMN,
    SlideType.AGENDA: RenderLayout.SIMPLE_CONTENT,
    SlideType.MATERIALS: RenderLayout.TWO_COLUMN,
    SlideType.DAY_DIVIDER: RenderLayout.DIVIDER,
    SlideType.CONTEXT: RenderLayout.SIMPLE_CONTENT,
    SlideType.BOOK_OR_TEXT_INTRODUCTION: RenderLayout.SIMPLE_CONTENT,
    SlideType.VOCABULARY: RenderLayout.VOCABULARY_CARDS,
    SlideType.READING_DIRECTIONS: RenderLayout.READING_CHECKPOINT,
    SlideType.READING_CHUNK: RenderLayout.READING_CHECKPOINT,
    SlideType.TEXT_DEPENDENT_QUESTION: RenderLayout.QUESTION,
    SlideType.DISCUSSION: RenderLayout.DISCUSSION,
    SlideType.CHECK_FOR_UNDERSTANDING: RenderLayout.QUESTION,
    SlideType.ACTIVITY_BOOK: RenderLayout.ACTIVITY_STEPS,
    SlideType.WRITING: RenderLayout.SIMPLE_CONTENT,
    SlideType.SYNTHESIS: RenderLayout.SIMPLE_CONTENT,
    SlideType.ASSESSMENT: RenderLayout.EXIT_TICKET,
    SlideType.HOMEWORK: RenderLayout.HOMEWORK,
    SlideType.TRANSITION: RenderLayout.DIVIDER,
}


class RenderVisualInstruction(StrictModel):
    description: str = Field(min_length=1)
    asset_reference: Optional[str] = None
    placeholder_text: Optional[str] = None
    required: bool


class NormalizedSlideInstruction(StrictModel):
    slide_number: int = Field(ge=1)
    source_slide_id: str = Field(min_length=1)
    phase_id: Optional[str] = None
    scope: SlideScope
    slide_type: SlideType
    layout_name: RenderLayout
    title: str = Field(min_length=1)
    subtitle: Optional[str] = None
    content_lines: list[str] = Field(default_factory=list)
    cue_lines: list[str] = Field(default_factory=list)
    footer: Optional[str] = None
    notes_text: str = Field(min_length=1)
    question_ids: list[str] = Field(default_factory=list)
    answer_ids: list[str] = Field(default_factory=list)
    source_node_ids: list[str] = Field(default_factory=list)
    resource_references: list[str] = Field(default_factory=list)
    visuals: list[RenderVisualInstruction] = Field(default_factory=list)
    visible_text_digest: str = Field(min_length=1)
    notes_digest: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


def _notes_text(slide, resource_references: list[str]) -> str:
    notes = slide.teacher_notes
    sections: list[tuple[str, list[str]]] = []

    def add(heading: str, values: list[str]) -> None:
        if values:
            sections.append((heading, values))

    add("TEACHER DIRECTIONS", [
        value.text for value in notes.publisher_directions
    ])
    add("PUBLISHER ANSWERS", [
        f"[{answer_id}] {answer.text}"
        for answer_id, answer in zip(
            notes.source_answer_ids, notes.source_answers
        )
    ])
    ai_heading = "AI-GENERATED TEACHER SUPPORT — DRAFT/UNREVIEWED"
    add(ai_heading + "\nFACILITATION NOTES", [
        value.text for value in notes.facilitation_notes
    ])
    add(ai_heading + "\nCHECKS FOR UNDERSTANDING", [
        value.text for value in notes.checks_for_understanding
    ])
    add(ai_heading + "\nLANGUAGE SUPPORTS", [
        value.text for value in notes.language_supports
    ])
    add(ai_heading + "\nDIFFERENTIATION", [
        value.text for value in notes.differentiation_supports
    ])
    if notes.transition:
        add("TRANSITION", [notes.transition.text])
    add("SOURCE REFERENCES", list(slide.source_node_ids))
    add("RESOURCE REFERENCES", resource_references)
    add("PROVENANCE", list(notes.provenance_references))
    add("INTERNAL WARNINGS", [
        *notes.warnings, *slide.warnings
    ])
    add("RENDER METADATA", [
        f"Source slide ID: {slide.slide_id}",
        f"Question IDs: {', '.join(slide.question_ids) or 'None'}",
        f"Answer IDs: {', '.join(slide.answer_ids) or 'None'}",
    ])
    rendered = []
    for heading, values in sections:
        rendered.append(
            heading + "\n" + "\n".join(f"• {value}" for value in values)
        )
    return "\n\n".join(rendered)


class LessonRenderingModelSlidesAdapter:
    """Convert a validated model without adding, deleting, or rewriting slides."""

    def adapt(
        self,
        model: LessonRenderingModel,
        validation: LessonRenderingValidationReport,
        *,
        asset_registry: dict[str, str] | None = None,
    ) -> list[NormalizedSlideInstruction]:
        asset_registry = asset_registry or {}
        self._validate_input(model, validation)
        instructions = [
            self._instruction(slide, asset_registry)
            for slide in sorted(
                model.slides, key=lambda value: value.slide_number
            )
        ]
        if len(instructions) != len(model.slides):
            raise ValueError("Render-instruction count differs from slide count.")
        if [value.source_slide_id for value in instructions] != [
            value.slide_id for value in model.slides
        ]:
            raise ValueError("Render instructions changed slide order or identity.")
        blockers = [
            blocker
            for instruction in instructions
            for blocker in instruction.blockers
        ]
        if blockers:
            raise ValueError("; ".join(blockers))
        return instructions

    def _validate_input(
        self,
        model: LessonRenderingModel,
        validation: LessonRenderingValidationReport,
    ) -> None:
        if model.readiness_status == RenderingReadinessStatus.BLOCKED:
            raise ValueError("LessonRenderingModel is blocked.")
        if validation.status == "fail":
            raise ValueError("LessonRenderingModel validation failed.")
        if validation.lesson_id != model.lesson_id:
            raise ValueError("Validation lesson identity does not match model.")
        if validation.model_digest != model.artifact_digest:
            raise ValueError("Validation artifact digest does not match model.")
        if len(model.slide_coverage) != len(model.slides):
            raise ValueError("Slide coverage count differs from slide count.")
        slide_ids = [value.slide_id for value in model.slides]
        if len(slide_ids) != len(set(slide_ids)):
            raise ValueError("Duplicate source slide ID.")
        if [value.slide_number for value in model.slides] != list(
            range(1, len(model.slides) + 1)
        ):
            raise ValueError("Slide numbers are not contiguous.")
        coverage_ids = [value.slide_id for value in model.slide_coverage]
        if coverage_ids != slide_ids or len(coverage_ids) != len(
            set(coverage_ids)
        ):
            raise ValueError("Slide coverage is incomplete or duplicated.")
        phases = {value.phase_id for value in model.phases}
        question_ids = {
            value.question_id for value in model.question_coverage
        }
        answer_ids = {
            answer_id
            for value in model.question_coverage
            for answer_id in value.source_answer_ids
        }
        for slide in model.slides:
            if (
                slide.scope == SlideScope.PHASE
                and slide.phase_id not in phases
            ):
                raise ValueError(
                    f"Unknown phase reference on slide {slide.slide_id}."
                )
            if (
                slide.scope == SlideScope.LESSON_STRUCTURE
                and slide.phase_id is not None
            ):
                raise ValueError(
                    f"Lesson-structure slide has phase ID: {slide.slide_id}."
                )
            if not set(slide.question_ids) <= question_ids:
                raise ValueError(
                    f"Unknown question ID on slide {slide.slide_id}."
                )
            if not set(slide.answer_ids) <= answer_ids:
                raise ValueError(
                    f"Unknown answer ID on slide {slide.slide_id}."
                )
            visible = slide.student_visible_content
            for value in [
                visible.title, visible.subtitle, visible.reading_cue,
                visible.response_format, visible.footer,
                *visible.directions, *visible.statements,
            ]:
                if (
                    value is not None
                    and value.origin
                    == ContentOrigin.AI_GENERATED_TEACHER_SUPPORT
                ):
                    raise ValueError(
                        f"AI teacher support is student-visible: {slide.slide_id}."
                    )
            if len(slide.teacher_notes.source_answer_ids) != len(
                slide.teacher_notes.source_answers
            ):
                raise ValueError(
                    f"Publisher answers cannot be mapped losslessly: {slide.slide_id}."
                )
            if any(
                value.origin != ContentOrigin.PUBLISHER_SOURCE
                for value in slide.teacher_notes.source_answers
            ):
                raise ValueError(
                    f"Publisher-only answer field has wrong origin: {slide.slide_id}."
                )
            if any(
                value.origin != ContentOrigin.PUBLISHER_SOURCE
                for value in slide.teacher_notes.publisher_directions
            ):
                raise ValueError(
                    "Publisher-only direction field has wrong origin: "
                    f"{slide.slide_id}."
                )
            ai_support = [
                *slide.teacher_notes.facilitation_notes,
                *slide.teacher_notes.checks_for_understanding,
                *slide.teacher_notes.language_supports,
                *slide.teacher_notes.differentiation_supports,
            ]
            if any(
                value.origin
                != ContentOrigin.AI_GENERATED_TEACHER_SUPPORT
                for value in ai_support
            ):
                raise ValueError(
                    f"AI-support field has wrong origin: {slide.slide_id}."
                )
            if slide.slide_type not in SLIDE_TYPE_LAYOUTS:
                raise ValueError(
                    f"Unsupported slide type: {slide.slide_type!r}."
                )

    def _instruction(
        self,
        slide,
        asset_registry: dict[str, str],
    ) -> NormalizedSlideInstruction:
        view = slide.student_visible_content
        content_lines = [
            *[value.text for value in view.directions],
            *[value.text for value in view.statements],
        ]
        if slide.activity_book_references:
            content_lines.append(
                "Resources: " + ", ".join(slide.activity_book_references)
            )
        cue_lines = []
        if view.reading_cue:
            cue_lines.append(view.reading_cue.text)
        if view.response_format:
            cue_lines.append(view.response_format.text)
        visuals = []
        resource_references = []
        blockers = list(slide.blockers)
        warnings = list(slide.warnings)
        for value in slide.visual_asset_requirements:
            reference = (
                asset_registry.get(value.resource_id or "")
                or asset_registry.get(value.assignment_id or "")
            )
            if reference:
                visuals.append(RenderVisualInstruction(
                    description=value.description,
                    asset_reference=reference,
                    required=value.required,
                ))
            elif self._is_resource_reference(value):
                resource_references.append(
                    f"{value.description} "
                    f"[resource={value.resource_id or 'unassigned'}; "
                    f"assignment={value.assignment_id or 'unassigned'}]"
                )
                warnings.append(
                    "resource_reference_not_visual:"
                    f"{value.resource_id or value.assignment_id}"
                )
            elif value.required:
                blockers.append(
                    f"required_visual_unavailable:{slide.slide_id}:"
                    f"{value.resource_id or value.assignment_id}"
                )
            elif value.neutral_placeholder_allowed:
                visuals.append(RenderVisualInstruction(
                    description=value.description,
                    placeholder_text="Optional visual — add approved image",
                    required=False,
                ))
            else:
                warnings.append(
                    "Optional visual is unavailable and placeholders are disabled."
                )
        notes = _notes_text(slide, resource_references)
        visible_payload = {
            "title": view.title.text,
            "subtitle": view.subtitle.text if view.subtitle else None,
            "content_lines": content_lines,
            "cue_lines": cue_lines,
            "footer": view.footer.text if view.footer else None,
        }
        return NormalizedSlideInstruction(
            slide_number=slide.slide_number,
            source_slide_id=slide.slide_id,
            phase_id=slide.phase_id,
            scope=slide.scope,
            slide_type=slide.slide_type,
            layout_name=SLIDE_TYPE_LAYOUTS[slide.slide_type],
            title=view.title.text,
            subtitle=view.subtitle.text if view.subtitle else None,
            content_lines=content_lines,
            cue_lines=cue_lines,
            footer=view.footer.text if view.footer else None,
            notes_text=notes,
            question_ids=slide.question_ids,
            answer_ids=slide.answer_ids,
            source_node_ids=slide.source_node_ids,
            resource_references=resource_references,
            visuals=visuals,
            visible_text_digest=content_digest(visible_payload),
            notes_digest=content_digest(notes),
            warnings=warnings,
            blockers=blockers,
        )

    @staticmethod
    def _is_resource_reference(value) -> bool:
        """Recognize resource indexes that do not identify an image asset."""
        identifiers = " ".join(filter(None, (
            value.resource_id, value.assignment_id, value.description,
        ))).casefold()
        return "online resource" in identifiers


__all__ = [
    "ADAPTER_VERSION", "LessonRenderingModelSlidesAdapter",
    "NormalizedSlideInstruction", "RENDER_INSTRUCTION_SCHEMA_VERSION",
    "RenderLayout", "RenderVisualInstruction", "SLIDE_TYPE_LAYOUTS",
]
