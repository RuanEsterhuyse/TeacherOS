"""Presentation rendering adapters."""

from renderer.google_slides_renderer import GoogleSlidesRenderer
from renderer.gamma_prompt import generate_gamma_deck_prompt, write_gamma_deck_prompt
from renderer.prompt_bundle import PromptBundle, RendererType
from renderer.prompt_generator import generate_prompt_bundle

__all__ = [
    "GoogleSlidesRenderer",
    "generate_gamma_deck_prompt",
    "write_gamma_deck_prompt",
    "PromptBundle",
    "RendererType",
    "generate_prompt_bundle",
]
