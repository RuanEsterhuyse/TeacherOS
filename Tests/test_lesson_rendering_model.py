"""Focused offline tests for the Phase 5A lesson rendering model."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from curriculum.intelligence.grounded_instructional_intelligence import (
    DEFAULT_PROMPT_PATH,
    GroundedInstructionalIntelligenceService,
)
from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.lesson_phase_support import (
    ExpectedPhaseSupportIdentity,
    resolve_phase_support,
)
from curriculum.intelligence.lesson_rendering_model import (
    LessonRenderingModelService,
    build_lesson_rendering_model,
)
from curriculum.intelligence.lesson_rendering_model_validator import (
    validate_lesson_rendering_model,
)
from curriculum.intelligence.instruction_plan import (
    SourceGroundedInstructionPlanBuilder,
)
from curriculum.intelligence.relationship_graph import (
    InstructionalRelationshipGraphBuilder,
)
from schemas.lesson_rendering_model_schema import (
    AnswerRevealBehavior,
    ContentOrigin,
    RenderingReadinessStatus,
    SlideScope,
    SlideType,
    SupportStatus,
)
from Tests.test_grounded_instructional_intelligence import (
    FakeProvider,
    intelligence_bundle,
)


@pytest.fixture
def rendering_fixture(tmp_path: Path):
    bundle = intelligence_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    graph, audit = InstructionalRelationshipGraphBuilder().build(bundle, plan)
    manifest, drafts = resolve_phase_support(
        bundle, plan, graph, audit, cache_directory=None
    )
    source_only = build_lesson_rendering_model(
        bundle, plan, graph, audit,
        support_manifest=manifest, support_drafts=drafts,
    )
    return {
        "root": tmp_path, "bundle": bundle, "plan": plan,
        "graph": graph, "audit": audit, "manifest": manifest,
        "drafts": drafts, "model": source_only,
    }


def _validate(fixture, model=None, drafts=None):
    return validate_lesson_rendering_model(
        model or fixture["model"], fixture["bundle"], fixture["plan"],
        fixture["graph"], fixture["audit"],
        support_drafts=fixture["drafts"] if drafts is None else drafts,
    )


def _generate_support(fixture, *, generation_parameters=None):
    paths = {}
    for name, value in (
        ("bundle_path", fixture["bundle"]),
        ("instruction_plan_path", fixture["plan"]),
        ("relationship_graph_path", fixture["graph"]),
        ("relationship_graph_audit_path", fixture["audit"]),
    ):
        path = fixture["root"] / f"{name}.json"
        path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
        paths[name] = path
    phase = fixture["plan"].instructional_phases[5]
    output = fixture["root"] / "phase-support"
    result = GroundedInstructionalIntelligenceService(
        FakeProvider()
    ).generate(
        **paths, phase_id=phase.id, output_directory=output,
        generation_parameters=generation_parameters,
    )
    return output, result


def _expected_identity(result):
    draft = result.draft
    context = result.context
    return ExpectedPhaseSupportIdentity(
        phase_id=draft.phase_id,
        cache_key=result.cache_key,
        context_digest=context.context_digest,
        prepared_bundle_digest=context.prepared_bundle_digest,
        instruction_plan_digest=context.instruction_plan_digest,
        relationship_graph_digest=context.relationship_graph_digest,
        prompt_version=draft.prompt_version,
        prompt_content_digest=content_digest(
            Path(DEFAULT_PROMPT_PATH).read_text(encoding="utf-8")
        ),
        provider=draft.provider,
        model=draft.model,
        generation_parameters=draft.generation_metadata.generation_parameters,
        support_schema_version=draft.schema_version,
        support_builder_version=draft.builder_version,
        content_digest=draft.content_digest,
        draft_digest=draft.digest,
    )


def _with_recalculated_digests(model):
    from curriculum.intelligence.ids import content_digest
    value = model.model_copy(update={
        "content_digest": content_digest(model.model_dump(
            mode="json",
            exclude={"content_digest", "artifact_digest", "warnings", "blockers"},
        )),
        "artifact_digest": "pending",
    })
    return value.model_copy(update={
        "artifact_digest": content_digest(
            value.model_dump(mode="json", exclude={"artifact_digest"})
        )
    })


def test_valid_source_only_model_and_exact_phase_order(rendering_fixture) -> None:
    model = rendering_fixture["model"]
    report = _validate(rendering_fixture)
    assert model.readiness_status == RenderingReadinessStatus.SOURCE_READY
    assert report.status == "pass_with_warnings"
    assert [item.phase_id for item in model.phases] == [
        item.id for item in rendering_fixture["plan"].instructional_phases
    ]
    assert all(item.covered for item in model.phase_coverage)


def test_every_slide_has_exactly_one_explicit_coverage_scope(rendering_fixture) -> None:
    model = rendering_fixture["model"]
    slide_ids = [item.slide_id for item in model.slides]
    covered_ids = [item.slide_id for item in model.slide_coverage]
    valid_phases = {item.phase_id for item in model.phases}

    assert covered_ids == slide_ids
    assert len(covered_ids) == len(set(covered_ids))
    assert all(
        (
            item.scope == SlideScope.LESSON_STRUCTURE
            and item.phase_id is None
        )
        or (
            item.scope == SlideScope.PHASE
            and item.phase_id in valid_phases
        )
        for item in model.slide_coverage
    )
    phase_count = sum(len(item.slide_ids) for item in model.phase_coverage)
    lesson_count = sum(
        item.scope == SlideScope.LESSON_STRUCTURE
        for item in model.slide_coverage
    )
    assert phase_count + lesson_count == len(model.slides)


def test_orphaned_or_multiply_covered_slide_blocks(rendering_fixture) -> None:
    model = rendering_fixture["model"].model_copy(deep=True)
    model.slide_coverage.pop()
    model.slide_coverage.append(model.slide_coverage[0].model_copy())
    codes = {item.code for item in _validate(rendering_fixture, model).findings}
    assert {
        "slide_coverage_order_invalid",
        "duplicate_slide_coverage",
        "orphaned_slide",
        "slide_count_accounting_invalid",
    } <= codes


def test_valid_model_with_phase_six_cached_support(rendering_fixture) -> None:
    output, result = _generate_support(rendering_fixture)
    manifest, drafts = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={
            rendering_fixture["plan"].instructional_phases[5].id:
                _expected_identity(result)
        },
    )
    model = build_lesson_rendering_model(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        support_manifest=manifest, support_drafts=drafts,
    )
    report = _validate(rendering_fixture, model, drafts)
    assert model.readiness_status == RenderingReadinessStatus.SOURCE_READY_WITH_SUPPORT
    assert report.status == "pass_with_warnings"
    assert manifest[5].status == SupportStatus.VALID_CACHE
    assert model.source_snapshot.ordered_support_digests == [
        result.draft.content_digest
    ]


def test_all_phase_six_questions_and_answers_are_accounted_for(rendering_fixture) -> None:
    phase = rendering_fixture["plan"].instructional_phases[5]
    coverage = [
        item for item in rendering_fixture["model"].question_coverage
        if item.phase_id == phase.id
    ]
    assert len(phase.questions) == len(coverage) == 32
    assert [item.question_id for item in coverage] == [
        item.id for item in phase.questions
    ]
    assert [item.source_answer_ids for item in coverage] == [
        [answer.id for answer in item.answers] for item in phase.questions
    ]
    assert all(
        item.answer_disposition == AnswerRevealBehavior.SPEAKER_NOTES_ONLY
        for item in coverage
    )


def test_phase_seven_open_questions_remain_unanswered(rendering_fixture) -> None:
    phase = rendering_fixture["plan"].instructional_phases[6]
    coverage = [
        item for item in rendering_fixture["model"].question_coverage
        if item.phase_id == phase.id
    ]
    assert len(coverage) == 3
    assert all(not item.source_answer_ids for item in coverage)
    assert all(
        item.answer_disposition == AnswerRevealBehavior.NOT_AVAILABLE
        for item in coverage
    )


def test_question_capacity_long_question_and_contiguous_numbers(rendering_fixture) -> None:
    model = rendering_fixture["model"]
    assert max((len(item.question_ids) for item in model.slides), default=0) <= 3
    assert [item.slide_number for item in model.slides] == list(
        range(1, len(model.slides) + 1)
    )
    source = rendering_fixture["plan"].instructional_phases[5].questions
    long_ids = {
        item.id for item in source
        if len(item.question_text.split()) > 24
        or item.question_text.count("?") > 1
    }
    assert all(
        len(slide.question_ids) == 1
        for slide in model.slides
        if set(slide.question_ids) & long_ids
    )


def test_student_visible_and_teacher_notes_origins_are_separate(rendering_fixture) -> None:
    output, result = _generate_support(rendering_fixture)
    manifest, drafts = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={
            result.draft.phase_id: _expected_identity(result)
        },
    )
    model = build_lesson_rendering_model(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        support_manifest=manifest, support_drafts=drafts,
    )
    visible = [
        item
        for slide in model.slides
        for item in (
            [slide.student_visible_content.title]
            + slide.student_visible_content.directions
            + slide.student_visible_content.statements
        )
    ]
    support_notes = [
        item
        for slide in model.slides
        for item in (
            slide.teacher_notes.facilitation_notes
            + slide.teacher_notes.checks_for_understanding
            + slide.teacher_notes.language_supports
            + slide.teacher_notes.differentiation_supports
        )
    ]
    assert all(
        item.origin != ContentOrigin.AI_GENERATED_TEACHER_SUPPORT
        for item in visible
    )
    assert support_notes
    assert all(
        item.origin == ContentOrigin.AI_GENERATED_TEACHER_SUPPORT
        for item in support_notes
    )
    assert all(
        answer.origin == ContentOrigin.PUBLISHER_SOURCE
        for slide in model.slides
        for answer in slide.teacher_notes.source_answers
    )


def test_question_mutation_answer_mutation_and_wrong_link_block(rendering_fixture) -> None:
    model = rendering_fixture["model"].model_copy(deep=True)
    question_slide = next(item for item in model.slides if item.question_ids)
    question_slide.student_visible_content.statements[0].text += " changed"
    question_slide.teacher_notes.source_answers[0].text += " changed"
    model.question_coverage[0].source_answer_ids = ["wrong-answer"]
    report = _validate(rendering_fixture, model)
    codes = {item.code for item in report.findings}
    assert {"question_mutated", "answer_mutated", "wrong_answer_link"} <= codes
    assert report.status == "fail"


@pytest.mark.parametrize("mutation,expected", [
    ("duplicate_question", "duplicate_question_disposition"),
    ("duplicate_slide_id", "duplicate_slide_id"),
    ("duplicate_slide_number", "slide_numbers_invalid"),
])
def test_duplicate_records_block(rendering_fixture, mutation, expected) -> None:
    model = rendering_fixture["model"].model_copy(deep=True)
    if mutation == "duplicate_question":
        model.question_coverage.insert(1, model.question_coverage[0].model_copy())
    elif mutation == "duplicate_slide_id":
        model.slides[1].slide_id = model.slides[0].slide_id
    else:
        model.slides[1].slide_number = model.slides[0].slide_number
    assert expected in {item.code for item in _validate(rendering_fixture, model).findings}


def test_missing_question_and_required_coverage_block(rendering_fixture) -> None:
    model = rendering_fixture["model"].model_copy(deep=True)
    model.question_coverage.pop()
    model.assignment_coverage.pop(0)
    required_resource = next(
        item.resource_id for item in rendering_fixture["bundle"].required_assignments
    )
    model.resource_coverage = [
        item for item in model.resource_coverage
        if item.resource_id != required_resource
    ]
    codes = {item.code for item in _validate(rendering_fixture, model).findings}
    assert {
        "question_coverage_order_invalid",
        "required_assignment_omitted",
        "required_resource_omitted",
    } <= codes


def test_homework_does_not_leak_and_exact_labels_are_preserved(rendering_fixture) -> None:
    model = rendering_fixture["model"]
    homework_phase = rendering_fixture["plan"].instructional_phases[-1]
    homework_ids = set(homework_phase.homework_assignment_ids)
    assert homework_ids
    assert all(
        not (homework_ids & set(phase.assignment_ids))
        for phase in model.phases[:-1]
    )
    labels = {
        label for slide in model.slides
        for label in slide.activity_book_references
    }
    assert {"1.1", "1.3", "SR.1"} <= labels


def test_unknown_pages_assessment_and_activity_are_blocked(rendering_fixture) -> None:
    from schemas.lesson_rendering_model_schema import ReadingPageReference
    model = rendering_fixture["model"].model_copy(deep=True)
    model.slides[0].reading_pages.append(ReadingPageReference(
        reference_system="story_relative_page",
        value="999–1000",
        assignment_id="unsupported",
    ))
    model.slides[0].slide_type = SlideType.ASSESSMENT
    model.slides[0].activity_book_references.append("FAKE.1")
    model.slides[0].student_visible_content.statements.append(
        model.slides[0].student_visible_content.title.model_copy(update={
            "text": "“Unsupported quotation”",
            "origin": ContentOrigin.DETERMINISTIC_STRUCTURE,
        })
    )
    codes = {item.code for item in _validate(rendering_fixture, model).findings}
    assert {
        "unsupported_page", "unsupported_assessment",
        "unsupported_required_activity", "unsupported_quotation",
    } <= codes


def test_phase_reordering_and_ai_mislabeled_as_publisher_block(rendering_fixture) -> None:
    model = rendering_fixture["model"].model_copy(deep=True)
    model.phases[0], model.phases[1] = model.phases[1], model.phases[0]
    model.slides[0].student_visible_content.statements.append(
        model.slides[0].student_visible_content.title.model_copy(update={
            "text": "Generated coaching presented as curriculum.",
            "origin": ContentOrigin.PUBLISHER_SOURCE,
        })
    )
    codes = {item.code for item in _validate(rendering_fixture, model).findings}
    assert {"phase_order_changed", "unsupported_publisher_content"} <= codes


def test_ambiguous_boundaries_and_timing_conflict_remain_visible(rendering_fixture) -> None:
    model = rendering_fixture["model"]
    assert any(not item.reading_boundary for item in model.question_coverage)
    assert [item.code for item in model.timing_warnings] == [
        "explicit_timing_conflict"
    ]
    assert model.declared_duration_minutes == 90
    assert model.explicit_phase_duration_minutes == 95


def test_assignment_and_resource_coverage_complete(rendering_fixture) -> None:
    model = rendering_fixture["model"]
    required_assignments = {
        item.assignment_id for item in rendering_fixture["bundle"].required_assignments
    }
    required_resources = {
        item.resource_id for item in rendering_fixture["bundle"].required_assignments
    }
    assert required_assignments <= {
        item.assignment_id for item in model.assignment_coverage if item.covered
    }
    assert required_resources <= {
        item.resource_id for item in model.resource_coverage if item.covered
    }


def test_stable_ids_and_unrelated_insertion(rendering_fixture) -> None:
    first = rendering_fixture["model"]
    second = build_lesson_rendering_model(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        support_manifest=rendering_fixture["manifest"], support_drafts={},
    )
    assert first.artifact_digest == second.artifact_digest
    assert [item.slide_id for item in first.slides] == [
        item.slide_id for item in second.slides
    ]
    shifted = second.model_copy(deep=True)
    inserted = shifted.slides[0].model_copy(deep=True)
    inserted.slide_id = "unrelated-valid-id"
    shifted.slides.insert(1, inserted)
    assert [item.slide_id for item in shifted.slides if item.slide_id != "unrelated-valid-id"] == [
        item.slide_id for item in second.slides
    ]


def test_invalid_and_digest_mismatched_cache_is_rejected(rendering_fixture) -> None:
    output, result = _generate_support(rendering_fixture)
    draft_path = result.draft_json_path
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    payload["content_digest"] = "wrong"
    draft_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest, drafts = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={
            result.draft.phase_id: _expected_identity(result)
        },
    )
    assert result.draft.phase_id not in drafts
    assert manifest[5].status == SupportStatus.INVALID_REJECTED


def test_cache_resolution_ignores_modification_time(rendering_fixture) -> None:
    output, result = _generate_support(rendering_fixture)
    before = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={
            result.draft.phase_id: _expected_identity(result)
        },
    )[0][5].cache_key
    os.utime(result.output_directory, (1, 1))
    after = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={
            result.draft.phase_id: _expected_identity(result)
        },
    )[0][5].cache_key
    assert before == after == result.cache_key


def test_exact_identity_ignores_unrelated_valid_variants_and_lexical_order(
    rendering_fixture,
) -> None:
    output, first = _generate_support(
        rendering_fixture,
        generation_parameters={
            "max_context_characters": 1_000_000,
            "provider_parameters": {},
        },
    )
    _, second = _generate_support(
        rendering_fixture,
        generation_parameters={
            "max_context_characters": 1_000_000,
            "temperature": 0,
        },
    )
    desired = max((first, second), key=lambda value: value.cache_key)
    unrelated = min((first, second), key=lambda value: value.cache_key)
    manifest, drafts = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={
            desired.draft.phase_id: _expected_identity(desired)
        },
    )
    assert desired.cache_key != unrelated.cache_key
    assert manifest[5].cache_key == desired.cache_key
    assert drafts[desired.draft.phase_id].digest == desired.draft.digest


def test_missing_exact_identity_does_not_fall_back_to_other_variant(
    rendering_fixture,
) -> None:
    output, result = _generate_support(rendering_fixture)
    empty = rendering_fixture["root"] / "empty-support-cache"
    empty.mkdir()
    manifest, drafts = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=empty,
        expected_support_identities={
            result.draft.phase_id: _expected_identity(result)
        },
    )
    assert result.draft.phase_id not in drafts
    assert manifest[5].status == SupportStatus.OPTIONAL_UNAVAILABLE
    assert manifest[5].cache_key is None
    assert any("exact expected" in value for value in manifest[5].warnings)


def test_caller_identity_must_match_every_expected_field(rendering_fixture) -> None:
    output, result = _generate_support(rendering_fixture)
    identity = _expected_identity(result).model_copy(update={
        "provider": "different-provider"
    })
    manifest, drafts = resolve_phase_support(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        cache_directory=output,
        expected_support_identities={result.draft.phase_id: identity},
    )
    assert result.draft.phase_id not in drafts
    assert manifest[5].status == SupportStatus.INVALID_REJECTED


def test_service_writes_isolated_inspectable_artifacts(rendering_fixture) -> None:
    inputs = {}
    for name, value in (
        ("bundle_path", rendering_fixture["bundle"]),
        ("instruction_plan_path", rendering_fixture["plan"]),
        ("relationship_graph_path", rendering_fixture["graph"]),
        ("relationship_graph_audit_path", rendering_fixture["audit"]),
    ):
        path = rendering_fixture["root"] / f"service-{name}.json"
        path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
        inputs[name] = path
    target = rendering_fixture["root"] / "rendering-output"
    model, report, reused = LessonRenderingModelService().generate(
        **inputs, output_directory=target
    )
    assert not reused
    assert report.status == "pass_with_warnings"
    assert {
        "lesson_phase_support_manifest.json",
        "lesson_rendering_model.json",
        "lesson_rendering_model.md",
        "lesson_rendering_model_validation.json",
        "lesson_rendering_model_validation.md",
    } == {item.name for item in target.iterdir()}
    again, again_report, reused = LessonRenderingModelService().generate(
        **inputs, output_directory=target
    )
    assert reused
    assert again == model
    assert again_report.status == report.status


def test_inputs_remain_byte_identical_and_no_live_provider(rendering_fixture, monkeypatch) -> None:
    snapshots = {
        key: value.model_dump_json()
        for key, value in rendering_fixture.items()
        if key in {"bundle", "plan", "graph", "audit"}
    }
    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Live provider must not be called")
        ),
    )
    build_lesson_rendering_model(
        rendering_fixture["bundle"], rendering_fixture["plan"],
        rendering_fixture["graph"], rendering_fixture["audit"],
        support_manifest=rendering_fixture["manifest"], support_drafts={},
    )
    assert snapshots == {
        key: rendering_fixture[key].model_dump_json() for key in snapshots
    }


def test_production_gamma_and_google_paths_do_not_import_new_model() -> None:
    root = Path(__file__).parents[1]
    for path in (
        root / "app" / "teacheros.py",
        root / "renderer" / "google_slides_renderer.py",
        root / "renderer" / "gamma_prompt.py",
    ):
        if path.exists():
            assert "lesson_rendering_model" not in path.read_text(encoding="utf-8")
