"""Presentation safety-pass tests."""

from brain.presentation_expander import expand_presentation, reconcile_timing
from schemas.presentation_design_schema import (PresentationDesignOutput, PresentationSlide, StudentView,
    TeacherNotes, SlideDesign, VisualPlan, InteractionPlan)


def make_slide(**changes):
    data = dict(slide_id="S1", sequence_number=1, slide_type="activity",
        student_view=StudentView(title="Activity"), teacher_notes=TeacherNotes(),
        design=SlideDesign(layout="simple_directions"), visuals=VisualPlan(), interaction=InteractionPlan(),
        timing=12, day=1, source_references=["TG p. 1"], fidelity_classification="source_adapted")
    data.update(changes)
    return PresentationSlide(**data)


def expand(slide):
    return expand_presentation(PresentationDesignOutput(request_id="r1", slides=[slide]))


def test_long_body_splits_without_truncation_or_added_time():
    original = " ".join(f"word{i}" for i in range(95))
    result = expand(make_slide(student_view=StudentView(title="Read", body_text=original)))
    assert len(result.slides) == 3
    restored = " ".join(s.student_view.body_text or "" for s in result.slides)
    assert restored == original
    assert sum(s.timing or 0 for s in result.slides) == 12


def test_vocabulary_overflow_splits_into_four_term_cards():
    terms = [f"term {i} — definition" for i in range(9)]
    result = expand(make_slide(slide_type="vocabulary", design=SlideDesign(layout="vocabulary_cards"),
        student_view=StudentView(title="Vocabulary", vocabulary_terms=terms)))
    assert [len(s.student_view.vocabulary_terms) for s in result.slides] == [4, 4, 1]
    assert sum(s.timing or 0 for s in result.slides) == 12


def test_read_aloud_and_discussion_split_semantically():
    reading = expand(make_slide(slide_type="reading", design=SlideDesign(layout="read_aloud"),
        student_view=StudentView(title="Read-Aloud", prompt="Listen for change.",
            directions=["Follow along.", "Pause and record evidence."], sentence_frames=["The detail ___ shows ___."])))
    assert [s.design.layout.value for s in reading.slides] == ["read_aloud", "sentence_frame", "reading_checkpoint"]
    assert sum(s.timing or 0 for s in reading.slides) == 12

    discussion = expand(make_slide(slide_type="discussion", design=SlideDesign(layout="discussion_prompt"),
        student_view=StudentView(title="Discuss", prompt="How does identity matter?", directions=["Pair, then join a group of four."])))
    assert [s.design.layout.value for s in discussion.slides] == ["discussion_prompt", "progressive_grouping"]


def test_teacher_language_moves_to_notes_and_long_title_is_reflowed():
    title = "A very long classroom title " * 6
    result = expand(make_slide(student_view=StudentView(title=title,
        directions=["Teacher will distribute the page.", "Discuss one idea with a partner."])))
    slide = result.slides[0]
    assert len(slide.student_view.title) <= 90
    assert slide.student_view.subtitle
    assert slide.student_view.directions == ["Discuss one idea with a partner."]
    assert slide.teacher_notes.teacher_directions == ["Teacher will distribute the page."]


def test_timing_reconciliation_matches_instructional_day_without_adding_minutes():
    slides = [make_slide(slide_id=f"S{i}", sequence_number=i, timing=minutes)
              for i, minutes in enumerate((20, 20, 19), 1)]
    value = PresentationDesignOutput(request_id="r1", slides=slides)
    result = reconcile_timing(value, {1: 45})
    assert sum(slide.timing or 0 for slide in result.slides) == 45
    assert all((slide.timing or 0) > 0 for slide in result.slides)


def test_expansion_is_idempotent_for_generated_continuation_slides():
    reading = expand(make_slide(slide_type="reading", design=SlideDesign(layout="read_aloud"),
        student_view=StudentView(title="Read-Aloud", directions=["Follow along.", "Record evidence."],
            sentence_frames=["The detail ___ shows ___."])))
    second = expand_presentation(reading)
    assert [s.slide_id for s in second.slides] == [s.slide_id for s in reading.slides]
