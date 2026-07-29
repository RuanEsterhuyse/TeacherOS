"""Focused tests for the isolated Daily Lesson Generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.interface_server import TeacherOSInterface
from curriculum.intelligence.daily_lesson_generator import (
    generate_daily_lesson_package,
)
from curriculum.intelligence.daily_lesson_provider import (
    DAILY_PROVIDER_CONFIGURATION_ERROR,
    DEFAULT_GEMINI_MODEL,
    DailyProviderResponse,
    GeminiDailyLessonProvider,
    OpenAIDailyLessonProvider,
    daily_lesson_provider_status,
    select_daily_lesson_provider,
)
from curriculum.intelligence.daily_lesson_repository import (
    DailyLessonRepository,
)
from curriculum.intelligence.pasted_lesson_analyzer import (
    analyze_pasted_lesson,
)
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
    create_pasted_lesson_source,
)
from renderer.daily_lesson_markdown import DESIGN_LANGUAGE, render_slide_prompts
from schemas.daily_lesson_schema import (
    DailyLessonGenerationOptions,
    DailyLessonStatus,
    DailyPlaybookContext,
)


def _source(lesson_number: int = 1):
    return create_pasted_lesson_source(
        grade="8",
        unit="1",
        lesson_number=lesson_number,
        lesson_title=f"Evidence Lesson {lesson_number}",
        teacher_guide_page_start=10,
        teacher_guide_page_end=12,
        teacher_guide_text=(
            "Objectives:\n- Analyze evidence.\n"
            "Essential Question: How does evidence strengthen an idea?\n"
            "Materials:\n- Reader\n"
            "Vocabulary: evidence\n"
            "Activity: Evidence Talk — 10 minutes\n"
            "Purpose: Discuss evidence.\n"
            "Question: What evidence supports the claim?\n"
            "Student Reader pp. 3–4\n"
            "Homework: Reread the evidence notes."
        ),
        student_reader_text="Student Reader pp. 3–4: Synthetic evidence text.",
    )


def _untimed_source():
    return create_pasted_lesson_source(
        grade="8",
        unit="1",
        lesson_number=3,
        lesson_title="Untimed Agenda Lesson",
        teacher_guide_page_start=20,
        teacher_guide_page_end=22,
        teacher_guide_text=(
            "Objectives:\n- Explain how evidence supports an idea.\n"
            "Materials:\n- Reader\n"
            "Lesson sequence:\n"
            "Launch the question.\n"
            "Discuss evidence with a partner.\n"
            "Complete an exit response."
        ),
    )


def _untimed_playbook_payload(source):
    baseline = analyze_pasted_lesson(source)
    return {
        "playbook": {
            "lesson_information": {
                "source_id": source.source_id,
                "grade": source.grade,
                "unit": source.unit,
                "lesson_number": source.lesson_number,
                "lesson_title": source.lesson_title,
                "teacher_guide_page_start": 20,
                "teacher_guide_page_end": 22,
            },
            "lesson_meaning": "Students explain a claim with evidence.",
            "leave_understanding": ["Evidence must connect to the idea."],
            "essential_question": None,
            "content_objective": "Explain how evidence supports an idea.",
            "language_objective": "Explain reasoning with because.",
            "success_criteria": ["I can connect a detail to a claim."],
            "agenda": [
                {
                    "title": "Evidence Launch",
                    "duration_minutes": 8,
                    "purpose": "Introduce the evidence question.",
                },
                {
                    "title": "Partner Evidence Discussion",
                    "duration_minutes": 12,
                    "purpose": "Rehearse evidence-based reasoning.",
                },
            ],
            "materials": ["Reader"],
            "vocabulary": [],
            "teacher_survival_guide": [],
            "activities": [],
            "exit_ticket": ["Connect one detail to a claim."],
            "homework": [],
            "teacher_reflection": [],
            "source_references": [
                value.model_dump(mode="json")
                for value in baseline.playbook.source_references
            ],
            "unavailable_information": [],
        },
        "warnings": [],
    }


def _daily_slide(
    number,
    *,
    related_id,
    related_title,
    title=None,
):
    return {
        "slide_number": number,
        "title": title or f"Evidence Slide {number}",
        "instructional_purpose": "Support evidence-based reasoning.",
        "related_activity_id": related_id,
        "related_activity": related_title,
        "suggested_layout": "Title with one concise prompt.",
        "student_facing_content_summary": "An evidence discussion prompt.",
        "exact_student_facing_text": [
            "Which detail best supports the idea?"
        ],
        "suggested_visual": "A neutral editable evidence icon.",
        "speaker_notes": {
            "teacher_says": ["Ask students to explain the connection."],
            "teacher_does": ["Listen for claim, evidence, and reasoning."],
            "discussion_prompts": [],
            "anticipated_responses": [],
            "misconception_support": [],
            "checks_for_understanding": [],
            "transition": None,
            "timing_minutes": 4,
            "source_references": [],
        },
        "source_references": [],
    }


class UntimedAgendaProvider:
    provider_name = "fake"
    model_name = "untimed-agenda-test"

    def __init__(self, source, slide_builder=None):
        self.playbook_payload = _untimed_playbook_payload(source)
        self.slide_builder = slide_builder
        self.slide_context = None

    def generate_playbook(self, context, prompt_contract):
        return DailyProviderResponse(self.playbook_payload)

    def generate_slide_outline(self, context, prompt_contract):
        self.slide_context = context
        if self.slide_builder:
            slides = self.slide_builder(context.playbook)
        else:
            activity = context.playbook.activities[0]
            slides = [_daily_slide(
                1,
                related_id=activity.activity_id,
                related_title=activity.title,
            )]
        return DailyProviderResponse({"slides": slides, "warnings": []})


def _playbook_payload(source):
    baseline = analyze_pasted_lesson(source)
    activity = baseline.playbook.activities[0]
    identity = {
        "source_id": source.source_id,
        "grade": source.grade,
        "unit": source.unit,
        "lesson_number": source.lesson_number,
        "lesson_title": source.lesson_title,
        "teacher_guide_page_start": 10,
        "teacher_guide_page_end": 12,
    }
    return {
        "playbook": {
            "lesson_information": identity,
            "lesson_meaning": "Students connect claims to evidence.",
            "leave_understanding": ["Evidence makes reasoning visible."],
            "essential_question": "How does evidence strengthen an idea?",
            "content_objective": "Analyze evidence.",
            "language_objective": "Explain a claim using because.",
            "success_criteria": ["I can name relevant evidence."],
            "agenda": [{
                "title": activity.title,
                "duration_minutes": 10,
                "purpose": "Discuss evidence.",
            }],
            "materials": ["Reader"],
            "vocabulary": [{
                "term": "evidence",
                "student_friendly_definition": "Details that support an idea.",
                "teacher_guidance": "Connect the word to proof.",
            }],
            "teacher_survival_guide": ["Keep the claim visible."],
            "activities": [{
                "activity_id": activity.activity_id,
                "title": activity.title,
                "duration_minutes": 10,
                "purpose": "Discuss evidence.",
                "teacher_goal": "Make the reasoning audible.",
                "what_to_say": ["Name the claim before choosing evidence."],
                "questions": [{
                    "question": "What evidence supports the claim?",
                    "why_ask": "Students must connect detail to idea.",
                    "strong_responses": ["The detail directly proves the claim."],
                    "typical_responses": ["This sentence supports it."],
                    "weak_responses": ["I agree."],
                    "teacher_response": "Ask which exact detail proves it.",
                    "misconceptions": ["Any detail counts as evidence."],
                }],
                "examples_and_analogies": ["Evidence is a receipt for a claim."],
                "eld_supports": ["Rehearse with a partner."],
                "sentence_frames": ["The evidence ___ supports ___ because ___."],
                "checks_for_understanding": ["Listen for a claim and detail."],
                "look_fors": ["Relevant textual detail"],
                "ready_to_move_on_criteria": ["Most students explain relevance."],
                "transition": "Carry the strongest detail into writing.",
                "source_references": [
                    value.model_dump(mode="json")
                    for value in activity.source_references
                ],
            }],
            "exit_ticket": ["Name one claim and supporting detail."],
            "homework": ["Reread the evidence notes."],
            "teacher_reflection": ["Which students need another model?"],
            "source_references": [
                value.model_dump(mode="json")
                for value in baseline.playbook.source_references
            ],
            "unavailable_information": [],
        },
        "warnings": [],
    }


def _slides_payload(source, count: int = 2):
    baseline = analyze_pasted_lesson(source)
    activity = baseline.playbook.activities[0]
    reference = activity.source_references[0].model_dump(mode="json")
    slides = []
    for index in range(1, count + 1):
        slides.append({
            "slide_number": index,
            "title": "Evidence Talk" if index == 1 else "Try It",
            "instructional_purpose": "Prepare students to discuss evidence.",
            "related_activity_id": activity.activity_id,
            "related_activity": activity.title,
            "suggested_layout": "Title above two balanced content areas.",
            "student_facing_content_summary": "A concise evidence prompt.",
            "exact_student_facing_text": [
                "What evidence supports the claim?",
                "The evidence ___ supports ___ because ___.",
            ],
            "suggested_visual": "An editable magnifying-glass icon.",
            "speaker_notes": {
                "teacher_says": ["Name the claim first."],
                "teacher_does": ["Point to the sentence frame."],
                "discussion_prompts": ["Which detail is strongest?"],
                "anticipated_responses": ["A relevant detail."],
                "misconception_support": ["Relevance matters more than length."],
                "checks_for_understanding": ["Listen for because."],
                "transition": "Move into partner practice.",
                "timing_minutes": 5,
                "source_references": [reference],
            },
            "source_references": [reference],
        })
    return {"slides": slides, "warnings": []}


class FakeProvider:
    provider_name = "fake"
    model_name = "daily-test"

    def __init__(self, source, *, slide_count=2, slide_error=None):
        self.playbook_payload = _playbook_payload(source)
        self.slide_payload = _slides_payload(source, slide_count)
        self.slide_error = slide_error
        self.calls = []

    def generate_playbook(self, context, prompt_contract):
        self.calls.append("playbook")
        assert "Never invent" in prompt_contract
        return DailyProviderResponse(
            self.playbook_payload, {"input_tokens": 10}
        )

    def generate_slide_outline(self, context, prompt_contract):
        self.calls.append("slides")
        assert "universal slide count" in prompt_contract
        if self.slide_error:
            raise self.slide_error
        return DailyProviderResponse(
            self.slide_payload, {"input_tokens": 5}
        )


def test_one_action_generates_playbook_outline_and_self_contained_prompts(
    tmp_path,
):
    source = _source()
    provider = FakeProvider(source)
    repository = DailyLessonRepository(tmp_path / "daily")

    package = generate_daily_lesson_package(
        source, provider=provider, repository=repository
    )

    assert provider.calls == ["playbook", "slides"]
    assert package.status == DailyLessonStatus.complete
    assert len(package.slide_outline) == 2
    assert len(package.gemini_slide_prompts) == 2
    for prompt in package.gemini_slide_prompts:
        assert DESIGN_LANGUAGE in prompt.prompt
        assert "EXACT STUDENT-FACING TEXT" in prompt.prompt
        assert "SPEAKER NOTES" in prompt.prompt
        assert "What evidence supports the claim?" in prompt.prompt
    assert "Activity-by-Activity Guide" in package.teacher_playbook_markdown
    assert "Possible strong responses" in package.teacher_playbook_markdown


def test_different_lessons_can_produce_different_slide_counts():
    first = _source(1)
    second = _source(2)

    one = generate_daily_lesson_package(
        first, provider=FakeProvider(first, slide_count=1)
    )
    three = generate_daily_lesson_package(
        second, provider=FakeProvider(second, slide_count=3)
    )

    assert len(one.slide_outline) == 1
    assert len(three.slide_outline) == 3


def test_source_references_are_preserved_and_invented_pages_rejected():
    source = _source()
    provider = FakeProvider(source)
    package = generate_daily_lesson_package(source, provider=provider)
    assert package.source_references == (
        analyze_pasted_lesson(source).playbook.source_references
    )

    provider = FakeProvider(source)
    provider.playbook_payload["playbook"]["source_references"].append({
        "source_type": "teacher_guide",
        "page_start": 99,
        "page_end": 99,
        "section": None,
        "activity_reference": None,
    })
    with pytest.raises(ValueError, match="unsupported source references"):
        generate_daily_lesson_package(source, provider=provider)

    provider = FakeProvider(source)
    provider.playbook_payload["playbook"]["teacher_survival_guide"].append(
        "Turn to page 99 before class."
    )
    with pytest.raises(ValueError, match="unsupported page reference"):
        generate_daily_lesson_package(source, provider=provider)


def test_unsupported_slide_source_reference_is_removed_with_warning():
    source = _source()
    provider = FakeProvider(source)
    invented = {
        "source_type": "student_reader",
        "page_start": 99,
        "page_end": 100,
        "section": "Invented passage",
        "activity_reference": None,
    }
    provider.slide_payload["slides"][0]["source_references"] = [invented]

    package = generate_daily_lesson_package(source, provider=provider)

    assert package.status == DailyLessonStatus.complete
    assert package.slide_outline[0].source_references == []
    warning = next(
        value for value in package.warnings
        if "Removed unsupported slide source reference" in value
    )
    assert "student_reader" in warning
    assert "99–100" in warning
    assert "Invented passage" in warning


def test_mixed_valid_and_invalid_slide_references_preserve_valid_reference():
    source = _source()
    provider = FakeProvider(source)
    valid = provider.slide_payload["slides"][0]["source_references"][0]
    invented = {
        "source_type": "teacher_guide",
        "page_start": 88,
        "page_end": 88,
        "section": None,
        "activity_reference": None,
    }
    provider.slide_payload["slides"][0]["source_references"] = [
        valid, invented
    ]

    package = generate_daily_lesson_package(source, provider=provider)

    assert package.status == DailyLessonStatus.complete
    assert [
        value.model_dump(mode="json")
        for value in package.slide_outline[0].source_references
    ] == [valid]
    assert any(
        "pages=88–88" in warning
        for warning in package.warnings
    )


def test_generated_reference_normalizes_to_exact_approved_reference():
    source = _source()
    provider = FakeProvider(source)
    valid = provider.slide_payload["slides"][0]["source_references"][0]
    variant = {
        **valid,
        "source_type": valid["source_type"].replace("_", " ").upper(),
        "section": "Provider-added descriptive section",
    }
    provider.slide_payload["slides"][0]["source_references"] = [variant]

    package = generate_daily_lesson_package(source, provider=provider)

    assert [
        value.model_dump(mode="json")
        for value in package.slide_outline[0].source_references
    ] == [valid]
    assert any(
        "Normalized slide source reference" in warning
        for warning in package.warnings
    )


def test_one_invalid_slide_reference_preserves_all_valid_slides_and_prompts():
    source = _source()
    provider = FakeProvider(source, slide_count=3)
    provider.slide_payload["slides"][1]["speaker_notes"][
        "source_references"
    ] = [{
        "source_type": "novel",
        "page_start": 404,
        "page_end": 404,
        "section": "Not supplied",
        "activity_reference": None,
    }]

    package = generate_daily_lesson_package(source, provider=provider)

    assert package.status == DailyLessonStatus.complete
    assert len(package.slide_outline) == 3
    assert len(package.gemini_slide_prompts) == 3
    assert package.slide_outline[1].speaker_notes.source_references == []
    assert any(
        "Removed unsupported speaker-notes source reference from slide 2"
        in warning
        for warning in package.warnings
    )


def test_omitted_source_reference_is_rejected():
    source = _source()
    provider = FakeProvider(source)
    provider.playbook_payload["playbook"]["source_references"] = []

    with pytest.raises(ValueError, match="preserve exact lesson references"):
        generate_daily_lesson_package(source, provider=provider)


def test_partial_slide_failure_preserves_and_saves_playbook(tmp_path):
    source = _source()
    repository = DailyLessonRepository(tmp_path / "daily")

    package = generate_daily_lesson_package(
        source,
        provider=FakeProvider(source, slide_error=TimeoutError("timed out")),
        repository=repository,
    )

    assert package.status == DailyLessonStatus.playbook_ready
    assert package.slide_outline == []
    assert "timed out" in package.warnings[-1]
    saved = repository.load(package.package_id)
    assert saved.teacher_playbook_markdown == package.teacher_playbook_markdown
    assert (repository.package_directory(package.package_id)
            / "teacher_playbook.md").is_file()


def test_repository_round_trip_and_markdown_exports(tmp_path):
    source = _source()
    repository = DailyLessonRepository(tmp_path / "daily")
    package = generate_daily_lesson_package(
        source, provider=FakeProvider(source), repository=repository
    )

    assert repository.load(package.package_id) == package
    assert repository.read_markdown(
        package.package_id, "teacher_playbook.md"
    ).startswith("# Evidence Lesson")
    prompts = repository.read_markdown(
        package.package_id, "gemini_slide_prompts.md"
    )
    assert "SLIDE 1" in prompts and "SLIDE 2" in prompts
    assert prompts == render_slide_prompts(package)


def test_speaker_notes_are_separate_from_student_facing_text():
    source = _source()
    package = generate_daily_lesson_package(
        source, provider=FakeProvider(source)
    )
    slide = package.slide_outline[0]
    assert "Name the claim first." not in slide.exact_student_facing_text
    assert "Name the claim first." in (
        package.gemini_slide_prompts[0].speaker_notes_markdown
    )


def test_empty_lesson_text_and_malformed_provider_output_fail_clearly():
    source = _source()
    blank = source.model_copy(update={"teacher_guide_text": " "})
    with pytest.raises(ValueError, match="lesson text is required"):
        generate_daily_lesson_package(blank, provider=FakeProvider(source))

    provider = FakeProvider(source)
    provider.playbook_payload = {"wrong": True}
    with pytest.raises(ValueError, match="Malformed daily playbook"):
        generate_daily_lesson_package(source, provider=provider)


def test_successful_package_is_not_overwritten_by_later_partial_failure(
    tmp_path,
):
    source = _source()
    repository = DailyLessonRepository(tmp_path / "daily")
    complete = generate_daily_lesson_package(
        source, provider=FakeProvider(source), repository=repository
    )
    partial = generate_daily_lesson_package(
        source,
        provider=FakeProvider(source, slide_error=TimeoutError("later failure")),
        repository=repository,
    )

    assert partial.status == DailyLessonStatus.playbook_ready
    assert repository.load(complete.package_id).status == DailyLessonStatus.complete


def test_no_existing_generation_pipeline_modules_are_imported():
    path = Path(__file__).parents[1] / "curriculum" / "intelligence" / (
        "daily_lesson_generator.py"
    )
    text = path.read_text(encoding="utf-8")
    for protected in (
        "canonical_lesson",
        "presentation_spec",
        "renderer_instruction",
        "powerpoint",
        "gamma",
        "google_slides",
    ):
        assert f"import {protected}" not in text


def test_interface_one_action_and_artifact_downloads(tmp_path):
    source = _source()
    interface = TeacherOSInterface.__new__(TeacherOSInterface)
    interface.pasted_repository = PastedLessonRepository(tmp_path / "pasted")
    interface.daily_lesson_repository = DailyLessonRepository(
        tmp_path / "daily"
    )
    interface.daily_lesson_provider = FakeProvider(source)

    payload = {
        "grade": source.grade,
        "unit": source.unit,
        "lesson_number": source.lesson_number,
        "lesson_title": source.lesson_title,
        "teacher_guide_page_start": 10,
        "teacher_guide_page_end": 12,
        "teacher_guide_text": source.teacher_guide_text,
        "student_reader_text": source.student_reader_text,
        "activity_book_text": None,
    }
    result = interface.generate_daily_lesson(payload)

    assert result["status"] == "complete"
    assert interface.load_daily_lesson_package(
        result["package_id"]
    ) == result
    assert "Activity-by-Activity Guide" in (
        interface.read_daily_lesson_artifact(
            result["package_id"], "teacher_playbook.md"
        )
    )
    assert "SLIDE 1" in interface.read_daily_lesson_artifact(
        result["package_id"], "gemini_slide_prompts.md"
    )


def test_gemini_is_selected_before_openai_and_uses_default_model(
    monkeypatch,
):
    monkeypatch.delenv("TEACHEROS_DAILY_PROVIDER", raising=False)
    monkeypatch.delenv("TEACHEROS_DAILY_GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    provider = select_daily_lesson_provider()

    assert isinstance(provider, GeminiDailyLessonProvider)
    assert provider.provider_name == "gemini"
    assert provider.model_name == DEFAULT_GEMINI_MODEL
    assert provider.model_name == "gemini-3.6-flash"


def test_gemini_model_can_be_configured_without_changing_default(
    monkeypatch,
):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "TEACHEROS_DAILY_GEMINI_MODEL", "gemini-test-model"
    )

    provider = select_daily_lesson_provider()

    assert provider.model_name == "gemini-test-model"
    assert DEFAULT_GEMINI_MODEL == "gemini-3.6-flash"


def test_explicit_provider_override_has_highest_priority(monkeypatch):
    source = _source()
    explicit = FakeProvider(source)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    assert select_daily_lesson_provider(explicit) is explicit


def test_explicit_configured_openai_and_automatic_openai_fallback(
    monkeypatch,
):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    automatic = select_daily_lesson_provider()
    explicit = select_daily_lesson_provider(configured_provider="openai")

    assert isinstance(automatic, OpenAIDailyLessonProvider)
    assert isinstance(explicit, OpenAIDailyLessonProvider)


def test_missing_provider_keys_raise_neutral_configuration_error(
    monkeypatch,
):
    monkeypatch.delenv("TEACHEROS_DAILY_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(
        ValueError, match="GEMINI_API_KEY or OPENAI_API_KEY"
    ) as caught:
        select_daily_lesson_provider()

    assert str(caught.value) == DAILY_PROVIDER_CONFIGURATION_ERROR


@pytest.mark.parametrize(
    ("environment", "expected_provider"),
    [
        ({"GEMINI_API_KEY": "test-gemini-key"}, "gemini"),
        ({"OPENAI_API_KEY": "test-openai-key"}, "openai"),
    ],
)
def test_provider_status_reports_configured_provider_without_key(
    monkeypatch, environment, expected_provider
):
    for name in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "TEACHEROS_DAILY_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    status = daily_lesson_provider_status()

    assert status["available"] is True
    assert status["provider"] == expected_provider
    assert set(status) == {"available", "provider", "model", "message"}
    assert all("test-" not in str(value) for value in status.values())


def test_provider_status_reports_unconfigured_without_key(monkeypatch):
    for name in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "TEACHEROS_DAILY_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)

    assert daily_lesson_provider_status() == {
        "available": False,
        "provider": None,
        "model": None,
        "message": DAILY_PROVIDER_CONFIGURATION_ERROR,
    }


def test_interface_provider_status_uses_injected_provider():
    source = _source()
    interface = TeacherOSInterface.__new__(TeacherOSInterface)
    interface.daily_lesson_provider = FakeProvider(source)

    assert interface.daily_lesson_provider_status() == {
        "available": True,
        "provider": "fake",
        "model": "daily-test",
        "message": "Fake is configured for live lesson generation.",
    }


def _gemini_playbook_context(source):
    return DailyPlaybookContext(
        source=source,
        deterministic_baseline=analyze_pasted_lesson(source).model_dump(
            mode="json"
        ),
        options=DailyLessonGenerationOptions(),
    )


def test_gemini_structured_response_and_request_contract():
    source = _source()
    observed = {}

    def transport(url, payload, timeout, api_key):
        observed.update({
            "url": url,
            "payload": payload,
            "timeout": timeout,
            "api_key": api_key,
        })
        return {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps(_playbook_payload(source))
                    }]
                }
            }],
            "usageMetadata": {"promptTokenCount": 12},
        }

    provider = GeminiDailyLessonProvider(
        api_key="test-gemini-key",
        transport=transport,
    )
    response = provider.generate_playbook(
        _gemini_playbook_context(source),
        "Never invent source facts.",
    )

    assert response.raw_payload == _playbook_payload(source)
    assert response.usage == {"promptTokenCount": 12}
    assert provider.model_name in observed["url"]
    assert "test-gemini-key" not in observed["url"]
    assert observed["api_key"] == "test-gemini-key"
    assert observed["payload"]["generationConfig"][
        "responseMimeType"
    ] == "application/json"
    assert "responseJsonSchema" in observed["payload"]["generationConfig"]


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"candidates": []},
        {"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]},
    ],
)
def test_malformed_gemini_response_fails_structured_validation(response):
    source = _source()

    def transport(url, payload, timeout, api_key):
        return response

    provider = GeminiDailyLessonProvider(
        api_key="test-gemini-key",
        transport=transport,
    )

    with pytest.raises(ValueError, match="malformed structured response"):
        provider.generate_playbook(
            _gemini_playbook_context(source), "Prompt"
        )


def test_gemini_timeout_is_reported_without_live_call():
    source = _source()

    def transport(url, payload, timeout, api_key):
        raise TimeoutError("Gemini request timed out.")

    provider = GeminiDailyLessonProvider(
        api_key="test-gemini-key",
        transport=transport,
    )

    with pytest.raises(TimeoutError, match="timed out"):
        provider.generate_playbook(
            _gemini_playbook_context(source), "Prompt"
        )


def test_no_timed_headings_generates_outline_from_agenda_fallback():
    source = _untimed_source()
    baseline = analyze_pasted_lesson(source)
    provider = UntimedAgendaProvider(source)

    package = generate_daily_lesson_package(source, provider=provider)

    assert baseline.playbook.activities == []
    assert any(
        warning.message == "No timed activity headings found."
        for warning in baseline.warnings
    )
    assert package.status == DailyLessonStatus.complete
    assert len(package.slide_outline) == 1
    assert len(package.gemini_slide_prompts) == 1
    assert package.slide_outline[0].related_activity == "Evidence Launch"


def test_empty_activity_guide_creates_stable_fallback_activity_records():
    source = _untimed_source()
    provider = UntimedAgendaProvider(source)
    assert provider.playbook_payload["playbook"]["activities"] == []

    first = generate_daily_lesson_package(source, provider=provider)
    second = generate_daily_lesson_package(
        source, provider=UntimedAgendaProvider(source)
    )

    assert len(first.teacher_playbook.activities) == 2
    assert [
        activity.activity_id for activity in first.teacher_playbook.activities
    ] == [
        activity.activity_id for activity in second.teacher_playbook.activities
    ]
    assert "### 1. Evidence Launch" in first.teacher_playbook_markdown
    assert any(
        "Created fallback activity records" in warning
        for warning in first.warnings
    )


def test_activity_title_resolves_when_provider_id_does_not_match():
    source = _untimed_source()

    def slides(playbook):
        return [_daily_slide(
            1,
            related_id="provider-generated-wrong-id",
            related_title="  evidence launch  ",
        )]

    package = generate_daily_lesson_package(
        source,
        provider=UntimedAgendaProvider(source, slides),
    )

    activity = package.teacher_playbook.activities[0]
    assert package.status == DailyLessonStatus.complete
    assert package.slide_outline[0].related_activity_id == activity.activity_id
    assert package.slide_outline[0].related_activity == activity.title
    assert not any(
        "Unmatched slide activity" in warning
        for warning in package.warnings
    )


def test_one_unknown_activity_keeps_all_other_slides_and_prompts():
    source = _untimed_source()

    def slides(playbook):
        known = playbook.activities[0]
        return [
            _daily_slide(
                1,
                related_id=known.activity_id,
                related_title=known.title,
            ),
            _daily_slide(
                2,
                related_id="unknown-provider-activity",
                related_title="Unscheduled Debate",
            ),
        ]

    package = generate_daily_lesson_package(
        source,
        provider=UntimedAgendaProvider(source, slides),
    )

    assert package.status == DailyLessonStatus.complete
    assert len(package.slide_outline) == 2
    assert len(package.gemini_slide_prompts) == 2
    assert package.slide_outline[0].related_activity_id is not None
    assert package.slide_outline[1].related_activity_id is None
    warning = next(
        value for value in package.warnings
        if "Unmatched slide activity" in value
    )
    assert "Unscheduled Debate" in warning
    assert "unknown-provider-activity" in warning
