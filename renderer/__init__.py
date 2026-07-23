"""Presentation rendering adapters."""

from renderer.google_slides_renderer import GoogleSlidesRenderer
from renderer.prompt_bundle import PromptBundle, RendererType
from renderer.prompt_generator import generate_prompt_bundle

__all__ = [
    "GoogleSlidesRenderer",
    "PromptBundle",
    "RendererType",
    "generate_prompt_bundle",
]
