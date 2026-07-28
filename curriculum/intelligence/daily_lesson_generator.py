"""One-action orchestration for the optional Daily Lesson Generator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from curriculum.intelligence.daily_lesson_provider import (
    DailyLessonProvider,
    select_daily_lesson_provider,
)
from curriculum.intelligence.daily_lesson_repository import (
    DailyLessonRepository,
)
from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.pasted_lesson_analyzer import (
    analyze_pasted_lesson,
)
from renderer.daily_lesson_markdown import (
    build_gemini_prompt,
    render_speaker_notes,
    render_teacher_playbook,
)
from schemas.daily_lesson_schema import (
    DAILY_LESSON_GENERATOR_VERSION,
    DailyGenerationMetadata,
    DailyLessonGenerationOptions,
    DailyLessonPackage,
    DailyLessonStatus,
    DailyPlaybookContext,
    DailySlideContext,
    DailySourceIdentity,
    GeminiSlidePrompt,
    GeneratedDailyPlaybook,
    GeneratedDailySlideOutline,
)
from schemas.pasted_lesson_schema import PastedLessonSource, SourceReference


PROMPT_ROOT = Path(__file__).parents[2] / "brain" / "prompts"
PLAYBOOK_PROMPT = PROMPT_ROOT / "daily_lesson_playbook_v1.md"
SLIDE_PROMPT = PROMPT_ROOT / "daily_lesson_slide_outline_v1.md"
PAGE_MENTION = re.compile(
    r"\b(?:pages?|pp\.|activity\s+page)\s*"
    r"([0-9]+(?:\.[0-9]+)?(?:\s*[–—-]\s*[0-9]+(?:\.[0-9]+)?)?)",
    re.IGNORECASE,
)


def _identity(source: PastedLessonSource) -> DailySourceIdentity:
    return DailySourceIdentity(
        source_id=source.source_id,
        grade=source.grade,
        unit=source.unit,
        lesson_number=source.lesson_number,
        lesson_title=source.lesson_title,
        teacher_guide_page_start=source.teacher_guide_page_start,
        teacher_guide_page_end=source.teacher_guide_page_end,
    )


def _reference_key(value: SourceReference) -> tuple:
    return (
        value.source_type,
        value.page_start,
        value.page_end,
        value.section,
        value.activity_reference,
    )


def _allowed_references(source, baseline) -> set[tuple]:
    values = list(baseline.playbook.source_references)
    for activity in baseline.playbook.activities:
        values.extend(activity.source_references)
    if source.teacher_guide_page_start is not None:
        values.append(SourceReference(
            source_type="teacher_guide",
            page_start=source.teacher_guide_page_start,
            page_end=source.teacher_guide_page_end,
            section=source.lesson_title,
        ))
    return {_reference_key(value) for value in values}


def _strings(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _validate_page_mentions(source, baseline, value: Any) -> None:
    source_text = "\n".join(filter(None, (
        source.teacher_guide_text,
        source.student_reader_text,
        source.activity_book_text,
    )))
    normalized_source = re.sub(r"\s+", "", source_text).replace(
        "—", "-"
    ).replace("–", "-")
    allowed_tokens = set()
    for reference in _allowed_references(source, baseline):
        if reference[1] is not None:
            token = str(reference[1])
            if reference[2] != reference[1]:
                token += f"-{reference[2]}"
            allowed_tokens.add(token)
    for text in _strings(value):
        for match in PAGE_MENTION.findall(text):
            token = re.sub(r"\s+", "", match).replace(
                "—", "-"
            ).replace("–", "-")
            if token not in normalized_source and token not in allowed_tokens:
                raise ValueError(
                    f"Generated output introduced unsupported page reference "
                    f"{match!r}."
                )


def _validate_references(source, baseline, references) -> None:
    allowed = _allowed_references(source, baseline)
    unsupported = [
        value for value in references if _reference_key(value) not in allowed
    ]
    if unsupported:
        raise ValueError(
            "Generated output introduced unsupported source references."
        )


def _validate_playbook(source, baseline, playbook) -> None:
    if playbook.lesson_information != _identity(source):
        raise ValueError("Generated playbook changed the source identity.")
    references = list(playbook.source_references)
    for activity in playbook.activities:
        references.extend(activity.source_references)
    _validate_references(source, baseline, references)
    baseline_ids = {
        activity.activity_id for activity in baseline.playbook.activities
    }
    generated_ids = {activity.activity_id for activity in playbook.activities}
    if generated_ids != baseline_ids:
        raise ValueError(
            "Generated playbook must preserve every baseline activity exactly once."
        )
    if playbook.source_references != baseline.playbook.source_references:
        raise ValueError(
            "Generated playbook did not preserve exact lesson references."
        )
    baseline_activities = {
        activity.activity_id: activity
        for activity in baseline.playbook.activities
    }
    for activity in playbook.activities:
        expected = baseline_activities[activity.activity_id].source_references
        if activity.source_references != expected:
            raise ValueError(
                "Generated playbook did not preserve exact activity references."
            )
    _validate_page_mentions(
        source, baseline, playbook.model_dump(mode="json")
    )


def _validate_slides(source, baseline, playbook, slides, options) -> None:
    activity_ids = {activity.activity_id for activity in playbook.activities}
    for slide in slides:
        if (
            slide.related_activity_id is not None
            and slide.related_activity_id not in activity_ids
        ):
            raise ValueError("Slide outline references an unknown activity.")
        _validate_references(
            source,
            baseline,
            slide.source_references + slide.speaker_notes.source_references,
        )
        visible_length = sum(
            len(value) for value in slide.exact_student_facing_text
        )
        if visible_length > options.maximum_student_text_characters:
            raise ValueError(
                f"Slide {slide.slide_number} exceeds the student-text limit."
            )
    _validate_page_mentions(
        source,
        baseline,
        [slide.model_dump(mode="json") for slide in slides],
    )


def generate_daily_lesson_package(
    source: PastedLessonSource,
    options: DailyLessonGenerationOptions | None = None,
    *,
    provider: DailyLessonProvider | None = None,
    repository: DailyLessonRepository | None = None,
) -> DailyLessonPackage:
    """Generate and persist a playbook before attempting slide prompts."""
    if not source.teacher_guide_text.strip():
        raise ValueError("Teacher Guide lesson text is required.")
    options = options or DailyLessonGenerationOptions()
    baseline = analyze_pasted_lesson(source)
    provider = select_daily_lesson_provider(provider)
    package_id = stable_id(
        "daily-lesson-package",
        source.source_id,
        content_digest(options.model_dump(mode="json")),
        provider.provider_name,
        provider.model_name,
        DAILY_LESSON_GENERATOR_VERSION,
    )
    playbook_response = provider.generate_playbook(
        DailyPlaybookContext(
            source=source,
            deterministic_baseline=baseline.model_dump(mode="json"),
            options=options,
        ),
        PLAYBOOK_PROMPT.read_text(encoding="utf-8"),
    )
    try:
        generated_playbook = GeneratedDailyPlaybook.model_validate(
            playbook_response.raw_payload
        )
    except (ValidationError, TypeError, ValueError) as error:
        raise ValueError("Malformed daily playbook output.") from error
    _validate_playbook(source, baseline, generated_playbook.playbook)
    markdown = render_teacher_playbook(generated_playbook.playbook)
    metadata = DailyGenerationMetadata(
        provider_name=provider.provider_name,
        model_name=provider.model_name,
        playbook_usage=playbook_response.usage,
    )
    package = DailyLessonPackage(
        package_id=package_id,
        source_identity=_identity(source),
        status=DailyLessonStatus.playbook_ready,
        teacher_playbook=generated_playbook.playbook,
        teacher_playbook_markdown=markdown,
        warnings=generated_playbook.warnings,
        source_references=generated_playbook.playbook.source_references,
        generation_metadata=metadata,
    )
    if repository:
        repository.save(package)
    try:
        slide_response = provider.generate_slide_outline(
            DailySlideContext(
                source=source,
                playbook=generated_playbook.playbook,
                options=options,
            ),
            SLIDE_PROMPT.read_text(encoding="utf-8"),
        )
        generated_slides = GeneratedDailySlideOutline.model_validate(
            slide_response.raw_payload
        )
        _validate_slides(
            source,
            baseline,
            generated_playbook.playbook,
            generated_slides.slides,
            options,
        )
    except Exception as error:
        warning = f"Slide prompt generation failed: {error}"
        partial = package.model_copy(update={
            "warnings": package.warnings + [warning],
        })
        if repository:
            repository.save(partial)
        return partial
    prompts = [
        GeminiSlidePrompt(
            slide_number=slide.slide_number,
            title=slide.title,
            prompt=build_gemini_prompt(
                slide,
                include_speaker_notes=options.include_speaker_notes_in_prompts,
            ),
            speaker_notes_markdown=render_speaker_notes(slide.speaker_notes),
        )
        for slide in generated_slides.slides
    ]
    complete = package.model_copy(update={
        "status": DailyLessonStatus.complete,
        "slide_outline": generated_slides.slides,
        "gemini_slide_prompts": prompts,
        "warnings": package.warnings + generated_slides.warnings,
        "generation_metadata": metadata.model_copy(update={
            "slide_usage": slide_response.usage,
        }),
    })
    if repository:
        repository.save(complete)
    return complete


__all__ = ["generate_daily_lesson_package"]
