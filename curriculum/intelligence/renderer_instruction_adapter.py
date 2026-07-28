"""Compile approved presentation specifications into renderer-neutral instructions."""

from __future__ import annotations

from dataclasses import dataclass

from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.renderer_instruction_validator import (
    validate_renderer_instruction_package,
)
from schemas.presentation_spec_schema import (
    ApprovalStatus,
    ContentElement,
    ContentElementType,
    GroundingLabel,
    LayoutType,
    PresentationSpec,
    SlideSpec,
    SlideType,
    ValidationStatus,
    VisualType,
)
from schemas.renderer_instruction_schema import (
    AssetManifestEntry,
    AssetStatus,
    AssetType,
    BackgroundInstruction,
    CanvasDimensions,
    FontManifestEntry,
    FontWeight,
    InstructionLayout,
    LayoutContract,
    NotesPayload,
    OverflowBehavior,
    Rectangle,
    RENDERER_INSTRUCTION_ADAPTER_VERSION,
    RendererInstructionGenerationMetadata,
    RendererInstructionOptions,
    RendererInstructionPackage,
    RendererInstructionResult,
    RendererInstructionValidationReport,
    RendererInstructionWarning,
    RendererSlideInstruction,
    RendererVisualType,
    SlideAccessibility,
    TextAlignment,
    TextBlockInstruction,
    TextRole,
    ThemeTokens,
    VerticalAlignment,
    VisualBlockInstruction,
)


LAYOUT_BY_SLIDE_TYPE = {
    SlideType.title: InstructionLayout.title,
    SlideType.agenda: InstructionLayout.agenda,
    SlideType.essential_question: InstructionLayout.essential_question,
    SlideType.learning_objectives: InstructionLayout.objectives_cards,
    SlideType.background_knowledge: InstructionLayout.concept_web,
    SlideType.vocabulary: InstructionLayout.vocabulary_cards,
    SlideType.map_or_geography: InstructionLayout.map_focus,
    SlideType.identity_or_concept: InstructionLayout.concept_web,
    SlideType.author_or_text_preview: InstructionLayout.title_with_visual,
    SlideType.windows_and_mirrors: InstructionLayout.comparison,
    SlideType.reading_purpose: InstructionLayout.reading_chunk,
    SlideType.reading_chunk: InstructionLayout.reading_chunk,
    SlideType.reading_checkpoint: InstructionLayout.reading_checkpoint,
    SlideType.discussion: InstructionLayout.discussion_prompt,
    SlideType.theme_analysis: InstructionLayout.comparison,
    SlideType.text_evidence: InstructionLayout.evidence_analysis,
    SlideType.activity_book: InstructionLayout.two_column,
    SlideType.writing_task: InstructionLayout.two_column,
    SlideType.grammar: InstructionLayout.two_column,
    SlideType.morphology: InstructionLayout.three_card,
    SlideType.reflection: InstructionLayout.reflection,
    SlideType.exit_ticket: InstructionLayout.exit_ticket,
    SlideType.homework: InstructionLayout.homework,
    SlideType.teacher_only: InstructionLayout.teacher_only,
}

ROLE_BY_ELEMENT = {
    ContentElementType.heading: TextRole.body,
    ContentElementType.paragraph: TextRole.body,
    ContentElementType.bullet_list: TextRole.bullet_list,
    ContentElementType.numbered_list: TextRole.bullet_list,
    ContentElementType.question: TextRole.question,
    ContentElementType.quotation: TextRole.quotation,
    ContentElementType.vocabulary_term: TextRole.vocabulary,
    ContentElementType.sentence_frame: TextRole.sentence_frame,
    ContentElementType.callout: TextRole.callout,
    ContentElementType.comparison_cards: TextRole.body,
    ContentElementType.timeline_items: TextRole.bullet_list,
    ContentElementType.table: TextRole.body,
    ContentElementType.image_caption: TextRole.body,
    ContentElementType.exit_ticket_prompt: TextRole.question,
}

VISUAL_TYPE_MAP = {
    VisualType.illustration: RendererVisualType.illustration,
    VisualType.photo: RendererVisualType.photo,
    VisualType.map: RendererVisualType.map,
    VisualType.diagram: RendererVisualType.diagram,
    VisualType.icon: RendererVisualType.icon,
    VisualType.chart: RendererVisualType.chart,
    VisualType.book_cover_reference: RendererVisualType.book_cover_reference,
    VisualType.activity_page_reference:
        RendererVisualType.activity_page_reference,
}


@dataclass(frozen=True)
class _Geometry:
    title: Rectangle
    body: Rectangle
    visual: Rectangle


