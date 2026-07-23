"""Tests for the renderer-specific Gamma handoff adapter."""

from __future__ import annotations

from renderer.gamma_prompt import generate_gamma_deck_prompt, write_gamma_deck_prompt
from renderer.prompt_generator import generate_prompt_bundle, load_presentation_design_guide
from Tests.test_prompt_generator import (
    THEME,
    source_json_from_prompt,
    two_slide_presentation,
)


def test_gamma_prompt_contains_clean_complete_deck_without_duplicates() -> None:
    source = two_slide_presentation()
    prompt = generate_gamma_deck_prompt(source, THEME)

    assert load_presentation_design_guide() in prompt
    assert "IMMUTABLE CONTENT RULES" in prompt
    assert "TYPOGRAPHY" in prompt
    assert "COLOR PALETTE" in prompt
    assert "Slide count: 2" in prompt
    assert prompt.count("BEGIN SLIDE 1 SOURCE JSON") == 1
    assert prompt.count("BEGIN SLIDE 2 SOURCE JSON") == 1
    assert "Per-Slide Prompts" not in prompt
    assert "SINGLE-SLIDE SOURCE" not in prompt
    assert "BEGIN DECK METADATA SOURCE JSON" not in prompt
    assert "source_digest" not in prompt
    assert "warnings" not in prompt


def test_gamma_prompt_preserves_exact_ordered_lesson_content() -> None:
    source = two_slide_presentation()
    before = source.model_dump(mode="json")
    prompt = generate_gamma_deck_prompt(source, THEME)

    assert source.model_dump(mode="json") == before
    for slide in source.slides:
        assert source_json_from_prompt(prompt, slide.sequence_number) == (
            slide.model_dump(mode="json")
        )
    assert prompt.index("BEGIN SLIDE 1 SOURCE JSON") < prompt.index(
        "BEGIN SLIDE 2 SOURCE JSON"
    )


def test_gamma_prompt_is_deterministic_and_does_not_mutate_renderer_bundle(
    tmp_path,
) -> None:
    source = two_slide_presentation()
    bundle = generate_prompt_bundle(source, THEME)
    json_path, markdown_path = bundle.write(tmp_path)
    original_json = json_path.read_bytes()
    original_markdown = markdown_path.read_bytes()

    first_path = write_gamma_deck_prompt(source, tmp_path, THEME)
    first = first_path.read_bytes()
    second_path = write_gamma_deck_prompt(source, tmp_path, THEME)

    assert second_path.read_bytes() == first
    assert json_path.read_bytes() == original_json
    assert markdown_path.read_bytes() == original_markdown
