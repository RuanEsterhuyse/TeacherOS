"""Phase 3C source-grounded playbook enrichment tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from curriculum.intelligence.pasted_lesson_analyzer import analyze_pasted_lesson
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
    create_pasted_lesson_source,
)
from curriculum.intelligence.playbook_enrichment import (
    enrich_teacher_playbook,
)
from curriculum.intelligence.playbook_enrichment_provider import (
    PlaybookEnrichmentProviderResponse,
)
from schemas.playbook_enrichment_schema import (
    ApprovedPlaybookEnrichment,
    EnrichmentStatus,
    GENERATED_GUIDANCE_LABEL,
    PlaybookEnrichmentOptions,
    TeacherApprovalStatus,
)
from schemas.pasted_lesson_schema import utc_now


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "pasted_lesson_ckla_g8_u1_l1_sanitized.txt"
)


def _source():
    return create_pasted_lesson_source(
        grade="8",
        unit="1",
        lesson_number=1,
        lesson_title="Synthetic Identity Lesson",
        teacher_guide_page_start=12,
        teacher_guide_page_end=18,
        teacher_guide_text=FIXTURE.read_text(encoding="utf-8"),
        student_reader_text="Synthetic reader pages 3–6.",
        activity_book_text="Activity Page 1.2: Evidence chart.",
    )


class FakeProvider:
    provider_name = "fake"
    model_name = "deterministic-test-model"

    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls = 0

    def enrich(self, context, prompt_contract):
        self.calls += 1
        assert context.source.teacher_guide_text
        assert context.baseline.warnings is not None
        assert "Never invent" in prompt_contract
        if self.error:
            raise self.error
        return PlaybookEnrichmentProviderResponse(
            raw_payload=self.payload,
            usage={"input_tokens": 10},
        )


def _valid_payload(source):
    baseline = analyze_pasted_lesson(source)
    playbook = deepcopy(baseline.playbook.model_dump(mode="json"))
    playbook["teacher_survival_guide"].append(
        "Preview the evidence routine before class."
    )
    playbook["activities"][0]["teacher_script"].append(
        "Invite students to name one observable detail."
    )
    return {
        "enriched_playbook": playbook,
        "source_backed_fields": ["objectives", "activities.0.title"],
        "inferred_fields": [
            "teacher_survival_guide.0",
            "activities.0.teacher_script.1",
        ],
        "omitted_unsupported_fields": [],
    }


def test_enrichment_interface_is_grounded_labeled_and_deterministic():
    source = _source()
    baseline = analyze_pasted_lesson(source)
    provider = FakeProvider(_valid_payload(source))

    first = enrich_teacher_playbook(source, baseline, provider=provider)
    second = enrich_teacher_playbook(
        source, baseline, PlaybookEnrichmentOptions(), provider=provider
    )

    assert first.status == EnrichmentStatus.success
    assert first.enrichment_id == second.enrichment_id
    assert first.enriched_playbook.objectives == baseline.playbook.objectives
    assert first.enriched_playbook.activities[0].source_references == (
        baseline.playbook.activities[0].source_references
    )
    assert first.enriched_playbook.teacher_survival_guide[0].startswith(
        GENERATED_GUIDANCE_LABEL
    )
    assert first.provider_metadata.provider_name == "fake"
    assert all(value.fully_retained for value in first.source_coverage)


@pytest.mark.parametrize(
    "mutation, expected_path",
    [
        (lambda value: value["objectives"].append("Invented objective"), "objectives"),
        (
            lambda value: value["activities"][0]["source_references"].append({
                "source_type": "teacher_guide",
                "page_start": 99,
                "page_end": 99,
                "section": None,
                "activity_reference": None,
            }),
            "activities.0.source_references",
        ),
        (
                lambda value: value["activities"][0]["teacher_script"].append(
                    "Turn to page 99."
                ),
            "activities.0.teacher_script.2",
        ),
    ],
)
def test_strict_grounding_rejects_mutation_and_invented_pages(
    mutation, expected_path
):
    source = _source()
    baseline = analyze_pasted_lesson(source)
    payload = _valid_payload(source)
    mutation(payload["enriched_playbook"])

    result = enrich_teacher_playbook(
        source, baseline, provider=FakeProvider(payload)
    )

    assert result.status == EnrichmentStatus.failed
    assert result.baseline_preserved is True
    assert result.enriched_playbook == baseline.playbook
    assert any(
        claim.field_path == expected_path
        for claim in result.unsupported_claims
    )


@pytest.mark.parametrize(
    "payload,error,code",
    [
        ({"wrong": True}, None, "enrichment_failed"),
        (None, TimeoutError("timed out"), "provider_timeout"),
        (None, ValueError("OPENAI_API_KEY is required"), "enrichment_failed"),
        ({}, None, "enrichment_failed"),
    ],
)
def test_provider_failures_fall_back_to_baseline(payload, error, code):
    source = _source()
    baseline = analyze_pasted_lesson(source)

    result = enrich_teacher_playbook(
        source, baseline, provider=FakeProvider(payload, error)
    )

    assert result.status == EnrichmentStatus.failed
    assert result.enriched_playbook == baseline.playbook
    assert result.baseline_preserved
    assert result.warnings[0].code == code


def test_partial_response_records_omitted_unsupported_fields():
    source = _source()
    baseline = analyze_pasted_lesson(source)
    payload = _valid_payload(source)
    payload["omitted_unsupported_fields"] = ["activities.0.answer_key"]

    result = enrich_teacher_playbook(
        source, baseline, provider=FakeProvider(payload)
    )

    assert result.status == EnrichmentStatus.partial
    assert result.grounding_report.omitted_unsupported_fields == [
        "activities.0.answer_key"
    ]


def test_repository_requires_approval_and_round_trips(tmp_path):
    source = _source()
    repository = PastedLessonRepository(tmp_path / "runtime")
    repository.save_source(source)
    baseline = analyze_pasted_lesson(source)
    result = enrich_teacher_playbook(
        source, baseline, provider=FakeProvider(_valid_payload(source))
    )
    pending = ApprovedPlaybookEnrichment(
        enrichment_id=result.enrichment_id,
        source_id=source.source_id,
        baseline_analyzer_version=baseline.analyzer_version,
        enriched_playbook=result.enriched_playbook,
        provider_metadata=result.provider_metadata,
        grounding_summary=result.grounding_report,
        teacher_approval_status=TeacherApprovalStatus.pending,
    )
    with pytest.raises(ValueError, match="teacher-approved"):
        repository.save_approved_enrichment(pending)

    approved = pending.model_copy(update={
        "teacher_approval_status": TeacherApprovalStatus.approved,
        "approved_at": utc_now(),
    })
    repository.save_approved_enrichment(approved)
    assert repository.load_approved_enrichment(
        approved.enrichment_id
    ) == approved
    assert repository.list_approved_enrichments() == [approved]


def test_baseline_analyzer_remains_unchanged_after_enrichment():
    source = _source()
    before = analyze_pasted_lesson(source)
    enrich_teacher_playbook(
        source, before, provider=FakeProvider(_valid_payload(source))
    )
    assert analyze_pasted_lesson(source) == before
