"""Deterministic safety pass for classroom-readable presentation units."""

from __future__ import annotations

import re

from schemas.presentation_design_schema import (PresentationDesignOutput, PresentationSlide, SlideLayout,
    ImagePlacement, InteractionPlan)

_TEACHER_LINE = re.compile(r"^(?:say|ask|have students|teacher(?: will| should)?|project|distribute|circulate)\b", re.I)


def _move_teacher_lines(slide: PresentationSlide) -> None:
    view, notes = slide.student_view, slide.teacher_notes
    kept = []
    for line in view.directions:
        if _TEACHER_LINE.search(line.strip()):
            notes.teacher_directions.append(line)
        else:
            kept.append(line)
    view.directions = kept
    for field in ("body_text", "subtitle", "footer_text"):
        value = getattr(view, field)
        if value and _TEACHER_LINE.search(value.strip()):
            notes.teacher_directions.append(value)
            setattr(view, field, None)


def _continuation(source: PresentationSlide, suffix: str, layout: SlideLayout,
                  *, title: str, directions=None, frames=None, bullets=None, terms=None, body=None) -> PresentationSlide:
    copy = source.model_copy(deep=True)
    copy.slide_id = f"{source.slide_id}_{suffix}"
    copy.slide_type = layout.value
    copy.timing = None
    copy.design.layout = layout
    copy.design.image_position = ImagePlacement.NONE
    copy.visuals.visual_required = False
    copy.visuals.image_prompt = None
    copy.visuals.source_asset_reference = None
    copy.interaction = InteractionPlan()
    copy.student_view.title = title
    copy.student_view.subtitle = None
    copy.student_view.body_text = body
    copy.student_view.prompt = None
    copy.student_view.quotation = None
    copy.student_view.bullet_points = list(bullets or [])
    copy.student_view.directions = list(directions or [])
    copy.student_view.sentence_frames = list(frames or [])
    copy.student_view.vocabulary_terms = list(terms or [])
    return copy


def expand_presentation(value: PresentationDesignOutput) -> PresentationDesignOutput:
    """Move teacher-only lines and split overloaded slides without adding time."""
    output = value.model_copy(deep=True)
    expanded: list[PresentationSlide] = []
    for slide in output.slides:
        _move_teacher_lines(slide)
        view = slide.student_view
        if len(view.title) > 90:
            split_at = view.title.rfind(" ", 0, 90)
            split_at = split_at if split_at > 45 else 90
            remainder = view.title[split_at:].strip()
            view.title = view.title[:split_at].strip()
            view.subtitle = f"{remainder} — {view.subtitle}" if view.subtitle else remainder
        layout = slide.design.layout
        if len(view.vocabulary_terms) > 4:
            terms = list(view.vocabulary_terms)
            view.vocabulary_terms = terms[:4]
            expanded.append(slide)
            for start in range(4, len(terms), 4):
                expanded.append(_continuation(slide, f"vocab_{start // 4 + 1}", SlideLayout.VOCABULARY_CARDS,
                    title=f"{view.title} — continued", terms=terms[start:start + 4]))
            continue
        if view.body_text and len(view.body_text.split()) > 40:
            words = view.body_text.split()
            chunks = [" ".join(words[start:start + 40]) for start in range(0, len(words), 40)]
            view.body_text = chunks[0]
            expanded.append(slide)
            for number, body in enumerate(chunks[1:], 2):
                expanded.append(_continuation(slide, f"part_{number}", SlideLayout.NO_VISUAL,
                    title=f"{view.title} — continued", body=body))
            continue
        if len(view.bullet_points) > 5:
            bullets = list(view.bullet_points)
            view.bullet_points = bullets[:5]
            expanded.append(slide)
            for start in range(5, len(bullets), 5):
                expanded.append(_continuation(slide, f"points_{start // 5 + 1}", SlideLayout.SIMPLE_DIRECTIONS,
                    title=f"{view.title} — continued", bullets=bullets[start:start + 5]))
            continue
        is_reading = layout in {SlideLayout.READ_ALOUD, SlideLayout.READING_CHECKPOINT} or (
            layout not in {SlideLayout.SENTENCE_FRAME, SlideLayout.SIMPLE_DIRECTIONS}
            and "read-aloud" in view.title.lower())
        if is_reading and (view.sentence_frames or len(view.directions) > 1):
            frames, directions = list(view.sentence_frames), list(view.directions)
            view.sentence_frames = []
            view.directions = directions[:1]
            expanded.append(slide)
            if frames:
                expanded.append(_continuation(slide, "evidence_frame", SlideLayout.SENTENCE_FRAME,
                    title=f"Evidence Frame — {view.title}", frames=frames))
            if len(directions) > 1:
                expanded.append(_continuation(slide, "checkpoint", SlideLayout.READING_CHECKPOINT,
                    title="Reading Checkpoint", directions=directions[1:]))
            continue
        is_discussion = layout in {SlideLayout.DISCUSSION_PROMPT, SlideLayout.PROGRESSIVE_GROUPING} or "progress" in slide.slide_type.lower()
        if is_discussion and view.prompt and view.directions:
            directions = list(view.directions)
            view.directions = []
            expanded.append(slide)
            expanded.append(_continuation(slide, "grouping", SlideLayout.PROGRESSIVE_GROUPING,
                title=f"Discussion Process — {view.title}", directions=directions, frames=view.sentence_frames))
            expanded[-1].interaction = slide.interaction.model_copy(deep=True)
            slide.interaction = InteractionPlan()
            view.sentence_frames = []
            continue
        supporting = bool(view.directions or view.sentence_frames or len(view.bullet_points) > 3)
        if len(view.all_text().split()) > 60 and supporting:
            directions, frames, bullets = list(view.directions), list(view.sentence_frames), list(view.bullet_points)
            view.directions = []; view.sentence_frames = []; view.bullet_points = bullets[:3]
            expanded.append(slide)
            expanded.append(_continuation(slide, "directions", SlideLayout.SIMPLE_DIRECTIONS,
                title=f"{view.title} — directions", directions=directions, frames=frames, bullets=bullets[3:]))
            continue
        expanded.append(slide)
    for index, slide in enumerate(expanded, 1):
        slide.sequence_number = index
    output.slides = expanded
    return PresentationDesignOutput.model_validate(output)


def reconcile_timing(value: PresentationDesignOutput, expected_by_day: dict[int, int]) -> PresentationDesignOutput:
    """Allocate existing source minutes across split slides without changing day totals."""
    output = value.model_copy(deep=True)
    for day, target in expected_by_day.items():
        slides = [s for s in output.slides if (s.day or 1) == day and s.design.layout != SlideLayout.DAY_DIVIDER]
        timed = [s for s in slides if s.timing is not None and s.timing > 0]
        if not timed or target < len(timed):
            continue
        current = sum(s.timing or 0 for s in timed)
        if current == target:
            continue
        raw = [target * (s.timing or 0) / current for s in timed]
        allocated = [max(1, int(amount)) for amount in raw]
        while sum(allocated) < target:
            index = max(range(len(raw)), key=lambda i: raw[i] - allocated[i])
            allocated[index] += 1
        while sum(allocated) > target:
            candidates = [i for i, amount in enumerate(allocated) if amount > 1]
            if not candidates: break
            index = min(candidates, key=lambda i: raw[i] - allocated[i])
            allocated[index] -= 1
        for slide, minutes in zip(timed, allocated):
            slide.timing = minutes
        output.warnings.append(f"Renderer safety pass reconciled Day {day} timing from {current} to {target} source minutes.")
    return PresentationDesignOutput.model_validate(output)
