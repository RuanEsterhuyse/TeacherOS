"""Deterministic visual-composition contract between presentation design and rendering."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class SlideFamily(str, Enum):
    CINEMATIC_TITLE="cinematic_title"; SECTION_DIVIDER="section_divider"; LESSON_GOALS_CARDS="lesson_goals_cards"
    IMAGE_HOOK="image_hook"; ANNOTATED_MAP="annotated_map"; VOCABULARY_CARDS="vocabulary_cards"
    VOCABULARY_IMAGE_GRID="vocabulary_image_grid"; BOOK_OR_TEXT_INTRO="book_or_text_intro"
    READ_ALOUD_FOCUS="read_aloud_focus"; SENTENCE_FRAME_SPOTLIGHT="sentence_frame_spotlight"
    QUOTE_ANALYSIS="quote_analysis"; EVIDENCE_COLLECTION="evidence_collection"
    DISCUSSION_QUESTION="discussion_question"; PROGRESSIVE_GROUPING="progressive_grouping"
    COMPARE_CONTRAST="compare_contrast"; CAUSE_EFFECT="cause_effect"; TIMELINE="timeline"
    SEQUENCE_STEPS="sequence_steps"; MODEL_EXAMPLE="model_example"; GUIDED_PRACTICE="guided_practice"
    INDEPENDENT_PRACTICE="independent_practice"; QUICK_CHECK="quick_check"; EXIT_TICKET="exit_ticket"
    HOMEWORK_SUMMARY="homework_summary"


class ComponentType(str, Enum):
    HERO_IMAGE="hero_image"; TITLE_BLOCK="title_block"; SUBTITLE="subtitle"; OBJECTIVE_CHIP="objective_chip"
    PROMPT_CARD="prompt_card"; VOCABULARY_CARD="vocabulary_card"; ICON_LABEL="icon_label"
    QUOTE_BLOCK="quote_block"; SENTENCE_FRAME_BANNER="sentence_frame_banner"; EVIDENCE_BOX="evidence_box"
    COMPARISON_PANEL="comparison_panel"; TIMELINE_STEP="timeline_step"; MAP_PANEL="map_panel"
    IMAGE_CAPTION="image_caption"; DISCUSSION_CARD="discussion_card"; TIMER_BADGE="timer_badge"
    PAGE_REFERENCE_BADGE="page_reference_badge"; PROGRESS_INDICATOR="progress_indicator"
    EXIT_TICKET_CARD="exit_ticket_card"; TEACHER_NOTE_BLOCK="teacher_note_block"


class StoryboardComponent(BaseModel):
    component_type: ComponentType
    semantic_purpose: str
    text: list[str] = Field(default_factory=list)
    region: str
    min_words: int = 0
    max_words: int = 45
    responsive_behavior: str = "fit_then_split"
    icon_concept: Optional[str] = None


class VisualStoryboardSlide(BaseModel):
    slide_id: str
    sequence_number: int
    family: SlideFamily
    instructional_purpose: str
    student_experience: str
    visual_concept: str
    primary_focal_element: str
    supporting_visual_elements: list[str] = Field(default_factory=list)
    components: list[StoryboardComponent]
    theme: str
    source_slide_id: str


class VisualStoryboard(BaseModel):
    request_id: str
    lesson_title: str
    theme: str
    slides: list[VisualStoryboardSlide]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def continuous(self):
        if [s.sequence_number for s in self.slides] != list(range(1, len(self.slides)+1)):
            raise ValueError("storyboard sequence must be continuous")
        return self