def _geometry(layout: InstructionLayout) -> _Geometry:
    title = Rectangle(x=0.7, y=0.45, width=11.93, height=0.8)
    body = Rectangle(x=0.85, y=1.55, width=11.63, height=4.95)
    visual = Rectangle(x=7.45, y=1.55, width=5.03, height=4.65)
    if layout == InstructionLayout.title:
        return _Geometry(
            Rectangle(x=1.1, y=2.15, width=11.13, height=1.5),
            Rectangle(x=1.45, y=3.85, width=10.43, height=1.1),
            visual,
        )
    if layout in {
        InstructionLayout.title_with_visual,
        InstructionLayout.two_column,
        InstructionLayout.map_focus,
        InstructionLayout.concept_web,
        InstructionLayout.evidence_analysis,
    }:
        body = Rectangle(x=0.85, y=1.55, width=5.95, height=4.95)
    if layout in {
        InstructionLayout.essential_question,
        InstructionLayout.discussion_prompt,
        InstructionLayout.reading_checkpoint,
        InstructionLayout.reflection,
        InstructionLayout.exit_ticket,
    }:
        body = Rectangle(x=1.15, y=1.75, width=11.03, height=4.4)
    if layout == InstructionLayout.teacher_only:
        body = Rectangle(x=0.85, y=1.55, width=11.63, height=4.95)
    return _Geometry(title, body, visual)


def layout_contracts() -> list[LayoutContract]:
    """Return the versioned, provider-neutral layout vocabulary."""
    contracts: list[LayoutContract] = []
    for layout in InstructionLayout:
        geometry = _geometry(layout)
        visual_layout = layout in {
            InstructionLayout.title_with_visual,
            InstructionLayout.two_column,
            InstructionLayout.map_focus,
            InstructionLayout.concept_web,
            InstructionLayout.evidence_analysis,
        }
        contracts.append(LayoutContract(
            layout=layout,
            required_blocks=(
                ["title", "notes"]
                if layout == InstructionLayout.teacher_only
                else ["title", "student_content", "notes"]
            ),
            optional_blocks=["footer"] + (["visual"] if visual_layout else []),
            default_coordinates={
                "title": geometry.title,
                "student_content": geometry.body,
                "visual": geometry.visual,
            },
            spacing_rules=[
                "Keep at least 0.25 inches between independent blocks.",
                "Keep all blocks inside the canvas safe area.",
            ],
            text_capacity_limits={
                "title_characters": 90,
                "body_characters": 700,
                "bullet_items": (
                    4 if layout == InstructionLayout.four_card
                    else 3 if layout == InstructionLayout.three_card
                    else 6
                ),
            },
            visual_placement_rules=(
                ["Place one meaningful visual in the reserved visual region."]
                if visual_layout
                else ["Do not require a visual; preserve whitespace."]
            ),
            accessibility_expectations=[
                "Maintain high contrast.",
                "Preserve reading order.",
                "Provide alt text for every meaningful visual.",
                "Do not encode meaning with color alone.",
            ],
        ))
    return contracts


def compile_theme(spec: PresentationSpec) -> ThemeTokens:
    """Compile the approved theme without changing its source values."""
    theme = spec.theme
    minimum = theme.accessibility_preferences.minimum_body_font_size
    return ThemeTokens(
        theme_id=theme.theme_id,
        background_colors=[theme.background_color],
        heading_color=theme.heading_color,
        body_color=theme.body_text_color,
        accent_colors=theme.accent_colors,
        heading_font_family=theme.heading_font,
        body_font_family=theme.body_font,
        title_font_family=theme.title_font,
        title_font_size=34,
        heading_font_size=28,
        body_font_size=max(20, minimum),
        caption_font_size=max(16, minimum - 4),
        card_fill=theme.background_color,
        card_border_color=theme.accent_colors[-1],
        border_radius=theme.border_radius,
        shadow_token=theme.shadow_style,
        spacing_scale=[float(value) for value in theme.spacing_scale],
        footer_style=theme.footer_style,
        image_treatment=theme.image_style,
        accessibility_defaults={
            "minimum_body_font_size": minimum,
            "high_contrast": theme.accessibility_preferences.high_contrast,
            "do_not_rely_on_color_alone":
                theme.accessibility_preferences.do_not_rely_on_color_alone,
            "require_alt_text":
                theme.accessibility_preferences.require_alt_text,
            "projection_readable":
                theme.accessibility_preferences.projection_readable,
        },
        source_theme=theme,
    )


