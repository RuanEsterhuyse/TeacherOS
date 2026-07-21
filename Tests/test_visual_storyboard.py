from pathlib import Path
from brain.visual_storyboard import build_visual_storyboard, evaluate_visual_quality
from renderer.presentation_theme import load_visual_theme
from schemas.presentation_design_schema import PresentationDesignOutput
from schemas.visual_storyboard_schema import ComponentType, SlideFamily

FIXTURE=Path(__file__).parent/"fixtures"/"sample_lesson_1_presentation_design.json"


def board():
    return build_visual_storyboard(PresentationDesignOutput.model_validate_json(FIXTURE.read_text()),"warm_humanities")


def test_three_visual_themes_are_coherent_and_distinct():
    themes=[load_visual_theme(name) for name in ("modern_middle_school","warm_humanities","clean_academic")]
    assert len({t["primary"] for t in themes})==3
    assert all({"primary","secondary","accent","background","heading_font","body_font","card_style"}<=set(t) for t in themes)


def test_storyboard_creates_semantic_components_and_varied_families():
    value=board(); families={s.family for s in value.slides}
    assert {SlideFamily.CINEMATIC_TITLE,SlideFamily.VOCABULARY_CARDS,SlideFamily.DISCUSSION_QUESTION,
            SlideFamily.EVIDENCE_COLLECTION,SlideFamily.EXIT_TICKET}<=families
    components={c.component_type for s in value.slides for c in s.components}
    assert {ComponentType.TITLE_BLOCK,ComponentType.VOCABULARY_CARD,ComponentType.DISCUSSION_CARD,
            ComponentType.EXIT_TICKET_CARD}<=components


def test_storyboard_quality_evaluator_detects_layout_monotony():
    value=board()
    for slide in value.slides: slide.family=SlideFamily.GUIDED_PRACTICE
    findings=evaluate_visual_quality(value)
    assert any(item.startswith("layout_concentration") for item in findings)
    assert any(item.startswith("text_only_ratio") for item in findings)


def test_lesson_storyboard_map_is_native_component():
    presentation=PresentationDesignOutput.model_validate_json(Path("output/generation_runs/ckla-grade-8-unit-1-lesson-1/04_presentation_design.json").read_text())
    value=build_visual_storyboard(presentation)
    maps=[s for s in value.slides if s.family==SlideFamily.ANNOTATED_MAP]
    assert maps and any(c.component_type==ComponentType.MAP_PANEL for c in maps[0].components)
