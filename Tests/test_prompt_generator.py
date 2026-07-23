"""Tests for deterministic, renderer-neutral prompt generation."""

from __future__ import annotations

import json

from renderer.prompt_bundle import PromptBundle, RendererType
from renderer.prompt_generator import (
    generate_prompt_bundle,
    load_presentation_design_guide,
)
from renderer.theme_loader import load_prompt_theme
from schemas.presentation_design_schema import PresentationDesignOutput, PresentationSlide
from Tests.test_generation_pipeline import presentation


THEME = {
    "name": "test_classroom",
    "dimensions": {"aspect_ratio": "16:9"},
    "typography": {
        "title_font": "Test Sans",
        "body_font": "Test Sans",
        "minimum_body_size": 20,
    },
    "colors": {
        "background": "#FFFFFF",
        "primary": "#112233",
        "text": "#000000",
    },
    "content_limits": {"maximum_words_per_slide": 45},
    "default_visual_style": "Serious, warm, modern classroom presentation",
}


def two_slide_presentation() -> PresentationDesignOutput:
    value = presentation()
    value.slides[0].student_view.prompt = 'Keep this exact: “Evidence ≠ opinion.”'
    value.slides[0].teacher_notes.teacher_script = "Say exactly: Do not simplify this explanation."
    second_data = value.slides[0].model_dump()
    second_data.update(
        slide_id="S02",
        sequence_number=2,
        slide_type="activity",
        timing=4,
        day=1,
    )
    second_data["student_view"]["title"] = "Second activity"
    second_data["student_view"]["directions"] = ["Read.", "Annotate.", "Discuss."]
    second_data["teacher_notes"]["teacher_script"] = "Keep students in assigned pairs."
    second_data["interaction"]["student_directions"] = ["Partner A begins."]
    second_data["design"]["layout"] = "activity_steps"
    second = PresentationSlide.model_validate(second_data)
    value.slides = [value.slides[0], second]
    return PresentationDesignOutput.model_validate(value.model_dump())


def source_json_from_prompt(prompt: str, sequence_number: int) -> dict:
    start = f"BEGIN SLIDE {sequence_number} SOURCE JSON\n"
    end = f"\nEND SLIDE {sequence_number} SOURCE JSON"
    return json.loads(prompt.split(start, 1)[1].split(end, 1)[0])


def test_slide_order_and_exact_schema_payload_are_preserved() -> None:
    source = two_slide_presentation()
    bundle = generate_prompt_bundle(source, THEME)

    assert [item.slide_id for item in bundle.slide_prompts] == ["S01", "S02"]
    assert [item.sequence_number for item in bundle.slide_prompts] == [1, 2]
    assert f'"theme": "{source.theme}"' in bundle.deck_prompt
    for slide, generated in zip(source.slides, bundle.slide_prompts):
        payload = source_json_from_prompt(generated.prompt, slide.sequence_number)
        assert payload == slide.model_dump(mode="json")
        assert source_json_from_prompt(bundle.deck_prompt, slide.sequence_number) == payload


def test_generation_does_not_mutate_or_paraphrase_content() -> None:
    source = two_slide_presentation()
    before = source.model_dump(mode="json")
    bundle = generate_prompt_bundle(source, THEME)

    assert source.model_dump(mode="json") == before
    exact_student_text = 'Keep this exact: “Evidence ≠ opinion.”'
    exact_teacher_text = "Say exactly: Do not simplify this explanation."
    assert exact_student_text in bundle.deck_prompt
    assert exact_teacher_text in bundle.deck_prompt
    assert exact_student_text in bundle.slide_prompts[0].prompt
    assert exact_teacher_text in bundle.slide_prompts[0].prompt