def _element_text(element: ContentElement) -> str:
    if element.text:
        return element.text
    if element.items:
        marker = "1." if element.element_type == ContentElementType.numbered_list else "•"
        return "\n".join(f"{marker} {item}" for item in element.items)
    return "\n".join(" | ".join(row) for row in element.table_rows)


def _notes(slide: SlideSpec) -> NotesPayload:
    source = slide.speaker_notes
    sections: list[str] = []
    values = (
        ("Purpose", [source.purpose] if source.purpose else []),
        ("Teacher script", source.teacher_script),
        ("Teacher actions", source.teacher_actions),
        ("Anticipated responses", source.anticipated_responses),
        ("Misconception support", source.misconception_support),
        ("Checks for understanding", source.checks_for_understanding),
        (
            "Transition",
            [source.transition_language] if source.transition_language else [],
        ),
        ("Pacing", [source.pacing_notes] if source.pacing_notes else []),
    )
    for heading, items in values:
        if items:
            sections.append(f"{heading}:\n" + "\n".join(f"- {item}" for item in items))
    return NotesPayload(
        purpose=source.purpose,
        teacher_script=source.teacher_script,
        teacher_actions=source.teacher_actions,
        anticipated_responses=source.anticipated_responses,
        misconception_support=source.misconception_support,
        checks_for_understanding=source.checks_for_understanding,
        transition_language=source.transition_language,
        pacing_notes=source.pacing_notes,
        source_references=source.source_references,
        grounding_labels=source.grounding_labels,
        plain_text_fallback="\n\n".join(sections),
    )


def _text_blocks(
    package_id: str,
    slide: SlideSpec,
    layout: InstructionLayout,
    theme: ThemeTokens,
) -> list[TextBlockInstruction]:
    geometry = _geometry(layout)
    blocks = [TextBlockInstruction(
        block_id=stable_id("renderer-text", package_id, slide.slide_id, "title"),
        role=(
            TextRole.teacher_only_label
            if slide.slide_type == SlideType.teacher_only else TextRole.title
        ),
        text=slide.title,
        **geometry.title.model_dump(),
        font_family=theme.title_font_family,
        font_size=theme.title_font_size,
        font_weight=FontWeight.bold,
        alignment=(
            TextAlignment.center
            if layout == InstructionLayout.title else TextAlignment.left
        ),
        vertical_alignment=VerticalAlignment.middle,
        color=theme.heading_color,
        grounding_label=(
            slide.grounding_labels[0]
            if slide.grounding_labels else GroundingLabel.source_backed
        ),
    )]
    elements = sorted(slide.student_facing_content, key=lambda item: item.order)
    if not elements:
        return blocks
    gap = 0.12
    available = geometry.body.height - gap * (len(elements) - 1)
    height = available / len(elements)
    for index, element in enumerate(elements):
        role = ROLE_BY_ELEMENT[element.element_type]
        blocks.append(TextBlockInstruction(
            block_id=stable_id(
                "renderer-text", package_id, slide.slide_id, element.element_id
            ),
            role=role,
            text=_element_text(element),
            x=geometry.body.x,
            y=geometry.body.y + index * (height + gap),
            width=geometry.body.width,
            height=height,
            font_family=theme.body_font_family,
            font_size=(
                theme.heading_font_size
                if role == TextRole.question else theme.body_font_size
            ),
            font_weight=(
                FontWeight.semibold
                if role in {TextRole.question, TextRole.callout}
                else FontWeight.regular
            ),
            alignment=(
                TextAlignment.center
                if role == TextRole.question else TextAlignment.left
            ),
            vertical_alignment=VerticalAlignment.top,
            color=theme.body_color,
            emphasis=element.emphasis,
            list_style=(
                "numbered"
                if element.element_type == ContentElementType.numbered_list
                else "bulleted"
                if element.items else None
            ),
            overflow_behavior=OverflowBehavior.warn,
            source_reference=element.source_reference,
            grounding_label=element.grounding_label,
            source_element_id=element.element_id,
        ))
    return blocks


