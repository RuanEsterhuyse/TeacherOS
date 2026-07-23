"""Renderer-neutral prompt bundle models and artifact serialization."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class RendererType(str, Enum):
    """Supported prompt phrasings; lesson data is identical for every renderer."""

    GENERIC = "generic"
    GEMINI = "gemini"
    GAMMA = "gamma"


class SlidePrompt(BaseModel):
    """One renderer-ready prompt tied to one source slide."""

    slide_id: str
    sequence_number: int = Field(ge=1)
    prompt: str


class PromptBundleMetadata(BaseModel):
    """Deterministic provenance for a generated prompt bundle."""

    schema_version: str = "1.0"
    request_id: str
    lesson_title: str = ""
    presentation_theme: str
    renderer_type: RendererType
    theme_name: str
    slide_count: int = Field(ge=0)
    slide_ids: list[str] = Field(default_factory=list)
    source_digest: str


class PromptBundle(BaseModel):
    """Complete-deck and per-slide prompts generated from one presentation."""

    deck_prompt: str
    slide_prompts: list[SlidePrompt]
    metadata: PromptBundleMetadata
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_slide_metadata(self):
        expected_numbers = list(range(1, len(self.slide_prompts) + 1))
        if [item.sequence_number for item in self.slide_prompts] != expected_numbers:
            raise ValueError("slide prompts must be continuous and ordered")
        if [item.slide_id for item in self.slide_prompts] != self.metadata.slide_ids:
            raise ValueError("slide prompt IDs must match metadata")
        if len(self.slide_prompts) != self.metadata.slide_count:
            raise ValueError("slide prompt count must match metadata")
        return self

    def to_markdown(self) -> str:
        """Return a copy-friendly Markdown representation without changing prompts."""
        lines = [
            "# Presentation Renderer Prompt Bundle",
            "",
            "## Metadata",
            "",
            f"- Request ID: `{self.metadata.request_id}`",
            f"- Lesson title: {self.metadata.lesson_title}",
            f"- Presentation design theme: {self.metadata.presentation_theme}",
            f"- Renderer type: `{self.metadata.renderer_type.value}`",
            f"- Theme: `{self.metadata.theme_name}`",
            f"- Slides: {self.metadata.slide_count}",
            f"- Source digest: `{self.metadata.source_digest}`",
            "",
        ]
        if self.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
            lines.append("")
        lines.extend([
            "## Complete Deck Prompt",
            "",
            "~~~~text",
            self.deck_prompt,
            "~~~~",
            "",
            "## Per-Slide Prompts",
            "",
        ])
        for item in self.slide_prompts:
            lines.extend([
                f"### Slide {item.sequence_number}: `{item.slide_id}`",
                "",
                "~~~~text",
                item.prompt,
                "~~~~",
                "",
            ])
        return "\n".join(lines)

    def write(self, directory: str | Path) -> tuple[Path, Path]:
        """Write the required JSON and Markdown artifacts."""
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        json_path = target / "RendererPromptBundle.json"
        markdown_path = target / "RendererPromptBundle.md"
        json_path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(self.to_markdown() + "\n", encoding="utf-8")
        return json_path, markdown_path


__all__ = [
    "PromptBundle",
    "PromptBundleMetadata",
    "RendererType",
    "SlidePrompt",
]
