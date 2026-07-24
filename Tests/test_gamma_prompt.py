"""Tests for the renderer-specific Gamma handoff adapter."""

from __future__ import annotations

import pytest

from renderer.gamma_prompt import (
    GammaAuthoritativeFacts,
    build_gamma_authoritative_facts,
    generate_gamma_deck_prompt,
    sanitize_gamma_renderer_text,
    write_gamma_deck_prompt,
)
from renderer.prompt_generator import generate_prompt_bundle, load_presentation_design_guide
from schemas.curriculum_schema import CurriculumUnit
from Tests.test_prompt_generator import (
    THEME,
    source_json_from_prompt,
    two_slide_presentation,
)

LESSON_1_FACTS = GammaAuthoritativeFacts(
    curriculum_name="CKLA",
    unit_title="Us, In Progress: Short Stories About Young Latinos",
    lesson_title='Read-Aloud: “The Attack”',
    source_text_title="Us, In Progress: Short Stories About Young Latinos",
    source_text_author="Lulu Delacre",
    exact_activity_page_references=("1.1", "1.2", "1.3", "SR.1"),
    exact_assigned_reading_pages=("1–15", "51–57"),
    approved_source_asset_references=(
        "data/curriculum/CKLA/Grade_8/Unit_1/Us, In Progress_ Short Stories About Young - Lulu Delacre.pdf",
    ),
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
    assert "neutral, editable placeholder clearly labeled for later replacement" in prompt
    assert "Do not generate fake screenshots, fake textbook pages, fake covers, or fake maps." in prompt
    assert "External presentation output must be reviewed before classroom use." in prompt


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


def test_gamma_prompt_preserves_lesson_1_authoritative_facts_exactly() -> None:
    prompt = generate_gamma_deck_prompt(
        two_slide_presentation(),
        THEME,
        authoritative_facts=LESSON_1_FACTS,
    )

    assert '"source_text_author": "Lulu Delacre"' in prompt
    assert (
        '"source_text_title": "Us, In Progress: Short Stories About Young Latinos"'
        in prompt
    )
    assert '"exact_activity_page_references": [' in prompt
    for reference in ("1.1", "1.2", "1.3", "SR.1"):
        assert f'"{reference}"' in prompt
    assert '"1–15"' in prompt
    assert '"51–57"' in prompt
    assert "Margarita Rivera" not in prompt
    assert "Never invent or alter author names, titles" in prompt


def test_lesson_1_author_is_derived_from_registered_source_asset() -> None:
    curriculum = CurriculumUnit(
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        unit_title="Us, In Progress: Short Stories About Young Latinos",
        teacher_guide_path="teacher-guide.pdf",
        student_reader_path=(
            "data/curriculum/CKLA/Grade_8/Unit_1/"
            "Us, In Progress_ Short Stories About Young - Lulu Delacre.pdf"
        ),
    )

    facts = build_gamma_authoritative_facts(
        two_slide_presentation(),
        curriculum,
        activity_page_references=("1.1", "1.2", "1.3", "SR.1"),
        assigned_reading_pages=("1–15", "51–57"),
    )

    assert facts.source_text_author == "Lulu Delacre"
    assert facts.source_text_title == curriculum.unit_title
    assert facts.exact_activity_page_references == ("1.1", "1.2", "1.3", "SR.1")


def test_gamma_prompt_normalizes_known_private_use_punctuation() -> None:
    malformed = "Pages 1\ue08915; \ue0811 min\ue082\ue092 read 3\ue0894."

    assert sanitize_gamma_renderer_text(malformed) == "Pages 1–15; (1 min): read 3–4."


def test_gamma_prompt_normalizes_renderer_quotes_apostrophes_and_spacing() -> None:
    malformed = (
        "\ue08bTitle\ue08c\ue083 \ue08dstudent\ue08fwork\ue08e"
        "\ue091A\ue08aB"
    )

    assert sanitize_gamma_renderer_text(malformed) == (
        "“Title”: ‘student'work’ A—B"
    )


def test_gamma_prompt_rejects_unknown_private_use_unicode() -> None:
    with pytest.raises(ValueError, match=r"U\+E099"):
        sanitize_gamma_renderer_text("unsupported \ue099 glyph")


def test_gamma_prompt_contains_no_private_use_unicode() -> None:
    prompt = generate_gamma_deck_prompt(
        two_slide_presentation(),
        THEME,
        authoritative_facts=LESSON_1_FACTS,
    )

    assert not any(
        "\ue000" <= character <= "\uf8ff"
        for character in prompt
    )
