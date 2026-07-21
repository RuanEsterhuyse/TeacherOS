"""Create a visual-first storyboard from validated presentation design."""

from collections import Counter
from schemas.presentation_design_schema import PresentationDesignOutput
from schemas.visual_storyboard_schema import *


def _family(slide):
    layout=slide.design.layout.value; title=slide.student_view.title.lower(); st=slide.slide_type.lower()
    if layout in {"title_slide","title_hero"}: return SlideFamily.CINEMATIC_TITLE
    if layout=="day_divider": return SlideFamily.SECTION_DIVIDER
    if layout=="objective_agenda" or "goal" in title: return SlideFamily.LESSON_GOALS_CARDS
    if "map" in title: return SlideFamily.ANNOTATED_MAP
    if "vocab" in st or layout.startswith("vocabulary"): return SlideFamily.VOCABULARY_CARDS
    if "book" in title or "text intro" in title: return SlideFamily.BOOK_OR_TEXT_INTRO
    if layout=="read_aloud": return SlideFamily.READ_ALOUD_FOCUS
    if layout=="sentence_frame": return SlideFamily.SENTENCE_FRAME_SPOTLIGHT
    if layout in {"quote_analysis","quote_focus"}: return SlideFamily.QUOTE_ANALYSIS
    if layout in {"evidence_analysis","evidence_chart"}: return SlideFamily.EVIDENCE_COLLECTION
    if layout in {"discussion_prompt","question_focus","turn_and_talk"}: return SlideFamily.DISCUSSION_QUESTION
    if layout=="progressive_grouping": return SlideFamily.PROGRESSIVE_GROUPING
    if layout in {"comparison","two_column"}: return SlideFamily.COMPARE_CONTRAST
    if layout in {"activity_steps","simple_directions"}: return SlideFamily.SEQUENCE_STEPS
    if layout=="exit_ticket": return SlideFamily.EXIT_TICKET
    if layout=="homework": return SlideFamily.HOMEWORK_SUMMARY
    if layout in {"image_and_prompt","full_visual"}: return SlideFamily.IMAGE_HOOK
    return SlideFamily.GUIDED_PRACTICE


def build_visual_storyboard(value: PresentationDesignOutput, theme: str="warm_humanities") -> VisualStoryboard:
    slides=[]
    for s in value.slides:
        v=s.student_view; family=_family(s); components=[]
        if v.title: components.append(StoryboardComponent(component_type="title_block",semantic_purpose="orient",text=[v.title],region="title",max_words=16))
        if v.subtitle: components.append(StoryboardComponent(component_type="subtitle",semantic_purpose="context",text=[v.subtitle],region="subtitle",max_words=20))
        if family==SlideFamily.LESSON_GOALS_CARDS:
            for item in v.bullet_points[:3]: components.append(StoryboardComponent(component_type="objective_chip",semantic_purpose="goal",text=[item],region="cards",max_words=18,icon_concept="target"))
        elif family==SlideFamily.VOCABULARY_CARDS:
            for item in v.vocabulary_terms[:4]: components.append(StoryboardComponent(component_type="vocabulary_card",semantic_purpose="vocabulary",text=[item],region="cards",max_words=18,icon_concept="concept"))
        elif family==SlideFamily.ANNOTATED_MAP:
            components.append(StoryboardComponent(component_type="map_panel",semantic_purpose="geography",text=["Minneapolis","Guanajuato"],region="visual",icon_concept="location"))
        elif family==SlideFamily.SENTENCE_FRAME_SPOTLIGHT:
            components.append(StoryboardComponent(component_type="sentence_frame_banner",semantic_purpose="language_support",text=v.sentence_frames,region="focus"))
        elif family==SlideFamily.QUOTE_ANALYSIS:
            components.append(StoryboardComponent(component_type="quote_block",semantic_purpose="analyze_text",text=[v.quotation or v.prompt or ""],region="focus"))
        elif family==SlideFamily.DISCUSSION_QUESTION:
            components.append(StoryboardComponent(component_type="discussion_card",semantic_purpose="discussion",text=[v.prompt or ""],region="focus"))
        elif family==SlideFamily.EXIT_TICKET:
            components.append(StoryboardComponent(component_type="exit_ticket_card",semantic_purpose="assessment",text=[v.prompt or "",*v.bullet_points],region="focus"))
        elif v.prompt:
            components.append(StoryboardComponent(component_type="prompt_card",semantic_purpose="focus",text=[v.prompt],region="focus"))
        if s.interaction.duration_minutes: components.append(StoryboardComponent(component_type="timer_badge",semantic_purpose="pacing",text=[f"{s.interaction.duration_minutes} min"],region="badge",max_words=3))
        slides.append(VisualStoryboardSlide(slide_id=s.slide_id,sequence_number=s.sequence_number,family=family,
            instructional_purpose=s.teacher_notes.instructional_purpose or s.slide_type,
            student_experience=s.interaction.interaction_type.value,visual_concept=s.visuals.visual_description or family.value,
            primary_focal_element=(v.prompt or v.title),supporting_visual_elements=s.visuals.icon_concepts,
            components=components,theme=theme,source_slide_id=s.slide_id))
    return VisualStoryboard(request_id=value.request_id,lesson_title=value.lesson_title,theme=theme,slides=slides,warnings=value.warnings)


def evaluate_visual_quality(board: VisualStoryboard) -> list[str]:
    findings=[]; total=max(1,len(board.slides)); families=[s.family.value for s in board.slides]
    most=Counter(families).most_common(1)[0]
    if most[1]/total>.35: findings.append(f"layout_concentration:{most[0]}:{most[1]}/{total}")
    visual_families={SlideFamily.CINEMATIC_TITLE,SlideFamily.SECTION_DIVIDER,SlideFamily.LESSON_GOALS_CARDS,
        SlideFamily.IMAGE_HOOK,SlideFamily.ANNOTATED_MAP,SlideFamily.VOCABULARY_CARDS,
        SlideFamily.VOCABULARY_IMAGE_GRID,SlideFamily.BOOK_OR_TEXT_INTRO,SlideFamily.SENTENCE_FRAME_SPOTLIGHT,
        SlideFamily.QUOTE_ANALYSIS,SlideFamily.EVIDENCE_COLLECTION,SlideFamily.PROGRESSIVE_GROUPING,
        SlideFamily.COMPARE_CONTRAST,SlideFamily.CAUSE_EFFECT,SlideFamily.TIMELINE,SlideFamily.SEQUENCE_STEPS,
        SlideFamily.EXIT_TICKET,SlideFamily.HOMEWORK_SUMMARY}
    text_only=sum(s.family not in visual_families for s in board.slides)
    if text_only/total>.25: findings.append(f"text_only_ratio:{text_only}/{total}")
    for a,b,c in zip(families,families[1:],families[2:]):
        if a==b==c: findings.append(f"three_consecutive:{a}"); break
    if not board.theme: findings.append("missing_theme")
    return findings
