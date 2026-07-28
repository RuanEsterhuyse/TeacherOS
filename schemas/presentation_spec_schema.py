"""Provider-neutral contracts for deterministic lesson presentation planning."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from schemas.pasted_lesson_schema import SourceReference, StrictModel


PRESENTATION_SPEC_SCHEMA_VERSION = "1.0"
PRESENTATION_SPEC_GENERATOR_VERSION = "presentation-spec-v1"


class SlideType(str, Enum):
    title = "title"
    agenda = "agenda"
    essential_question = "essential_question"
    learning_objectives = "learning_objectives"
    background_knowledge = "background_knowledge"
    vocabulary = "vocabulary"
    map_or_geography = "map_or_geography"
    identity_or_concept = "identity_or_concept"
    author_or_text_preview = "author_or_text_preview"
    windows_and_mirrors = "windows_and_mirrors"
    reading_purpose = "reading_purpose"
    reading_chunk = "reading_chunk"
    reading_checkpoint = "reading_checkpoint"
    discussion = "discussion"
    theme_analysis = "theme_analysis"
    text_evidence = "text_evidence"
    activity_book = "activity_book"
    writing_task = "writing_task"
    grammar = "grammar"
    morphology = "morphology"
    reflection = "reflection"
    exit_ticket = "exit_ticket"
    homework = "homework"
    teacher_only = "teacher_only"


class LayoutType(str, Enum):
    title = "title"
    day_opener = "day_opener"
    single_focus = "single_focus"
    question_focus = "question_focus"
    cards = "cards"
    split = "split"
    steps = "steps"
    comparison = "comparison"
    visual_focus = "visual_focus"
    text_evidence = "text_evidence"
    teacher_only = "teacher_only"


class ContentElementType(str, Enum):
    heading = "heading"
    paragraph = "paragraph"
    bullet_list = "bullet_list"
    numbered_list = "numbered_list"
    question = "question"
    quotation = "quotation"
    vocabulary_term = "vocabulary_term"
    sentence_frame = "sentence_frame"
    callout = "callout"
    comparison_cards = "comparison_cards"
    timeline_items = "timeline_items"
    table = "table"
    image_caption = "image_caption"
    exit_ticket_prompt = "exit_ticket_prompt"


class GroundingLabel(str, Enum):
    source_backed = "source_backed"
    generated_guidance_review = "generated_guidance_review"
    unavailable = "unavailable"


class VisualType(str, Enum):
    illustration = "illustration"
    photo = "photo"
    map = "map"
    diagram = "diagram"
    icon = "icon"
    chart = "chart"
    text_only = "text_only"
    book_cover_reference = "book_cover_reference"
    activity_page_reference = "activity_page_reference"


class ImagePlacement(str, Enum):
    none = "none"
    left = "left"
    right = "right"
    top = "top"
    bottom = "bottom"
    background = "background"
    full_bleed = "full_bleed"
    inset = "inset"


class CropBehavior(str, Enum):
    contain = "contain"
    cover = "cover"
    no_crop = "no_crop"


class ValidationStatus(str, Enum):
    pending = "pending"
    passed = "passed"
    passed_with_warnings = "passed_with_warnings"
    failed = "failed"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RequiredSectionKey(str, Enum):
    title = "title"
    day_start = "day_start"
    activity = "activity"
    essential_question = "essential_question"
    objectives = "objectives"
    vocabulary = "vocabulary"
    assessment = "assessment"
    exit_ticket = "exit_ticket"
    homework = "homework"


class PresentationDetailLevel(str, Enum):
    focused = "focused"
    comprehensive = "comprehensive"


class ValidationSeverity(str, Enum):
    error = "error"
    warning = "warning"


class ContentElement(StrictModel):
    element_id: str = Field(min_length=1)
    element_type: ContentElementType
    text: Optional[str] = None
    label: Optional[str] = None
    emphasis: Optional[str] = None
    order: int = Field(ge=1)
    items: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    source_reference: Optional[SourceReference] = None
    grounding_label: GroundingLabel = GroundingLabel.source_backed

    @model_validator(mode="after")
    def require_content(self) -> "ContentElement":
        if not (self.text or self.items or self.table_rows):
            raise ValueError("Content elements cannot be empty.")
        return self


class SpeakerNotes(StrictModel):
    purpose: Optional[str] = None
    teacher_script: list[str] = Field(default_factory=list)
    teacher_actions: list[str] = Field(default_factory=list)
    anticipated_responses: list[str] = Field(default_factory=list)
    misconception_support: list[str] = Field(default_factory=list)
    checks_for_understanding: list[str] = Field(default_factory=list)
    transition_language: Optional[str] = None
    pacing_notes: Optional[str] = None
    source_references: list[SourceReference] = Field(default_factory=list)
    grounding_labels: list[GroundingLabel] = Field(default_factory=list)

    def has_content(self) -> bool:
        return any((
            self.purpose,
            self.teacher_script,
            self.teacher_actions,
            self.anticipated_responses,
            self.misconception_support,
            self.checks_for_understanding,
            self.transition_language,
            self.pacing_notes,
            self.source_references,
        ))


class VisualSpec(StrictModel):
    visual_type: VisualType = VisualType.text_only
    description: Optional[str] = None
    image_prompt: Optional[str] = None
    image_source: Optional[str] = None
    aspect_ratio: Optional[str] = None
    placement: ImagePlacement = ImagePlacement.none
    crop_behavior: CropBehavior = CropBehavior.contain
    alt_text: Optional[str] = None
    decorative: bool = False
    required: bool = False
    source_reference: Optional[SourceReference] = None
    licensing_note: Optional[str] = None

    @model_validator(mode="after")
    def validate_accessibility(self) -> "VisualSpec":
        if self.required and self.visual_type != VisualType.text_only:
            if not self.alt_text:
                raise ValueError("Required visuals need alt text.")
        return self


class AccessibilityPreferences(StrictModel):
    minimum_body_font_size: int = Field(default=20, ge=14)
    high_contrast: bool = True
    do_not_rely_on_color_alone: bool = True
    require_alt_text: bool = True
    projection_readable: bool = True


class ThemeSpec(StrictModel):
    theme_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    background_color: str
    heading_color: str
    body_text_color: str
    accent_colors: list[str] = Field(min_length=1)
    heading_font: str = Field(min_length=1)
    body_font: str = Field(min_length=1)
    title_font: str = Field(min_length=1)
    border_radius: int = Field(ge=0)
    shadow_style: str
    spacing_scale: list[int] = Field(min_length=1)
    footer_style: str
    image_style: str
    accessibility_preferences: AccessibilityPreferences = Field(
        default_factory=AccessibilityPreferences
    )


class SlideGenerationMetadata(StrictModel):
    generator_version: str = PRESENTATION_SPEC_GENERATOR_VERSION
    deterministic: bool = True
    source_activity_id: Optional[str] = None


class SlideSpec(StrictModel):
    slide_id: str = Field(min_length=1)
    slide_number: int = Field(ge=1)
    instructional_day: Optional[int] = Field(default=None, ge=1)
    activity_id: Optional[str] = None
    slide_type: SlideType
    layout_type: LayoutType
    title: str = Field(min_length=1)
    subtitle: Optional[str] = None
    student_facing_content: list[ContentElement] = Field(default_factory=list)
    speaker_notes: SpeakerNotes = Field(default_factory=SpeakerNotes)
    teacher_actions: list[str] = Field(default_factory=list)
    student_actions: list[str] = Field(default_factory=list)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    visual_spec: Optional[VisualSpec] = None
    source_references: list[SourceReference] = Field(default_factory=list)
    grounding_labels: list[GroundingLabel] = Field(default_factory=list)
    eld_supports: list[str] = Field(default_factory=list)
    required: bool = True
    sequence_group: Optional[str] = None
    continuation_of: Optional[str] = None
    notes_required: bool = True
    generation_metadata: SlideGenerationMetadata = Field(
        default_factory=SlideGenerationMetadata
    )


class RequiredSection(StrictModel):
    section_key: RequiredSectionKey
    required: bool = True
    activity_id: Optional[str] = None
    instructional_day: Optional[int] = Field(default=None, ge=1)
    represented_by_slide_ids: list[str] = Field(default_factory=list)


class PresentationGenerationMetadata(StrictModel):
    generator_name: str = "deterministic_presentation_spec_builder"
    generator_version: str = PRESENTATION_SPEC_GENERATOR_VERSION
    generated_at: datetime
    deterministic: bool = True
    approved_enrichment_id: str = Field(min_length=1)
    options_digest: str = Field(min_length=1)


class PresentationSpec(StrictModel):
    presentation_id: str = Field(min_length=1)
    playbook_id: str = Field(min_length=1)
    approved_enrichment_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    presentation_title: str = Field(min_length=1)
    instructional_days: list[int] = Field(default_factory=list)
    estimated_total_minutes: int = Field(ge=0)
    theme: ThemeSpec
    slides: list[SlideSpec]
    required_sections: list[RequiredSection] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    generation_metadata: PresentationGenerationMetadata
    validation_status: ValidationStatus = ValidationStatus.pending
    approval_status: ApprovalStatus = ApprovalStatus.pending
    approved_at: Optional[datetime] = None
    schema_version: str = PRESENTATION_SPEC_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity_and_order(self) -> "PresentationSpec":
        ids = [slide.slide_id for slide in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("Slide IDs must be unique.")
        expected = list(range(1, len(self.slides) + 1))
        if [slide.slide_number for slide in self.slides] != expected:
            raise ValueError("Slide numbers must be sequential and ordered.")
        if self.approval_status == ApprovalStatus.approved:
            if self.approved_at is None:
                raise ValueError("Approved specifications require approved_at.")
            if self.validation_status not in {
                ValidationStatus.passed,
                ValidationStatus.passed_with_warnings,
            }:
                raise ValueError("Only passing specifications may be approved.")
        return self


class PresentationBuildOptions(StrictModel):
    target_slide_count: Optional[int] = Field(default=None, ge=1)
    maximum_slide_count: Optional[int] = Field(default=None, ge=1)
    detail_level: PresentationDetailLevel = (
        PresentationDetailLevel.comprehensive
    )
    include_agenda: bool = True
    include_objectives: bool = True
    include_vocabulary: bool = True
    include_eld_supports: bool = True
    include_teacher_only_slides: bool = False
    include_homework: bool = True
    include_exit_ticket: bool = True
    include_visual_prompts: bool = True
    preferred_theme_id: str = "teacheros_classroom"
    split_long_activities: bool = True
    strict_required_section_coverage: bool = True

    @model_validator(mode="after")
    def validate_counts(self) -> "PresentationBuildOptions":
        if (
            self.target_slide_count is not None
            and self.maximum_slide_count is not None
            and self.target_slide_count > self.maximum_slide_count
        ):
            raise ValueError("Target slide count cannot exceed maximum.")
        return self


class PresentationWarning(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    slide_id: Optional[str] = None
    activity_id: Optional[str] = None


class SectionCoverage(StrictModel):
    section_key: str = Field(min_length=1)
    required: bool
    covered: bool
    slide_ids: list[str] = Field(default_factory=list)


class ActivityCoverage(StrictModel):
    activity_id: str = Field(min_length=1)
    covered: bool
    slide_ids: list[str] = Field(default_factory=list)
    retained_source_references: list[SourceReference] = Field(
        default_factory=list
    )


class SourceCoverage(StrictModel):
    expected_reference_count: int = Field(ge=0)
    retained_reference_count: int = Field(ge=0)
    unsupported_references: list[SourceReference] = Field(default_factory=list)
    complete: bool


class PresentationValidationIssue(StrictModel):
    code: str = Field(min_length=1)
    severity: ValidationSeverity
    message: str = Field(min_length=1)
    slide_id: Optional[str] = None
    activity_id: Optional[str] = None


class PresentationValidationReport(StrictModel):
    status: ValidationStatus
    issues: list[PresentationValidationIssue] = Field(default_factory=list)
    section_coverage: list[SectionCoverage] = Field(default_factory=list)
    activity_coverage: list[ActivityCoverage] = Field(default_factory=list)
    source_coverage: SourceCoverage
    expected_activity_minutes: int = Field(ge=0)
    represented_activity_minutes: int = Field(ge=0)
    valid: bool


class PresentationBuildResult(StrictModel):
    presentation_spec: PresentationSpec
    warnings: list[PresentationWarning] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    source_coverage: SourceCoverage
    activity_coverage: list[ActivityCoverage] = Field(default_factory=list)
    validation_report: PresentationValidationReport
    generator_version: str = PRESENTATION_SPEC_GENERATOR_VERSION


__all__ = [
    "AccessibilityPreferences", "ActivityCoverage", "ApprovalStatus",
    "ContentElement", "ContentElementType", "CropBehavior", "GroundingLabel",
    "ImagePlacement", "LayoutType", "PRESENTATION_SPEC_GENERATOR_VERSION",
    "PRESENTATION_SPEC_SCHEMA_VERSION", "PresentationBuildOptions",
    "PresentationBuildResult", "PresentationDetailLevel",
    "PresentationGenerationMetadata", "PresentationSpec",
    "PresentationValidationIssue", "PresentationValidationReport",
    "PresentationWarning", "RequiredSection", "RequiredSectionKey",
    "SectionCoverage", "SlideGenerationMetadata", "SlideSpec", "SlideType",
    "SourceCoverage", "SpeakerNotes", "ThemeSpec", "ValidationSeverity",
    "ValidationStatus", "VisualSpec", "VisualType",
]
