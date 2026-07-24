"""Presentation rendering adapters."""

from renderer.google_slides_renderer import GoogleSlidesRenderer
from renderer.gamma_prompt import (
    GammaAuthoritativeFacts,
    build_gamma_authoritative_facts,
    generate_gamma_deck_prompt,
    sanitize_gamma_renderer_text,
    write_gamma_deck_prompt,
)
from renderer.prompt_bundle import PromptBundle, RendererType
from renderer.prompt_generator import generate_prompt_bundle

__all__ = [
    "GoogleSlidesRenderer",
    "GammaAuthoritativeFacts",
    "build_gamma_authoritative_facts",
    "generate_gamma_deck_prompt",
    "sanitize_gamma_renderer_text",
    "write_gamma_deck_prompt",
    "PromptBundle",
    "RendererType",
    "generate_prompt_bundle",
]
