"""Deterministically convert PresentationDesignOutput into renderer prompts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from schemas.presentation_design_schema import PresentationDesignOutput, PresentationSlide
from renderer.prompt_bundle import (
    PromptBundle,
    PromptBundleMetadata,
    RendererType,
    SlidePrompt,
)
from renderer.theme_loader import LoadedTheme, load_prompt_theme


_RENDERER_DIRECTIONS = {
    RendererType.GENERIC: (
        "Create an editable presentation from the supplied specification."
    ),
    RendererType.GEMINI: (
        "Create an editable presentation in Google Slides from the supplied specification."
    ),
    RendererType.GAMMA: (
        "Create an editable Gamma presentation from the supplied specification."
    ),
}


def _canonical_json(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":") if indent is None else None,
        indent=indent,
    )


def _source_payload(presentation: PresentationDesignOutput) -> dict[str, Any]:
    return presentation.model_dump(mode="json")


def _slide_json(slide: PresentationSlide) -> str:
    return _canonical_json(slide.model_dump(mode="json"), indent=2)


def _shared_header(theme: LoadedTheme, renderer_type: RendererType) -> str:
    settings = theme.settings
    dimensions = settings.get("dimensions", {})
    typography = settings.get("typography", {})
    colors = settings.get("colors", {})
    content_limits = settings.get("content_limits", {})
    default_style = settings.get(
        "default_visual_style",
        "Mature, uncluttered, classroom-readable presentation design",
    )
    attribution = settings.get("attribution_footer", {})
    return "\n".join([
        "PRESENTATION RENDERER INSTRUCTIONS",
        _RENDERER_DIRECTIONS[renderer_type],
        "",
        "IMMUTABLE CONTENT RULES",
        "- Do not rewrite supplied content.",
        "- Do not paraphrase, summarize, omit, combine, reorder, or add lesson content.",
        "- Preserve the exact separation between student_view and teacher_notes.",
        "- Place teacher_notes in speaker notes; never project them as student-facing text.",
        "- Preserve slide IDs, sequence numbers, timing, interactions, directions, sources, and fidelity classifications.",
        "",
        "PRESENTATION STYLE",
        f"- Theme: {theme.name}",
        f"- Visual style: {default_style}",
        f"- Dimensions: {_canonical_json(dimensions)}",
        "",
        "TYPOGRAPHY",
        _canonical_json(typography),
        "",
        "COLOR PALETTE",
        _canonical_json(colors),
        "",
        "CLASSROOM DESIGN RULES",
        f"- Content limits: {_canonical_json(content_limits)}",
        "- Follow each slide's design and visuals objects exactly.",
        "- Keep all elements editable and preserve the requested semantic layout.",
        f"- Attribution footer: {_canonical_json(attribution)}",
        "",
        "ACCESSIBILITY RULES",
        "- Maintain high contrast and classroom-readable type sizes.",
        "- Preserve supplied alt_text exactly and apply it to the corresponding visual.",
        "- Do not encode essential meaning through color alone.",
        "- Do not place text inside generated images.",
    ])


def _slide_block(slide: PresentationSlide) -> str:
    return "\n".join([
        f"BEGIN SLIDE {slide.sequence_number} SOURCE JSON",
        _slide_json(slide),
        f"END SLIDE {slide.sequence_number} SOURCE JSON",
    ])


def generate_prompt_bundle(
    presentation: PresentationDesignOutput,
    theme: Mapping[str, Any] | str | Path | None = None,
    *,
    renderer_type: RendererType = RendererType.GENERIC,
) -> PromptBundle:
    """Generate synchronized deck and slide prompts without mutating lesson data."""
    if not isinstance(presentation, PresentationDesignOutput):
        raise TypeError("presentation must be a validated PresentationDesignOutput")
    renderer_type = RendererType(renderer_type)
    loaded_theme = load_prompt_theme(theme)
    header = _shared_header(loaded_theme, renderer_type)
    blocks = [_slide_block(slide) for slide in presentation.slides]
    deck_metadata = _canonical_json({
        "request_id": presentation.request_id,
        "lesson_title": presentation.lesson_title,
        "theme": presentation.theme,
        "warnings": presentation.warnings,
    }, indent=2)
    deck_prompt = "\n\n".join([
        header,
        "DECK SOURCE",
        "BEGIN DECK METADATA SOURCE JSON",
        deck_metadata,
        "END DECK METADATA SOURCE JSON",
        f"Slide count: {len(presentation.slides)}",
        "Render every slide below in the supplied order.",
        *blocks,
    ])
    slide_prompts = [
        SlidePrompt(
            slide_id=slide.slide_id,
            sequence_number=slide.sequence_number,
            prompt="\n\n".join([
                header,
                "SINGLE-SLIDE SOURCE",
                (
                    f"Render only slide {slide.sequence_number} of "
                    f"{len(presentation.slides)} for lesson {presentation.lesson_title}."
                ),
                block,
            ]),
        )
        for slide, block in zip(presentation.slides, blocks)
    ]
    source_json = _canonical_json(_source_payload(presentation))
    metadata = PromptBundleMetadata(
        request_id=presentation.request_id,
        lesson_title=presentation.lesson_title,
        presentation_theme=presentation.theme,
        renderer_type=renderer_type,
        theme_name=loaded_theme.name,
        slide_count=len(presentation.slides),
        slide_ids=[slide.slide_id for slide in presentation.slides],
        source_digest=hashlib.sha256(source_json.encode("utf-8")).hexdigest(),
    )
    warnings = list(dict.fromkeys([*presentation.warnings, *loaded_theme.warnings]))
    return PromptBundle(
        deck_prompt=deck_prompt,
        slide_prompts=slide_prompts,
        metadata=metadata,
        warnings=warnings,
    )


__all__ = ["generate_prompt_bundle"]
