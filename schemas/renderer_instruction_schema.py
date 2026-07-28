"""Provider-neutral contracts for deterministic presentation rendering."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import Field, model_validator

from schemas.pasted_lesson_schema import SourceReference, StrictModel
from schemas.presentation_spec_schema import (
    ApprovalStatus,
    GroundingLabel,
    PresentationValidationIssue,
    ThemeSpec,
    ValidationStatus,
)


RENDERER_CONTRACT_VERSION = "renderer-contract-v1"
RENDERER_INSTRUCTION_SCHEMA_VERSION = "1.0"
RENDERER_INSTRUCTION_ADAPTER_VERSION = "renderer-instruction-adapter-v1"


class CoordinateUnit(str, Enum):
    inches = "inches"


class RendererPackageApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"


class TextRole(str, Enum):
    title = "title"
    subtitle = "subtitle"
    body = "body"
    bullet_list = "bullet_list"
    question = "question"
    quotation = "quotation"
    callout = "callout"
    vocabulary = "vocabulary"
    sentence_frame = "sentence_frame"
    footer = "footer"
    page_reference = "page_reference"
    teacher_only_label = "teacher_only_label"


class TextAlignment(str, Enum):
    left = "left"
    center = "center"
    right = "right"


class VerticalAlignment(str, Enum):
    top = "top"
    middle = "middle"
    bottom = "bottom"


class FontWeight(str, Enum):
    regular = "regular"
    medium = "medium"
    semibold = "semibold"
    bold = "bold"


class OverflowBehavior(str, Enum):
    warn = "warn"
    shrink_to_minimum = "shrink_to_minimum"
    clip_prohibited = "clip_prohibited"


class RendererVisualType(str, Enum):
    illustration = "illustration"
    photo = "photo"
    map = "map"
    diagram = "diagram"
    icon = "icon"
    chart = "chart"
    book_cover_reference = "book_cover_reference"
    activity_page_reference = "activity_page_reference"
    external_image_reference = "external_image_reference"
    placeholder = "placeholder"


class AssetType(str, Enum):
    generated_illustration_needed = "generated_illustration_needed"
    map_needed = "map_needed"
    icon_needed = "icon_needed"
    book_cover_reference = "book_cover_reference"
    activity_page_reference = "activity_page_reference"
    external_image_reference = "external_image_reference"
    no_visual_required = "no_visual_required"


class AssetStatus(str, Enum):
    unresolved = "unresolved"
    approved_source_required = "approved_source_required"
    neutral_placeholder_allowed = "neutral_placeholder_allowed"
    not_required = "not_required"


class InstructionLayout(str, Enum):
    title = "title"
    title_with_visual = "title_with_visual"
    essential_question = "essential_question"
    objectives_cards = "objectives_cards"
    agenda = "agenda"
    vocabulary_cards = "vocabulary_cards"
    two_column = "two_column"
    three_card = "three_card"
    four_card = "four_card"
    map_focus = "map_focus"
    concept_web = "concept_web"
    reading_chunk = "reading_chunk"
    reading_checkpoint = "reading_checkpoint"
    discussion_prompt = "discussion_prompt"
    comparison = "comparison"
    evidence_analysis = "evidence_analysis"
    reflection = "reflection"
    exit_ticket = "exit_ticket"
    homework = "homework"
    teacher_only = "teacher_only"


class CanvasDimensions(StrictModel):
    width: float = Field(default=13.333, gt=0)
    height: float = Field(default=7.5, gt=0)
    units: CoordinateUnit = CoordinateUnit.inches
    aspect_ratio: str = "16:9"


class Rectangle(StrictModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class BackgroundInstruction(StrictModel):
    color: str = Field(min_length=1)
    accent_color: Optional[str] = None
    treatment: str = "solid"


class TextBlockInstruction(Rectangle):
    block_id: str = Field(min_length=1)
    role: TextRole
    text: str = Field(min_length=1)
    font_family: str = Field(min_length=1)
    font_size: float = Field(gt=0)
    font_weight: FontWeight = FontWeight.regular
    alignment: TextAlignment = TextAlignment.left
    vertical_alignment: VerticalAlignment = VerticalAlignment.top
    line_spacing: float = Field(default=1.15, gt=0)
    color: str = Field(min_length=1)
    emphasis: Optional[str] = None
    list_style: Optional[str] = None
    overflow_behavior: OverflowBehavior = OverflowBehavior.warn
    source_reference: Optional[SourceReference] = None
    grounding_label: GroundingLabel = GroundingLabel.source_backed
    alt_description: Optional[str] = None
    source_element_id: Optional[str] = None


class VisualBlockInstruction(Rectangle):
    block_id: str = Field(min_length=1)
    visual_type: RendererVisualType
    description: str = Field(min_length=1)
    image_prompt: Optional[str] = None
    source_uri: Optional[str] = None
    crop_behavior: str = "contain"
    aspect_ratio: Optional[str] = None
    alt_text: Optional[str] = None
    decorative: bool = False
    required: bool = False
    licensing_note: Optional[str] = None
    source_reference: Optional[SourceReference] = None
    grounding_label: GroundingLabel = GroundingLabel.source_backed

    @model_validator(mode="after")
    def require_alt_text(self) -> "VisualBlockInstruction":
        if not self.decorative and not self.alt_text:
            raise ValueError("Meaningful visuals require alt text.")
        return self


class NotesPayload(StrictModel):
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
    plain_text_fallback: str = ""


class FooterPayload(StrictModel):
    text: Optional[str] = None
    show_slide_number: bool = True
    style: str = "minimal"


class SlideAccessibility(StrictModel):
    reading_order: list[str] = Field(default_factory=list)
    minimum_body_font_size: int = Field(default=20, ge=14)
    high_contrast: bool = True
    do_not_rely_on_color_alone: bool = True
    projection_readable: bool = True


class RendererSlideInstruction(StrictModel):
    slide_id: str = Field(min_length=1)
    slide_number: int = Field(ge=1)
    slide_type: str = Field(min_length=1)
    layout_type: InstructionLayout
    canvas_dimensions: CanvasDimensions
    background: BackgroundInstruction
    text_blocks: list[TextBlockInstruction] = Field(default_factory=list)
    visual_blocks: list[VisualBlockInstruction] = Field(default_factory=list)
    notes_payload: NotesPayload
    footer_payload: FooterPayload
    timing: Optional[int] = Field(default=None, ge=0)
    source_references: list[SourceReference] = Field(default_factory=list)
    grounding_labels: list[GroundingLabel] = Field(default_factory=list)
    accessibility: SlideAccessibility
    required: bool = True
    sequence_group: Optional[str] = None
    source_content_element_ids: list[str] = Field(default_factory=list)


class ThemeTokens(StrictModel):
    theme_id: str = Field(min_length=1)
    background_colors: list[str] = Field(min_length=1)
    heading_color: str = Field(min_length=1)
    body_color: str = Field(min_length=1)
    accent_colors: list[str] = Field(min_length=1)
    heading_font_family: str = Field(min_length=1)
    body_font_family: str = Field(min_length=1)
    title_font_family: str = Field(min_length=1)
    title_font_size: float = Field(gt=0)
    heading_font_size: float = Field(gt=0)
    body_font_size: float = Field(gt=0)
    caption_font_size: float = Field(gt=0)
    card_fill: str = Field(min_length=1)
    card_border_color: str = Field(min_length=1)
    border_radius: float = Field(ge=0)
    shadow_token: str = Field(min_length=1)
    spacing_scale: list[float] = Field(min_length=1)
    footer_style: str = Field(min_length=1)
    image_treatment: str = Field(min_length=1)
    accessibility_defaults: dict[str, Union[bool, int]]
    source_theme: ThemeSpec


class FontManifestEntry(StrictModel):
    family: str = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    fallback_families: list[str] = Field(default_factory=list)
    required: bool = True


class AssetManifestEntry(StrictModel):
    asset_id: str = Field(min_length=1)
    slide_id: str = Field(min_length=1)
    asset_type: AssetType
    description: str = Field(min_length=1)
    prompt: Optional[str] = None
    required_dimensions: Rectangle
    aspect_ratio: Optional[str] = None
    licensing_requirement: Optional[str] = None
    source_reference: Optional[SourceReference] = None
    status: AssetStatus


class LayoutContract(StrictModel):
    layout: InstructionLayout
    required_blocks: list[str] = Field(default_factory=list)
    optional_blocks: list[str] = Field(default_factory=list)
    default_coordinates: dict[str, Rectangle] = Field(default_factory=dict)
    spacing_rules: list[str] = Field(default_factory=list)
    text_capacity_limits: dict[str, int] = Field(default_factory=dict)
    visual_placement_rules: list[str] = Field(default_factory=list)
    accessibility_expectations: list[str] = Field(default_factory=list)


class RendererInstructionGenerationMetadata(StrictModel):
    adapter_name: str = "deterministic_renderer_instruction_adapter"
    adapter_version: str = RENDERER_INSTRUCTION_ADAPTER_VERSION
    generated_at: datetime
    deterministic: bool = True
    presentation_digest: str = Field(min_length=1)
    options_digest: str = Field(min_length=1)


class RendererInstructionValidationReport(StrictModel):
    status: ValidationStatus
    valid: bool
    issues: list[PresentationValidationIssue] = Field(default_factory=list)
    expected_slide_count: int = Field(ge=0)
    represented_slide_count: int = Field(ge=0)
    source_content_block_count: int = Field(ge=0)
    represented_content_block_count: int = Field(ge=0)


class RendererInstructionPackage(StrictModel):
    package_id: str = Field(min_length=1)
    presentation_id: str = Field(min_length=1)
    playbook_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    renderer_contract_version: str = RENDERER_CONTRACT_VERSION
    theme: ThemeTokens
    canvas: CanvasDimensions
    slides: list[RendererSlideInstruction]
    asset_manifest: list[AssetManifestEntry] = Field(default_factory=list)
    font_manifest: list[FontManifestEntry] = Field(default_factory=list)
    layout_contracts: list[LayoutContract] = Field(default_factory=list)
    validation_report: RendererInstructionValidationReport
    generation_metadata: RendererInstructionGenerationMetadata
    approval_status: RendererPackageApprovalStatus = (
        RendererPackageApprovalStatus.pending
    )
    approved_at: Optional[datetime] = None
    schema_version: str = RENDERER_INSTRUCTION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity_and_order(self) -> "RendererInstructionPackage":
        numbers = [slide.slide_number for slide in self.slides]
        if numbers != list(range(1, len(self.slides) + 1)):
            raise ValueError("Renderer slide numbers must be sequential.")
        if len({slide.slide_id for slide in self.slides}) != len(self.slides):
            raise ValueError("Renderer slide IDs must be unique.")
        if self.approval_status == RendererPackageApprovalStatus.approved:
            if self.approved_at is None or not self.validation_report.valid:
                raise ValueError(
                    "Approved renderer packages require approval time and valid report."
                )
        return self


class RendererInstructionOptions(StrictModel):
    canvas: CanvasDimensions = Field(default_factory=CanvasDimensions)
    include_footer: bool = True
    include_slide_numbers: bool = True
    notes_fallback_character_limit: int = Field(default=6000, ge=500)
    conservative_capacity_checks: bool = True


class RendererInstructionWarning(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    slide_id: Optional[str] = None
    block_id: Optional[str] = None


class RendererInstructionResult(StrictModel):
    instruction_package: RendererInstructionPackage
    warnings: list[RendererInstructionWarning] = Field(default_factory=list)
    unsupported_features: list[RendererInstructionWarning] = Field(
        default_factory=list
    )
    overflow_risks: list[RendererInstructionWarning] = Field(
        default_factory=list
    )
    asset_requirements: list[AssetManifestEntry] = Field(default_factory=list)
    validation_report: RendererInstructionValidationReport
    adapter_version: str = RENDERER_INSTRUCTION_ADAPTER_VERSION


__all__ = [
    "AssetManifestEntry", "AssetStatus", "AssetType",
    "BackgroundInstruction", "CanvasDimensions", "CoordinateUnit",
    "FontManifestEntry", "FontWeight", "InstructionLayout",
    "LayoutContract", "NotesPayload", "OverflowBehavior", "Rectangle",
    "RENDERER_CONTRACT_VERSION", "RENDERER_INSTRUCTION_ADAPTER_VERSION",
    "RENDERER_INSTRUCTION_SCHEMA_VERSION", "RendererInstructionGenerationMetadata",
    "RendererInstructionOptions", "RendererInstructionPackage",
    "RendererInstructionResult", "RendererInstructionValidationReport",
    "RendererInstructionWarning", "RendererPackageApprovalStatus",
    "RendererSlideInstruction", "RendererVisualType", "SlideAccessibility",
    "TextAlignment", "TextBlockInstruction", "TextRole", "ThemeTokens",
    "VerticalAlignment", "VisualBlockInstruction",
]
