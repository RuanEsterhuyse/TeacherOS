"""Gamma-specific handoff adapter for validated renderer prompt bundles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from renderer.prompt_bundle import RendererType
from renderer.prompt_generator import generate_prompt_bundle
from schemas.curriculum_schema import CurriculumUnit
from schemas.presentation_design_schema import PresentationDesignOutput


GAMMA_PROMPT_FILENAME = "GammaDeckPrompt.md"
_METADATA_START = "BEGIN DECK METADATA SOURCE JSON"
_METADATA_END = "END DECK METADATA SOURCE JSON"
_PRIVATE_USE_PATTERN = re.compile(
    r"[\ue000-\uf8ff\U000f0000-\U000ffffd\U00100000-\U0010fffd]"
)
_MALFORMED_PUNCTUATION = str.maketrans(
    {
        "\ue081": "(",
        "\ue082": ")",
        "\ue083": ":",
        "\ue089": "–",
        "\ue08a": "—",
        "\ue08b": "“",
        "\ue08c": "”",
        "\ue08d": "‘",
        "\ue08e": "’",
        "\ue08f": "'",
        "\ue090": ":",
        "\ue091": " ",
        "\ue092": ":",
    }
)

_SOURCE_ASSET_FIDELITY_RULES = """STRICT SOURCE-ASSET FIDELITY RULES
- Never invent or recreate book covers.
- Never invent or alter author names, titles, quotations, page numbers, maps, document labels, or curriculum facts.
- Never place generated text inside a visual that represents a source document.
- Use an approved source asset when one is available and has been supplied or is accessible to the renderer.
- If no approved asset is supplied or accessible, use a neutral, editable placeholder clearly labeled for later replacement.
- Do not generate fake screenshots, fake textbook pages, fake covers, or fake maps.
- Do not duplicate slide content or repeat a slide unless the ordered deck specification explicitly requires it.
- Preserve exact supplied slide titles; do not expand them into longer headings."""

_RENDERER_REVIEW_WARNING = (
    "External presentation output must be reviewed before classroom use. "
    "Any generated visual containing factual text must be checked against the "
    "authoritative facts block."
)


@dataclass(frozen=True)
class GammaAuthoritativeFacts:
    """Validated curriculum facts that an external renderer may not rewrite."""

    curriculum_name: str
    unit_title: str
    lesson_title: str
    source_text_title: str
    source_text_author: str
    exact_activity_page_references: tuple[str, ...]
    exact_assigned_reading_pages: tuple[str, ...]
    approved_source_asset_references: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "curriculum_name": self.curriculum_name,
            "unit_title": self.unit_title,
            "lesson_title": self.lesson_title,
            "source_text_title": self.source_text_title,
            "source_text_author": self.source_text_author,
            "exact_activity_page_references": list(
                self.exact_activity_page_references
            ),
            "exact_assigned_reading_pages": list(
                self.exact_assigned_reading_pages
            ),
            "approved_source_asset_references": list(
                self.approved_source_asset_references
            ),
        }


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _source_text_author(student_reader_path: str | None) -> str:
    if not student_reader_path:
        return ""
    stem = Path(student_reader_path).stem
    return stem.rsplit(" - ", 1)[-1].strip() if " - " in stem else ""


def build_gamma_authoritative_facts(
    presentation: PresentationDesignOutput,
    curriculum: CurriculumUnit,
    *,
    activity_page_references: Iterable[str] = (),
    assigned_reading_pages: Iterable[str] = (),
) -> GammaAuthoritativeFacts:
    """Build immutable renderer facts from validated curriculum and lesson data."""
    source_assets = [
        value
        for value in (
            curriculum.teacher_guide_path,
            curriculum.student_reader_path,
            curriculum.activity_book_path,
        )
        if value
    ]
    source_assets.extend(
        slide.visuals.source_asset_reference
        for slide in presentation.slides
        if slide.visuals.source_asset_reference
    )
    unit_title = curriculum.unit_title or ""
    return GammaAuthoritativeFacts(
        curriculum_name=curriculum.curriculum_name,
        unit_title=unit_title,
        lesson_title=presentation.lesson_title,
        source_text_title=unit_title,
        source_text_author=_source_text_author(curriculum.student_reader_path),
        exact_activity_page_references=_unique(activity_page_references),
        exact_assigned_reading_pages=_unique(assigned_reading_pages),
        approved_source_asset_references=_unique(source_assets),
    )


def sanitize_gamma_renderer_text(value: str) -> str:
    """Normalize known malformed renderer punctuation and reject unknown PUA."""
    sanitized = value.translate(_MALFORMED_PUNCTUATION).replace("\u00a0", " ")
    remaining = sorted(
        {
            f"U+{ord(char):04X}"
            for char in _PRIVATE_USE_PATTERN.findall(sanitized)
        }
    )
    if remaining:
        raise ValueError(
            "unsupported private-use Unicode remains in Gamma prompt: "
            + ", ".join(remaining)
        )
    return sanitized


def _facts_block(facts: GammaAuthoritativeFacts | None) -> str:
    payload = facts.as_dict() if facts else {
        "curriculum_name": "",
        "unit_title": "",
        "lesson_title": "",
        "source_text_title": "",
        "source_text_author": "",
        "exact_activity_page_references": [],
        "exact_assigned_reading_pages": [],
        "approved_source_asset_references": [],
    }
    return "\n".join(
        [
            "AUTHORITATIVE FACTS — DO NOT REWRITE",
            "Treat every value in this block as exact, validated source data.",
            "BEGIN AUTHORITATIVE FACTS JSON",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "END AUTHORITATIVE FACTS JSON",
        ]
    )


def generate_gamma_deck_prompt(
    presentation: PresentationDesignOutput,
    theme: Mapping[str, Any] | str | Path | None = None,
    *,
    design_guide_path: str | Path | None = None,
    authoritative_facts: GammaAuthoritativeFacts | None = None,
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
    prompt = "\n\n".join(
        [
            "# Gamma Deck Prompt",
            _SOURCE_ASSET_FIDELITY_RULES,
            _facts_block(authoritative_facts),
            f"RENDERER REVIEW WARNING\n{_RENDERER_REVIEW_WARNING}",
            before.rstrip(),
            after.lstrip(),
        ]
    )
    return sanitize_gamma_renderer_text(prompt)


def write_gamma_deck_prompt(
    presentation: PresentationDesignOutput,
    directory: str | Path,
    theme: Mapping[str, Any] | str | Path | None = None,
    *,
    design_guide_path: str | Path | None = None,
    authoritative_facts: GammaAuthoritativeFacts | None = None,
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
            authoritative_facts=authoritative_facts,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "GAMMA_PROMPT_FILENAME",
    "GammaAuthoritativeFacts",
    "build_gamma_authoritative_facts",
    "generate_gamma_deck_prompt",
    "sanitize_gamma_renderer_text",
    "write_gamma_deck_prompt",
]
