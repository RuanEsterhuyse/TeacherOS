"""Gamma-specific handoff adapter for validated renderer prompt bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from renderer.prompt_bundle import RendererType
from renderer.prompt_generator import generate_prompt_bundle
from schemas.presentation_design_schema import PresentationDesignOutput


GAMMA_PROMPT_FILENAME = "GammaDeckPrompt.md"
_METADATA_START = "BEGIN DECK METADATA SOURCE JSON"
_METADATA_END = "END DECK METADATA SOURCE JSON"


def generate_gamma_deck_prompt(
    presentation: PresentationDesignOutput,
    theme: Mapping[str, Any] | str | Path | None = None,
    *,
    design_guide_path: str | Path | None = None,
) -> str:
    """Create a copy-ready Gamma deck prompt without changing lesson content."""
    bundle = generate_prompt_bundle(
        presentation,
        theme,
        renderer_type=RendererType.GAMMA,
        design_guide_path=design_guide_path,
    )
    before, separator, remainder = bundle.deck_prompt.partition(_METADATA_START)
    if not separator:
        raise ValueError("renderer deck prompt is missing its metadata boundary")
    _, separator, after = remainder.partition(_METADATA_END)
    if not separator:
        raise ValueError("renderer deck prompt has an incomplete metadata boundary")
    return f"# Gamma Deck Prompt\n\n{before.rstrip()}\n\n{after.lstrip()}"


def write_gamma_deck_prompt(
    presentation: PresentationDesignOutput,
    directory: str | Path,
    theme: Mapping[str, Any] | str | Path | None = None,
    *,
    design_guide_path: str | Path | None = None,
) -> Path:
    """Write the deterministic Gamma handoff artifact."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / GAMMA_PROMPT_FILENAME
    path.write_text(
        generate_gamma_deck_prompt(
            presentation,
            theme,
            design_guide_path=design_guide_path,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "GAMMA_PROMPT_FILENAME",
    "generate_gamma_deck_prompt",
    "write_gamma_deck_prompt",
]
