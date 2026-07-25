"""Offline tests for the Phase 3B source-grounded instruction plan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from curriculum.intelligence.canonical_bridge import BundleCanonicalBridge
from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.instruction_plan import (
    InstructionPlanService,
    SourceGroundedInstructionPlanBuilder,
    compare_instruction_plan,
    validate_instruction_plan,
)
from schemas.source_grounded_instruction_schema import (
    SourceFindingCategory,
    SourceGroundedInstructionPlan,
)
from schemas.curriculum_intelligence_schema import ReadinessState
from Tests.test_prepared_curriculum_source_bundle import prepared


TEACHER_GUIDE_TEXT = """Lesson 1

AT A GLANCE CHART

Materials: Book, Activity Pages
Objective: Analyze theme.

DAY 1:
45 min

DAY 2:
45 min

ADVANCE PREPARATION

• Display a map and the Lesson 1 Online Resources.

DAY 1

CORE CONNECTIONS 45 minutes

Introduce the Themes and Methods 25 minutes

• Tell students to consider identity.

Introduce the Book 15 minutes

• Ensure each student has the assigned text.

Wrap Up 5 minutes

• Think-Pair-Share Have students share one observation.

DAY 2

READING 45 minutes

Read-Aloud: “The Attack” [pages 1–15]

Introduce the Story 10 minutes

• Have students reference Activity Page 1.2 and Student Resource SR.1.

Read the Story 30 minutes

Inferential\u2002 What does the evidence reveal?

oo The evidence reveals the character’s concern.

Evaluative\u2002 Explain how the theme develops throughout the story.

oo The theme develops through the character’s choices.

Turn and Talk Have student pairs discuss the event. Did the response seem fair?

oo Answers will vary based on cited evidence.

Discuss the Story and Wrap Up the Lesson 10 minutes

Then use the following questions to lead a discussion: How did identity affect the event?
Did one factor matter more? Has anyone observed a similar situation?

• Have students partner up to discuss the question.

Take-Home Material

Core Connections
• Distribute Activity Page 1.1.
Reading
• Have students take home Student Resource SR.1.