def _visual_and_asset(
    package_id: str,
    slide: SlideSpec,
    layout: InstructionLayout,
) -> tuple[list[VisualBlockInstruction], AssetManifestEntry]:
    geometry = _geometry(layout).visual
    visual = slide.visual_spec
    if visual is None or visual.visual_type == VisualType.text_only:
        asset = AssetManifestEntry(
            asset_id=stable_id("asset", package_id, slide.slide_id, "none"),
            slide_id=slide.slide_id,
            asset_type=AssetType.no_visual_required,
            description="No visual is required for this slide.",
            required_dimensions=geometry,
            status=AssetStatus.not_required,
        )
        return [], asset
    rendered_type = VISUAL_TYPE_MAP[visual.visual_type]
    asset_type = {
        VisualType.map: AssetType.map_needed,
        VisualType.icon: AssetType.icon_needed,
        VisualType.book_cover_reference: AssetType.book_cover_reference,
        VisualType.activity_page_reference: AssetType.activity_page_reference,
        VisualType.photo: AssetType.external_image_reference,
    }.get(visual.visual_type, AssetType.generated_illustration_needed)
    status = (
        AssetStatus.approved_source_required
        if visual.visual_type in {
            VisualType.book_cover_reference,
            VisualType.activity_page_reference,
        }
        else AssetStatus.neutral_placeholder_allowed
    )
    description = visual.description or f"Visual support for {slide.title}"
    block = VisualBlockInstruction(
        block_id=stable_id("renderer-visual", package_id, slide.slide_id),
        visual_type=rendered_type,
        description=description,
        image_prompt=visual.image_prompt,
        source_uri=visual.image_source,
        **geometry.model_dump(),
        crop_behavior=visual.crop_behavior.value,
        aspect_ratio=visual.aspect_ratio,
        alt_text=visual.alt_text,
        decorative=visual.decorative,
        required=visual.required,
        licensing_note=visual.licensing_note,
        source_reference=visual.source_reference,
        grounding_label=(
            slide.grounding_labels[0]
            if slide.grounding_labels else GroundingLabel.source_backed
        ),
    )
    asset = AssetManifestEntry(
        asset_id=stable_id("asset", package_id, slide.slide_id, asset_type.value),
        slide_id=slide.slide_id,
        asset_type=asset_type,
        description=description,
        prompt=visual.image_prompt,
        required_dimensions=geometry,
        aspect_ratio=visual.aspect_ratio,
        licensing_requirement=visual.licensing_note,
        source_reference=visual.source_reference,
        status=status,
    )
    return [block], asset


def _overflow_warnings(
    slide: RendererSlideInstruction,
    contract: LayoutContract,
    options: RendererInstructionOptions,
) -> list[RendererInstructionWarning]:
    if not options.conservative_capacity_checks:
        return []
    warnings: list[RendererInstructionWarning] = []
    title_limit = contract.text_capacity_limits["title_characters"]
    body_limit = contract.text_capacity_limits["body_characters"]
    bullet_limit = contract.text_capacity_limits["bullet_items"]
    for block in slide.text_blocks:
        code = None
        if block.role == TextRole.title and len(block.text) > title_limit:
            code = "title_capacity_risk"
        elif block.role != TextRole.title and len(block.text) > body_limit:
            code = "body_capacity_risk"
        elif (
            block.role == TextRole.bullet_list
            and len(block.text.splitlines()) > bullet_limit
        ):
            code = "list_capacity_risk"
        if code:
            warnings.append(RendererInstructionWarning(
                code=code,
                message=(
                    "Content exceeds the conservative layout capacity; "
                    "a future renderer must block or request review, not truncate."
                ),
                slide_id=slide.slide_id,
                block_id=block.block_id,
            ))
    if len(slide.notes_payload.plain_text_fallback) > (
        options.notes_fallback_character_limit
    ):
        warnings.append(RendererInstructionWarning(
            code="notes_fallback_capacity_risk",
            message="Plain-text speaker notes exceed the configured fallback capacity.",
            slide_id=slide.slide_id,
        ))
    return warnings


