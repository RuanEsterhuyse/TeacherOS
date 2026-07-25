"""Offline tests for Phase 4B grounded instructional intelligence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import get_settings
from curriculum.intelligence.grounded_instructional_intelligence import (
    GroundedInstructionalIntelligenceService,
    PhaseTeacherSupportContextBuilder,
    validate_phase_teacher_support,
)
from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.instruction_plan import (
    SourceGroundedInstructionPlanBuilder,
)
from curriculum.intelligence.instructional_intelligence_provider import (
    InstructionalIntelligenceProvider,
    InstructionalIntelligenceProviderResponse,
)
from curriculum.intelligence.relationship_graph import (
    InstructionalRelationshipGraphBuilder,
    _audit_digest,
    _graph_digest,
)
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    ValidationFinding,
)
from schemas.phase_teacher_support_schema import (
    GeneratedPhaseTeacherSupport,
    GeneratedTeacherSupportItem,
    TeacherSupportGenerationStatus,
    TeacherSupportOrigin,
    TeacherSupportReviewStatus,
    TeacherSupportType,
)
from Tests.test_source_grounded_instruction_plan import instruction_bundle


def _with_digest(bundle):
    return bundle.model_copy(update={
        "bundle_digest": content_digest(
            bundle.model_dump(mode="json", exclude={"bundle_digest"})
        )
    })


def intelligence_bundle(tmp_path: Path):
    bundle = instruction_bundle(tmp_path)
    assignments = list(bundle.required_assignments)
    index = next(
        index
        for index, value in enumerate(assignments)
        if value.assignment_type == "defines_lesson"
    )
    assignment = assignments[index]
    segment = assignment.source_segments[0]
    start = segment.exact_text.index("Read the Story 30 minutes")
    end = segment.exact_text.index(
        "Discuss the Story and Wrap Up the Lesson 10 minutes"
    )
    guided_reading = ["Read the Story 30 minutes", ""]
    for number in range(1, 33):
        guided_reading.extend([
            f"Literal Question {number}: What does detail {number} reveal?",
            "",
            f"oo Source-provided answer {number}.",
            "",
        ])
    exact_text = (
        segment.exact_text[:start]
        + "\n".join(guided_reading)
        + "\n"
        + segment.exact_text[end:]
    )
    assignments[index] = assignment.model_copy(update={
        "source_segments": [
            segment.model_copy(update={"exact_text": exact_text})
        ]
    })
    return _with_digest(bundle.model_copy(
        update={"required_assignments": assignments}
    ))


@pytest.fixture
def intelligence_fixture(tmp_path: Path):
    bundle = intelligence_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    graph, audit = InstructionalRelationshipGraphBuilder().build(
        bundle, plan
    )
    phase = plan.instructional_phases[5]
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    paths = {
        "bundle_path": inputs / "prepared_source_bundle.json",
        "instruction_plan_path":
            inputs / "source_grounded_instruction_plan.json",
        "relationship_graph_path":
            inputs / "instructional_relationship_graph.json",
        "relationship_graph_audit_path":
            inputs / "instructional_relationship_graph_audit.json",
    }
    paths["bundle_path"].write_text(
        bundle.model_dump_json(indent=2), encoding="utf-8"
    )
    paths["instruction_plan_path"].write_text(
        plan.model_dump_json(indent=2), encoding="utf-8"
    )
    paths["relationship_graph_path"].write_text(
        graph.model_dump_json(indent=2), encoding="utf-8"
    )
    paths["relationship_graph_audit_path"].write_text(
        audit.model_dump_json(indent=2), encoding="utf-8"
    )
    return {
        "root": tmp_path,
        "bundle": bundle,
        "plan": plan,
        "graph": graph,
        "audit": audit,
        "phase": phase,
        "paths": paths,
    }


def valid_payload(context):
    question_id = context.questions[0].node_id
    reading_id = context.readings[0].node_id
    resource_id = context.resources[0].node_id
    segment_id = context.source_segments[0].node_id
    content = {
        TeacherSupportType.TEACHER_EXPLANATION:
            "Use the verified question sequence to help students move from "
            "noticing details to explaining what those details reveal.",
        TeacherSupportType.ANTICIPATED_MISCONCEPTIONS:
            "Likely misunderstanding: a student may offer an unsupported "
            "claim. Cause: recalling the event without rereading. Signal: no "
            "detail is cited. Teacher response: ask the student to locate the "
            "linked passage and connect one detail to the claim.",
        TeacherSupportType.FACILITATION_NOTES:
            "Preserve the verified question order. Invite a response, request "
            "linked textual support, and use the supplied answer only to "
            "clarify after students have explained their evidence.",
        TeacherSupportType.CHECKS_FOR_UNDERSTANDING:
            "Optional oral check: ask partners to name one verified detail "
            "and explain how it supports their response before sharing.",
        TeacherSupportType.LANGUAGE_SUPPORTS:
            "Language support for multilingual learners: offer the response "
            "stem “The detail ___ supports my idea because ___,” followed by "
            "partner rehearsal before whole-group discussion.",
        TeacherSupportType.DIFFERENTIATION_SUPPORTS:
            "Optional_support: let students reread the linked source segment "
            "and mark one detail before responding. Optional_extension: ask "
            "students to connect two verified details using the same question.",
    }
    return GeneratedPhaseTeacherSupport(
        phase_id=context.phase_id,
        source_context_digest=context.context_digest,
        support_sections=[
            GeneratedTeacherSupportItem(
                support_type=support_type,
                title=support_type.value.replace("_", " ").title(),
                content=content[support_type],
                intended_use="Optional support during the selected phase.",
                linked_phase_ids=[context.phase_node_id],
                linked_question_ids=[question_id],
                linked_reading_ids=[reading_id],
                linked_resource_ids=[resource_id],
                linked_source_segment_ids=[segment_id],
                evidence_summary=(
                    "Linked to the selected phase, verified question, reading, "
                    "resource, and source segment."
                ),
                origin=TeacherSupportOrigin.AI_GENERATED,
                review_status=TeacherSupportReviewStatus.DRAFT_UNREVIEWED,
            )
            for support_type in TeacherSupportType
        ],
    ).model_dump(mode="json")


class FakeProvider:
    provider_name = "fake"
    model_name = "deterministic-fixture-v1"

    def __init__(self, transform=None, error: Exception | None = None):
        self.transform = transform
        self.error = error
        self.calls = 0

    def generate_phase_teacher_support(self, context, prompt_contract):
        self.calls += 1
        if self.error:
            raise self.error
        payload = valid_payload(context)
        if self.transform:
            payload = self.transform(payload, context)
        return InstructionalIntelligenceProviderResponse(
            raw_payload=payload,
            usage={"fixture_tokens": 1},
        )


def generate(fixture, provider, output, *, prompt_version="1.0"):
    return GroundedInstructionalIntelligenceService(
        provider,
        prompt_version=prompt_version,
    ).generate(
        **fixture["paths"],
        phase_id=fixture["phase"].id,
        output_directory=output,
    )


def test_provider_abstraction_and_no_live_api(
    intelligence_fixture,
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Live OpenAI client must not be constructed")

    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__",
        forbidden,
    )
    provider = FakeProvider()
    result = generate(
        intelligence_fixture,
        provider,
        intelligence_fixture["root"] / "support",
    )

    assert isinstance(provider, InstructionalIntelligenceProvider)
    assert provider.calls == 1
    assert result.status == TeacherSupportGenerationStatus.GENERATED_VALID
    assert result.validation.status == "pass"


def test_context_is_deterministic_and_phase_only(
    intelligence_fixture,
) -> None:
    fixture = intelligence_fixture
    builder = PhaseTeacherSupportContextBuilder()
    first = builder.build(
        fixture["bundle"],
        fixture["plan"],
        fixture["graph"],
        fixture["audit"],
        phase_id=fixture["phase"].id,
    )
    second = builder.build(
        fixture["bundle"],
        fixture["plan"],
        fixture["graph"],
        fixture["audit"],
        phase_id=fixture["phase"].id,
    )
    payload = first.model_dump_json()

    assert first == second
    assert first.context_digest == second.context_digest
    assert first.phase_sequence == 6
    assert first.phase_title == "Read the Story"
    assert len(first.questions) == 32
    assert sum(len(value.source_answers) for value in first.questions) == 32
    assert all("Question " in value.question_text for value in first.questions)
    assert "Güera" not in payload
    assert "Take-Home Material" not in payload
    assert "generated_instructional_guidance" not in payload
    assert len(first.objectives) == 0
    assert any(
        "objective links" in value
        for value in first.excluded_relationships
    )


def test_valid_draft_has_six_sections_and_exact_linkage(
    intelligence_fixture,
) -> None:
    result = generate(
        intelligence_fixture,
        FakeProvider(),
        intelligence_fixture["root"] / "valid",
    )
    draft = result.draft

    assert draft is not None
    assert {value.support_type for value in draft.support_sections} == set(
        TeacherSupportType
    )
    assert all(
        value.origin == TeacherSupportOrigin.AI_GENERATED
        and value.review_status
        == TeacherSupportReviewStatus.DRAFT_UNREVIEWED
        for value in draft.support_sections
    )
    assert draft.provider == "fake"
    assert draft.model == "deterministic-fixture-v1"
    assert draft.prompt_version == "1.0"
    assert draft.review_status == TeacherSupportReviewStatus.DRAFT_UNREVIEWED
    assert draft.content_origin == TeacherSupportOrigin.AI_GENERATED


@pytest.mark.parametrize(
    ("transform", "expected_status", "expected_code"),
    [
        (
            lambda payload, context: {
                **payload,
                "support_sections": [
                    {
                        **value,
                        "linked_question_ids": ["unknown-question-node"],
                    }
                    for value in payload["support_sections"]
                ],
            },
            TeacherSupportGenerationStatus.VALIDATION_BLOCKED,
            "linked_id_invalid",
        ),
        (
            lambda payload, context: {
                **payload,
                "support_sections": payload["support_sections"][:-1],
            },
            TeacherSupportGenerationStatus.VALIDATION_BLOCKED,
            "required_sections_invalid",
        ),
        (
            lambda payload, context: {
                **payload,
                "support_sections": [
                    {
                        **value,
                        "content": value["content"]
                        + " Add a pause for 4 minutes.",
                    }
                    for value in payload["support_sections"]
                ],
            },
            TeacherSupportGenerationStatus.VALIDATION_BLOCKED,
            "generated_timing_change",
        ),
        (
            lambda payload, context: {
                **payload,
                "support_sections": [
                    {
                        **value,
                        "content": (
                            "The publisher requires this additional task. "
                            + value["content"]
                        ),
                    }
                    for value in payload["support_sections"]
                ],
            },
            TeacherSupportGenerationStatus.VALIDATION_BLOCKED,
            "publisher_content_impersonation",
        ),
    ],
)
def test_validation_blocks_invalid_generated_support(
    intelligence_fixture,
    transform,
    expected_status,
    expected_code,
) -> None:
    result = generate(
        intelligence_fixture,
        FakeProvider(transform),
        intelligence_fixture["root"] / expected_code,
    )

    assert result.status == expected_status
    assert result.validation.status == "fail"
    assert any(
        value.code == expected_code
        for value in result.validation.findings
    )


def test_unsupported_section_origin_and_review_status_are_rejected(
    intelligence_fixture,
) -> None:
    def unsupported(payload, context):
        payload["support_sections"][0]["support_type"] = "exit_ticket"
        return payload

    result = generate(
        intelligence_fixture,
        FakeProvider(unsupported),
        intelligence_fixture["root"] / "unsupported",
    )
    assert result.status == TeacherSupportGenerationStatus.RESPONSE_INVALID

    def wrong_origin(payload, context):
        payload["support_sections"][0]["origin"] = "publisher_authored"
        return payload

    origin = generate(
        intelligence_fixture,
        FakeProvider(wrong_origin),
        intelligence_fixture["root"] / "origin",
    )
    assert origin.status == TeacherSupportGenerationStatus.RESPONSE_INVALID

    def wrong_review(payload, context):
        payload["support_sections"][0]["review_status"] = "approved"
        return payload

    review = generate(
        intelligence_fixture,
        FakeProvider(wrong_review),
        intelligence_fixture["root"] / "review",
    )
    assert review.status == TeacherSupportGenerationStatus.RESPONSE_INVALID


def test_stable_content_digest_and_cache_hit(
    intelligence_fixture,
) -> None:
    provider = FakeProvider()
    output = intelligence_fixture["root"] / "cache"
    first = generate(intelligence_fixture, provider, output)
    second = generate(intelligence_fixture, provider, output)

    assert first.draft is not None and second.draft is not None
    assert provider.calls == 1
    assert second.reused is True
    assert second.status == TeacherSupportGenerationStatus.CACHE_HIT_VALID
    assert first.draft.content_digest == second.draft.content_digest
    assert first.draft.digest == second.draft.digest


def test_cache_invalidates_for_prompt_or_graph_change(
    intelligence_fixture,
) -> None:
    fixture = intelligence_fixture
    provider = FakeProvider()
    output = fixture["root"] / "cache-invalidation"
    first = generate(fixture, provider, output)
    prompt_changed = generate(
        fixture, provider, output, prompt_version="1.1"
    )

    graph = fixture["graph"].model_copy(update={
        "warnings": [
            *fixture["graph"].warnings,
            ValidationFinding(
                code="test_graph_revision",
                severity=FindingSeverity.WARNING,
                message="Deterministic test graph revision.",
                reference_id=fixture["graph"].lesson_id,
            ),
        ],
        "graph_digest": "pending",
    })
    graph = graph.model_copy(update={"graph_digest": _graph_digest(graph)})
    audit = fixture["audit"].model_copy(update={
        "graph_digest": graph.graph_digest,
        "warnings": graph.warnings,
        "audit_digest": "pending",
    })
    audit = audit.model_copy(update={"audit_digest": _audit_digest(audit)})
    fixture["paths"]["relationship_graph_path"].write_text(
        graph.model_dump_json(indent=2), encoding="utf-8"
    )
    fixture["paths"]["relationship_graph_audit_path"].write_text(
        audit.model_dump_json(indent=2), encoding="utf-8"
    )
    graph_changed = generate(fixture, provider, output)

    assert provider.calls == 3
    assert len({
        first.cache_key,
        prompt_changed.cache_key,
        graph_changed.cache_key,
    }) == 3


def test_malformed_response_and_provider_failure(
    intelligence_fixture,
) -> None:
    malformed = FakeProvider(lambda payload, context: "{not-json")
    malformed_result = generate(
        intelligence_fixture,
        malformed,
        intelligence_fixture["root"] / "malformed",
    )
    assert (
        malformed_result.status
        == TeacherSupportGenerationStatus.RESPONSE_INVALID
    )

    failed = FakeProvider(error=RuntimeError("fixture provider failure"))
    failed_result = generate(
        intelligence_fixture,
        failed,
        intelligence_fixture["root"] / "provider-failure",
    )
    assert (
        failed_result.status
        == TeacherSupportGenerationStatus.PROVIDER_ERROR
    )
    assert failed_result.draft is None


def test_missing_configuration_is_explicit(
    intelligence_fixture,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    result = GroundedInstructionalIntelligenceService().generate(
        **intelligence_fixture["paths"],
        phase_id=intelligence_fixture["phase"].id,
        output_directory=intelligence_fixture["root"] / "no-provider",
    )
    get_settings.cache_clear()

    assert (
        result.status
        == TeacherSupportGenerationStatus.PROVIDER_UNAVAILABLE
    )
    assert result.draft is None
    assert result.validation.status == "fail"


def test_inputs_are_read_only_and_artifacts_are_isolated(
    intelligence_fixture,
) -> None:
    before = {
        key: value.read_bytes()
        for key, value in intelligence_fixture["paths"].items()
    }
    result = generate(
        intelligence_fixture,
        FakeProvider(),
        intelligence_fixture["root"] / "read-only",
    )

    assert before == {
        key: value.read_bytes()
        for key, value in intelligence_fixture["paths"].items()
    }
    assert result.output_directory.name == result.cache_key
    assert {value.name for value in result.output_directory.iterdir()} == {
        "phase_teacher_support_context.json",
        "phase_teacher_support_prompt.md",
        "phase_teacher_support_raw_response.json",
        "phase_teacher_support_draft.json",
        "phase_teacher_support_draft.md",
        "phase_teacher_support_validation.json",
        "phase_teacher_support_validation.md",
    }
    assert not (result.output_directory / "lesson.json").exists()
    assert not (result.output_directory / "slides.json").exists()
    ignore = (
        Path(__file__).resolve().parents[1] / ".gitignore"
    ).read_text(encoding="utf-8")
    assert "output/" in ignore


def test_direct_validator_detects_tampering(
    intelligence_fixture,
) -> None:
    result = generate(
        intelligence_fixture,
        FakeProvider(),
        intelligence_fixture["root"] / "tamper",
    )
    assert result.draft is not None
    tampered = result.draft.model_copy(update={"digest": "tampered"})
    report = validate_phase_teacher_support(
        tampered,
        result.context,
        intelligence_fixture["graph"],
        prompt_version="1.0",
        provider="fake",
        model="deterministic-fixture-v1",
    )

    assert report.status == "fail"
    assert any(
        value.code == "draft_digest_invalid"
        for value in report.findings
    )
