"""Structured output for the presentation-design stage."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class StringEnum(str, Enum):
    pass


class SlideLayout(StringEnum):
    TITLE_SLIDE = "title_slide"
    TITLE_HERO = "title_hero"
    DAY_DIVIDER = "day_divider"
    SPLIT_VISUAL = "split_visual"
    QUESTION_FOCUS = "question_focus"
    QUOTE_FOCUS = "quote_focus"
    MAP_FOCUS = "map_focus"
    VOCABULARY_CARDS = "vocabulary_cards"
    THREE_CARD = "three_card"
    READING_CHECKPOINT = "reading_checkpoint"
    DISCUSSION_PROMPT = "discussion_prompt"
    ACTIVITY_STEPS = "activity_steps"
    COMPARISON = "comparison"
    EVIDENCE_CHART = "evidence_chart"
    EXIT_TICKET = "exit_ticket"
    MINIMAL_TEXT = "minimal_text"
    NO_VISUAL = "no_visual"
    OBJECTIVE_AGENDA = "objective_agenda"
    VOCABULARY_VISUAL = "vocabulary_visual"
    IMAGE_AND_PROMPT = "image_and_prompt"
    TEXT_AND_IMAGE = "text_and_image"
    TURN_AND_TALK = "turn_and_talk"
    SENTENCE_FRAME = "sentence_frame"
    READ_ALOUD = "read_aloud"
    QUOTE_ANALYSIS = "quote_analysis"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    PROGRESSIVE_GROUPING = "progressive_grouping"
    HOMEWORK = "homework"
    TWO_COLUMN = "two_column"
    FULL_VISUAL = "full_visual"
    SIMPLE_DIRECTIONS = "simple_directions"


class TextDensity(StringEnum):
    MINIMAL = "minimal"
    LIGHT = "light"
    MODERATE = "moderate"


class VisualType(StringEnum):
    NONE = "none"
    PHOTOGRAPH = "photograph"
    ILLUSTRATION = "illustration"
    MAP = "map"
    DIAGRAM = "diagram"
    CHART = "chart"
    BOOK_COVER = "book_cover"
    ACTIVITY_EXCERPT = "activity_page_excerpt"
    ICONS = "icons"
    TEACHER_ASSET = "teacher_provided_asset"
    CURRICULUM_ASSET = "curriculum_provided_asset"
    EXTERNAL_LICENSED = "external_licensed_asset"


class ImagePlacement(StringEnum):
    NONE = "none"
    FULL_BLEED = "full_bleed"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    BACKGROUND = "background"
    INSET = "inset"


class InteractionType(StringEnum):
    NONE = "none"
    THINK_PAIR_SHARE = "think_pair_share"
    TURN_AND_TALK = "turn_and_talk"
    QUICK_WRITE = "quick_write"
    POLL = "poll"
    COLD_CALL = "cold_call"
    PARTNER_ANNOTATION = "partner_annotation"
    SMALL_GROUP_DISCUSSION = "small_group_discussion"
    EVIDENCE_COLLECTION = "evidence_collection"
    INDEPENDENT_RESPONSE = "independent_response"
    EXIT_TICKET = "exit_ticket"


class Grouping(StringEnum):
    WHOLE_CLASS = "whole_class"
    INDIVIDUAL = "individual"
    PARTNERS = "partners"
    SMALL_GROUP = "small_group"
    FLEXIBLE = "flexible"


class ResponseMode(StringEnum):
    NONE = "none"
    ORAL = "oral"
    WRITTEN = "written"
    GESTURE = "gesture"
    DIGITAL = "digital"
    ANNOTATION = "annotation"
    PERFORMANCE = "performance"


class StudentView(BaseModel):
    title: str = ""
    subtitle: Optional[str] = None
    body_text: Optional[str] = None
    bullet_points: list[str] = Field(default_factory=list)
    prompt: Optional[str] = None
    quotation: Optional[str] = None
    vocabulary_terms: list[str] = Field(default_factory=list)
    sentence_frames: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)
    footer_text: Optional[str] = None

    def all_text(self) -> str:
        parts = [self.title, self.subtitle, self.body_text, self.prompt, self.quotation,
                 self.footer_text, *self.bullet_points, *self.vocabulary_terms,
                 *self.sentence_frames, *self.directions]
        return " ".join(part for part in parts if part)


class TeacherNotes(BaseModel):
    instructional_purpose: Optional[str] = None
    teacher_script: Optional[str] = None
    teacher_directions: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    anticipated_responses: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    checks_for_understanding: list[str] = Field(default_factory=list)
    eld_supports: list[str] = Field(default_factory=list)
    differentiation: list[str] = Field(default_factory=list)
    transition: Optional[str] = None
    pacing_notes: Optional[str] = None
    safety_or_sensitivity_notes: Optional[str] = None

    def as_text(self) -> str:
        values = self.model_dump(exclude_none=True)
        return "\n".join(f"{key.replace('_', ' ').title()}: " +
                         ("; ".join(value) if isinstance(value, list) else value)
                         for key, value in values.items() if value)


class SlideDesign(BaseModel):
    layout: SlideLayout
    background_style: Optional[str] = None
    visual_hierarchy: Optional[str] = None
    title_emphasis: Optional[str] = None
    content_alignment: Optional[str] = None
    image_position: ImagePlacement = ImagePlacement.NONE
    text_density: TextDensity = TextDensity.LIGHT
    max_words: int = Field(default=45, ge=1, le=100)
    notes_for_renderer: Optional[str] = None


class VisualPlan(BaseModel):
    visual_required: bool = False
    visual_type: VisualType = VisualType.NONE
    visual_description: Optional[str] = None
    image_prompt: Optional[str] = None
    source_asset_reference: Optional[str] = None
    icon_concepts: list[str] = Field(default_factory=list)
    diagram_description: Optional[str] = None
    alt_text: Optional[str] = None
    placement: ImagePlacement = ImagePlacement.NONE
    crop_style: Optional[str] = None


class InteractionPlan(BaseModel):
    interaction_type: InteractionType = InteractionType.NONE
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    grouping: Optional[Grouping] = None
    student_directions: list[str] = Field(default_factory=list)
    response_mode: ResponseMode = ResponseMode.NONE
    accountability_method: Optional[str] = None


class PresentationSlide(BaseModel):
    slide_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=1)
    slide_type: str = Field(min_length=1)
    student_view: StudentView
    teacher_notes: TeacherNotes = Field(default_factory=TeacherNotes)
    design: SlideDesign
    visuals: VisualPlan = Field(default_factory=VisualPlan)
    interaction: InteractionPlan = Field(default_factory=InteractionPlan)
    timing: Optional[int] = Field(default=None, ge=0)
    day: Optional[int] = Field(default=None, ge=1)
    materials: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    fidelity_classification: str = Field(pattern="^(source_required|source_adapted|teacheros_added)$")

    @model_validator(mode="after")
    def validate_semantic_timing(self):
        """Section dividers have no duration; all explicit normal timings are positive."""
        is_divider = (self.slide_type.lower().replace("_", " ") == "day divider"
                      or self.design.layout == SlideLayout.DAY_DIVIDER)
        if is_divider:
            if self.timing is not None:
                self.timing = 0
        elif self.timing == 0:
            raise ValueError("instructional slide timing must be positive when provided")
        return self


class PresentationDesignOutput(BaseModel):
    request_id: str
    lesson_title: str = ""
    theme: str = "grade_8_modern"
    slides: list[PresentationSlide]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_and_continuous(self):
        ids = [slide.slide_id for slide in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("slide IDs must be unique")
        if [slide.sequence_number for slide in self.slides] != list(range(1, len(self.slides) + 1)):
            raise ValueError("slide sequence numbers must be continuous and ordered")
        return self