def build_renderer_instruction_package(
    presentation_spec: PresentationSpec,
    options: RendererInstructionOptions | None = None,
) -> RendererInstructionResult:
    """Compile one approved, valid PresentationSpec without rendering output."""
    options = options or RendererInstructionOptions()
    if presentation_spec.approval_status != ApprovalStatus.approved:
        raise ValueError("Renderer instructions require an approved PresentationSpec.")
    if presentation_spec.validation_status not in {
        ValidationStatus.passed,
        ValidationStatus.passed_with_warnings,
    }:
        raise ValueError("Renderer instructions require a valid PresentationSpec.")

    options_digest = content_digest(options.model_dump(mode="json"))
    presentation_digest = content_digest(
        presentation_spec.model_dump(mode="json")
    )
    package_id = stable_id(
        "renderer-instruction-package",
        presentation_spec.presentation_id,
        presentation_digest,
        options_digest,
        RENDERER_INSTRUCTION_ADAPTER_VERSION,
    )
    theme = compile_theme(presentation_spec)
    contracts = layout_contracts()
    by_layout = {contract.layout: contract for contract in contracts}
    slides: list[RendererSlideInstruction] = []
    assets: list[AssetManifestEntry] = []
    overflow: list[RendererInstructionWarning] = []
    for source_slide in presentation_spec.slides:
        layout = LAYOUT_BY_SLIDE_TYPE[source_slide.slide_type]
        text_blocks = _text_blocks(package_id, source_slide, layout, theme)
        visual_blocks, asset = _visual_and_asset(
            package_id, source_slide, layout
        )
        assets.append(asset)
        reading_order = [
            block.block_id for block in text_blocks
        ] + [block.block_id for block in visual_blocks]
        instruction = RendererSlideInstruction(
            slide_id=source_slide.slide_id,
            slide_number=source_slide.slide_number,
            slide_type=source_slide.slide_type.value,
            layout_type=layout,
            canvas_dimensions=options.canvas,
            background=BackgroundInstruction(
                color=theme.background_colors[0],
                accent_color=(
                    theme.accent_colors[
                        (source_slide.slide_number - 1)
                        % len(theme.accent_colors)
                    ]
                ),
            ),
            text_blocks=text_blocks,
            visual_blocks=visual_blocks,
            notes_payload=_notes(source_slide),
            footer_payload={
                "text": None,
                "show_slide_number": (
                    options.include_footer and options.include_slide_numbers
                ),
                "style": theme.footer_style,
            },
            timing=source_slide.estimated_minutes,
            source_references=source_slide.source_references,
            grounding_labels=source_slide.grounding_labels,
            accessibility=SlideAccessibility(
                reading_order=reading_order,
                minimum_body_font_size=(
                    presentation_spec.theme.accessibility_preferences
                    .minimum_body_font_size
                ),
                high_contrast=(
                    presentation_spec.theme.accessibility_preferences
                    .high_contrast
                ),
                do_not_rely_on_color_alone=(
                    presentation_spec.theme.accessibility_preferences
                    .do_not_rely_on_color_alone
                ),
                projection_readable=(
                    presentation_spec.theme.accessibility_preferences
                    .projection_readable
                ),
            ),
            required=source_slide.required,
            sequence_group=source_slide.sequence_group,
            source_content_element_ids=[
                element.element_id
                for element in source_slide.student_facing_content
            ],
        )
        slides.append(instruction)
        overflow.extend(_overflow_warnings(
            instruction, by_layout[layout], options
        ))

    placeholder = RendererInstructionValidationReport(
        status=ValidationStatus.pending,
        valid=False,
        expected_slide_count=len(presentation_spec.slides),
        represented_slide_count=len(slides),
        source_content_block_count=sum(
            len(slide.student_facing_content)
            for slide in presentation_spec.slides
        ),
        represented_content_block_count=sum(
            len(slide.source_content_element_ids) for slide in slides
        ),
    )
    package = RendererInstructionPackage(
        package_id=package_id,
        presentation_id=presentation_spec.presentation_id,
        playbook_id=presentation_spec.playbook_id,
        source_id=presentation_spec.source_id,
        theme=theme,
        canvas=options.canvas,
        slides=slides,
        asset_manifest=assets,
        font_manifest=[
            FontManifestEntry(
                family=theme.title_font_family,
                roles=["title", "subtitle"],
                fallback_families=["Arial", "sans-serif"],
            ),
            FontManifestEntry(
                family=theme.body_font_family,
                roles=["body", "question", "list", "footer"],
                fallback_families=["Arial", "sans-serif"],
            ),
        ],
        layout_contracts=contracts,
        validation_report=placeholder,
        generation_metadata=RendererInstructionGenerationMetadata(
            generated_at=presentation_spec.generation_metadata.generated_at,
            presentation_digest=presentation_digest,
            options_digest=options_digest,
        ),
    )
    report = validate_renderer_instruction_package(
        package, presentation_spec
    )
    package = package.model_copy(update={"validation_report": report})
    unsupported: list[RendererInstructionWarning] = []
    if any(slide.continuation_of for slide in presentation_spec.slides):
        unsupported.append(RendererInstructionWarning(
            code="continuation_semantics_deferred",
            message=(
                "Continuation metadata is preserved by slide order, but "
                "renderer-specific continuation styling is not defined."
            ),
        ))
    warnings = list(overflow) + unsupported
    return RendererInstructionResult(
        instruction_package=package,
        warnings=warnings,
        unsupported_features=unsupported,
        overflow_risks=overflow,
        asset_requirements=assets,
        validation_report=report,
    )


__all__ = [
    "LAYOUT_BY_SLIDE_TYPE", "build_renderer_instruction_package",
    "compile_theme", "layout_contracts",
]