• Assign “Güera” (pages 51–57) as homework and complete Activity Page 1.3.
"""


def _with_digest(bundle):
    return bundle.model_copy(update={
        "bundle_digest": content_digest(
            bundle.model_dump(mode="json", exclude={"bundle_digest"})
        )
    })


def instruction_bundle(tmp_path: Path):
    _, _, _, result = prepared(tmp_path)
    bundle = result.bundle
    assignments = list(bundle.required_assignments)
    index = next(
        index
        for index, value in enumerate(assignments)
        if value.assignment_type == "defines_lesson"
    )
    teacher_assignment = assignments[index]
    segment = teacher_assignment.source_segments[0].model_copy(
        update={"exact_text": TEACHER_GUIDE_TEXT}
    )
    assignments[index] = teacher_assignment.model_copy(
        update={"source_segments": [segment]}
    )
    return _with_digest(bundle.model_copy(
        update={"required_assignments": assignments}
    ))


def test_schema_is_curriculum_agnostic() -> None:
    schema = json.dumps(SourceGroundedInstructionPlan.model_json_schema())
    assert "CKLA" not in schema
    assert "ckla" not in schema.casefold()


def test_zero_ai_and_deterministic_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("AI client must not be constructed")

    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__",
        forbidden,
    )
    bundle = instruction_bundle(tmp_path)
    first = SourceGroundedInstructionPlanBuilder().build(bundle)
    second = SourceGroundedInstructionPlanBuilder().build(bundle)

    assert first == second
    assert first.digest == second.digest
    assert [value.id for value in first.instructional_phases] == [
        value.id for value in second.instructional_phases
    ]


def test_exact_phase_order_and_explicit_timing(tmp_path: Path) -> None:
    plan = SourceGroundedInstructionPlanBuilder().build(
        instruction_bundle(tmp_path)
    )

    assert [value.phase_title for value in plan.instructional_phases] == [
        "Advance Preparation",
        "Introduce the Themes and Methods",
        "Introduce the Book",
        "Wrap Up",
        "Introduce the Story",
        "Read the Story",
        "Discuss the Story and Wrap Up the Lesson",
        "Take-Home Material",
    ]
    assert [
        value.duration_minutes for value in plan.instructional_phases
    ] == [None, 25, 15, 5, 10, 30, 10, None]
    assert plan.total_duration_minutes == 90
    assert [value.code for value in plan.warnings] == [
        "explicit_timing_conflict"
    ]


def test_questions_answers_and_provenance_are_exact(tmp_path: Path) -> None:
    bundle = instruction_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    questions = [
        value
        for phase in plan.instructional_phases
        for value in phase.questions
    ]

    assert [value.question_text for value in questions[:3]] == [
        "What does the evidence reveal?",
        "Explain how the theme develops throughout the story.",
        "Did the response seem fair?",
    ]
    assert [value.answers[0].exact_text for value in questions[:3]] == [
        "The evidence reveals the character’s concern.",
        "The theme develops through the character’s choices.",
        "Answers will vary based on cited evidence.",
    ]
    assert len(questions) == 6
    assert all(not value.answers for value in questions[-3:])
    for question in questions:
        provenance = question.provenance[0]
        assert provenance.assignment_id
        assert provenance.resource_id
        assert provenance.segment_ids
        assert provenance.bundle_digest == bundle.bundle_digest
        assert provenance.resource_checksum


def test_activity_student_online_and_reading_roles(tmp_path: Path) -> None:
    bundle = instruction_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    by_type = {
        value.assignment_type: value.assignment_id
        for value in bundle.required_assignments
    }
    all_references = {
        value
        for phase in plan.instructional_phases
        for value in phase.referenced_assignment_ids
    }

    assert len(plan.activity_sequence) >= 2
    assert by_type["assigned_reading"] in all_references
    assert by_type["assigned_reading"] in (
        plan.reading_sequence[-1].assignment_ids
    )
    homework_ids = {
        value
        for item in plan.homework_sequence
        for value in item.assignment_ids
    }
    assert by_type["homework"] in homework_ids
    assert by_type["assigned_reading"] not in homework_ids
    assert any(
        "online" in assignment.title.casefold()
        and assignment.assignment_id in all_references
        for assignment in bundle.required_assignments
    )
    assert any(
        "student resource" in assignment.title.casefold()
        and assignment.assignment_id in all_references
        for assignment in bundle.required_assignments
    )


def test_only_permitted_source_categories_enter_plan(tmp_path: Path) -> None:
    plan = SourceGroundedInstructionPlanBuilder().build(
        instruction_bundle(tmp_path)
    )
    permitted = {
        SourceFindingCategory.EXPLICIT_SOURCE_INSTRUCTION,
        SourceFindingCategory.EXPLICIT_SOURCE_QUESTION,
        SourceFindingCategory.EXPLICIT_SOURCE_OBJECTIVE,
        SourceFindingCategory.EXPLICIT_SOURCE_TIMING,
        SourceFindingCategory.DETERMINISTIC_STRUCTURE,
    }

    assert all(
        value.category in permitted
        for value in plan.audit_findings
        if value.included_in_plan
    )
    assert all(
        value.category != SourceFindingCategory.LEGACY_GENERATED
        for value in plan.audit_findings
        if value.included_in_plan
    )


def test_validation_rejects_digest_tampering_and_non_ready_bundle(
    tmp_path: Path,
) -> None:
    bundle = instruction_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    tampered = plan.model_copy(update={"digest": "tampered"})
    findings = validate_instruction_plan(tampered, bundle)
    assert any(value.code == "plan_digest_invalid" for value in findings)

    partial = _with_digest(bundle.model_copy(
        update={"readiness_state": ReadinessState.PARTIALLY_READY}
    ))
    with pytest.raises(ValueError, match="source_ready"):
        SourceGroundedInstructionPlanBuilder().build(partial)


def test_comparison_is_deterministic_and_labels_generated_content(
    tmp_path: Path,
) -> None:
    bundle = instruction_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    current = BundleCanonicalBridge().build(bundle).model_dump(mode="json")
    current["lesson_blocks"][0]["teacher_guidance"]["introduction"] = {
        "text": "Legacy generated guidance.",
        "availability": "available",
        "origin": "generated_instructional_guidance",
    }
    first = compare_instruction_plan(plan, current)
    second = compare_instruction_plan(plan, current)

    assert first == second
    assert first.not_reproducible_current_paths
    legacy = next(
        value
        for value in first.comparisons
        if value.field == "legacy_generated_content"
    )
    assert legacy.notes == [
        "Not reproducible from verified curriculum sources.",
        "This does not assert that the generated content is incorrect.",
    ]


def test_service_writes_only_parallel_artifacts_and_preserves_current(
    tmp_path: Path,
) -> None:
    bundle = instruction_bundle(tmp_path)
    current = BundleCanonicalBridge().build(bundle)
    bundle_path = tmp_path / "prepared_source_bundle.json"
    current_path = tmp_path / "lesson.json"
    output = tmp_path / "instruction-plan"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    current_path.write_text(
        current.model_dump_json(indent=2), encoding="utf-8"
    )
    before = current_path.read_bytes()

    first = InstructionPlanService().build(
        bundle_path=bundle_path,
        current_canonical_path=current_path,
        output_directory=output,
    )
    first_bytes = {
        value.name: value.read_bytes()
        for value in (
            first.plan_json_path,
            first.plan_markdown_path,
            first.comparison_json_path,
            first.comparison_markdown_path,
        )
    }
    second = InstructionPlanService().build(
        bundle_path=bundle_path,
        current_canonical_path=current_path,
        output_directory=output,
    )

    assert current_path.read_bytes() == before
    assert first.plan == second.plan
    assert first.comparison == second.comparison
    assert first_bytes == {
        value.name: value.read_bytes()
        for value in (
            second.plan_json_path,
            second.plan_markdown_path,
            second.comparison_json_path,
            second.comparison_markdown_path,
        )
    }
    assert {value.name for value in output.iterdir()} == {
        "source_grounded_instruction_plan.json",
        "source_grounded_instruction_plan.md",
        "instruction_plan_comparison.json",
        "instruction_plan_comparison.md",
    }