def test_teacher_student_separation_and_required_fields_are_preserved() -> None:
    source = two_slide_presentation()
    bundle = generate_prompt_bundle(source, THEME)
    payload = source_json_from_prompt(bundle.slide_prompts[1].prompt, 2)

    assert payload["student_view"]["directions"] == ["Read.", "Annotate.", "Discuss."]
    assert payload["teacher_notes"]["teacher_script"] == "Keep students in assigned pairs."
    assert payload["visuals"] == source.slides[1].visuals.model_dump(mode="json")
    assert payload["interaction"] == source.slides[1].interaction.model_dump(mode="json")
    assert payload["timing"] == 4
    assert payload["design"]["layout"] == "activity_steps"
    assert "Do not rewrite supplied content." in bundle.slide_prompts[1].prompt
    assert "Place teacher_notes in speaker notes" in bundle.slide_prompts[1].prompt
    assert all("Test Sans" in item.prompt for item in bundle.slide_prompts)
    assert all("#112233" in item.prompt for item in bundle.slide_prompts)


def test_generation_is_deterministic_and_prompts_stay_synchronized(tmp_path) -> None:
    source = two_slide_presentation()
    first = generate_prompt_bundle(source, THEME, renderer_type=RendererType.GEMINI)
    second = generate_prompt_bundle(source, THEME, renderer_type=RendererType.GEMINI)
    assert first == second

    for slide_prompt in first.slide_prompts:
        sequence = slide_prompt.sequence_number
        slide_payload = source_json_from_prompt(slide_prompt.prompt, sequence)
        assert source_json_from_prompt(first.deck_prompt, sequence) == slide_payload

    json_path, markdown_path = first.write(tmp_path)
    restored = PromptBundle.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert restored == first
    markdown = markdown_path.read_text(encoding="utf-8")
    assert first.deck_prompt in markdown
    assert all(item.prompt in markdown for item in first.slide_prompts)


def test_renderer_type_changes_only_renderer_wording() -> None:
    source = two_slide_presentation()
    generic = generate_prompt_bundle(source, THEME, renderer_type=RendererType.GENERIC)
    gemini = generate_prompt_bundle(source, THEME, renderer_type=RendererType.GEMINI)
    gamma = generate_prompt_bundle(source, THEME, renderer_type=RendererType.GAMMA)

    for sequence in (1, 2):
        expected = source.slides[sequence - 1].model_dump(mode="json")
        assert source_json_from_prompt(generic.deck_prompt, sequence) == expected
        assert source_json_from_prompt(gemini.deck_prompt, sequence) == expected
        assert source_json_from_prompt(gamma.deck_prompt, sequence) == expected
    assert "Google Slides" in gemini.deck_prompt
    assert "Gamma" in gamma.deck_prompt
    assert "Google Slides" not in generic.deck_prompt


def test_presentation_warnings_flow_to_bundle_without_changes() -> None:
    source = two_slide_presentation()
    source.warnings = ["Teacher review required: preserve this exact warning."]
    bundle = generate_prompt_bundle(source, THEME)
    assert bundle.warnings == source.warnings


def test_theme_loader_merges_partial_theme_and_warns_on_missing_file(tmp_path) -> None:
    loaded = load_prompt_theme({"name": "partial", "colors": {"accent": "#ABCDEF"}})
    assert loaded.name == "partial"
    assert loaded.settings["colors"]["accent"] == "#ABCDEF"
    assert loaded.settings["typography"]["title_font"] == "Arial"
    assert loaded.warnings == []

    fallback = load_prompt_theme(tmp_path / "missing-theme.json")
    assert fallback.name == "grade_8_modern"
    assert fallback.warnings


def test_design_guide_is_injected_once_into_deck_prompt_only() -> None:
    guide = load_presentation_design_guide()
    bundle = generate_prompt_bundle(two_slide_presentation(), THEME)

    assert bundle.deck_prompt.count(guide) == 1
    assert bundle.deck_prompt.index(guide) < bundle.deck_prompt.index("DECK SOURCE")
    assert all(guide not in item.prompt for item in bundle.slide_prompts)


def test_design_guide_is_renderer_neutral() -> None:
    guide = load_presentation_design_guide()
    prohibited_names = ("Gemini", "Gamma", "Google Slides")
    assert all(name not in guide for name in prohibited_names)
