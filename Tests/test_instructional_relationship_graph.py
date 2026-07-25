"""Offline tests for the Phase 4A instructional relationship graph."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from curriculum.intelligence.instruction_plan import (
    SourceGroundedInstructionPlanBuilder,
)
from curriculum.intelligence.relationship_graph import (
    InstructionalRelationshipGraphBuilder,
    InstructionalRelationshipGraphService,
    relationship_graph_markdown,
    validate_relationship_graph,
)
from schemas.instructional_relationship_graph_schema import (
    GraphNodeType,
    GraphRelationshipType,
    InstructionalRelationshipGraph,
    RelationshipBasis,
)
from Tests.test_source_grounded_instruction_plan import instruction_bundle


@pytest.fixture(scope="module")
def graph_fixture(tmp_path_factory):
    root = tmp_path_factory.mktemp("relationship-graph")
    bundle = instruction_bundle(root)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    graph, audit = InstructionalRelationshipGraphBuilder().build(
        bundle, plan
    )
    return root, bundle, plan, graph, audit


def test_graph_schema_is_curriculum_agnostic() -> None:
    schema = json.dumps(InstructionalRelationshipGraph.model_json_schema())
    assert "CKLA" not in schema
    assert "ckla" not in schema.casefold()


def test_zero_ai_and_deterministic_ids_and_digest(
    graph_fixture,
    monkeypatch,
) -> None:
    _, bundle, plan, first, first_audit = graph_fixture

    def forbidden(*args, **kwargs):
        raise AssertionError("AI client must not be constructed")

    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__",
        forbidden,
    )
    second, second_audit = InstructionalRelationshipGraphBuilder().build(
        bundle, plan
    )

    assert first == second
    assert first_audit == second_audit
    assert first.graph_digest == second.graph_digest
    assert [value.node_id for value in first.nodes] == [
        value.node_id for value in second.nodes
    ]
    assert [value.edge_id for value in first.edges] == [
        value.edge_id for value in second.edges
    ]


def test_unique_ids_and_valid_endpoints(graph_fixture) -> None:
    _, _, _, graph, _ = graph_fixture
    node_ids = [value.node_id for value in graph.nodes]
    edge_ids = [value.edge_id for value in graph.edges]

    assert len(node_ids) == len(set(node_ids))
    assert len(edge_ids) == len(set(edge_ids))
    assert all(
        value.source_node_id in node_ids
        and value.target_node_id in node_ids
        for value in graph.edges
    )
    assert all(
        value.relationship_basis in {
            RelationshipBasis.EXPLICIT_SOURCE,
            RelationshipBasis.DETERMINISTIC_STRUCTURE,
        }
        for value in graph.edges
    )


def test_phase_order_and_bidirectional_edges(graph_fixture) -> None:
    _, _, plan, graph, _ = graph_fixture
    phases = sorted(
        (
            value for value in graph.nodes
            if value.node_type == GraphNodeType.PHASE
        ),
        key=lambda value: value.sequence_number or 0,
    )
    edge_keys = {
        (
            value.source_node_id,
            value.target_node_id,
            value.relationship_type,
        )
        for value in graph.edges
    }

    assert [value.label for value in phases] == [
        value.phase_title for value in plan.instructional_phases
    ]
    assert [value.sequence_number for value in phases] == list(
        range(1, len(phases) + 1)
    )
    for previous, following in zip(phases, phases[1:]):
        assert (
            previous.node_id,
            following.node_id,
            GraphRelationshipType.PRECEDES,
        ) in edge_keys
        assert (
            following.node_id,
            previous.node_id,
            GraphRelationshipType.FOLLOWS,
        ) in edge_keys


def test_question_answer_and_phase_relationships(graph_fixture) -> None:
    _, _, plan, graph, _ = graph_fixture
    questions = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.QUESTION
    ]
    answers = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.ANSWER
    ]
    answer_edges = [
        value for value in graph.edges
        if value.relationship_type == GraphRelationshipType.ANSWERED_BY
    ]
    phase_question_edges = [
        value for value in graph.edges
        if value.relationship_type == GraphRelationshipType.CONTAINS
        and any(
            node.node_id == value.source_node_id
            and node.node_type == GraphNodeType.PHASE
            for node in graph.nodes
        )
        and any(
            node.node_id == value.target_node_id
            and node.node_type == GraphNodeType.QUESTION
            for node in graph.nodes
        )
    ]
    expected_questions = [
        question
        for phase in plan.instructional_phases
        for question in phase.questions
    ]
    expected_answers = [
        answer
        for question in expected_questions
        for answer in question.answers
    ]

    assert len(questions) == len(expected_questions)
    assert len(answers) == len(expected_answers)
    assert len(answer_edges) == len(expected_answers)
    assert len(phase_question_edges) == len(expected_questions)
    unanswered = {
        value.node_id for value in questions
        if not value.metadata["source_answer_count"]
    }
    assert len(unanswered) == 3
    assert unanswered.isdisjoint({
        value.source_node_id for value in answer_edges
    })


def test_reading_homework_and_resource_roles_remain_distinct(
    graph_fixture,
) -> None:
    _, _, _, graph, _ = graph_fixture
    readings = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.READING
    ]
    homework = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.HOMEWORK
    ]
    activities = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.ACTIVITY
    ]
    resources = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.RESOURCE
    ]

    assert any("The Attack" in value.label for value in readings)
    assert any("Güera" in value.label for value in homework)
    assert {value.node_id for value in readings}.isdisjoint(
        value.node_id for value in homework
    )
    assert {"1.1", "1.2", "1.3", "SR.1"} <= {
        reference["value"]
        for value in activities
        for reference in value.metadata["curriculum_references"]
    }
    assert any(
        "online" in value.metadata["resource_type"]
        for value in resources
    )


def test_provenance_is_complete_and_references_verified_sources(
    graph_fixture,
) -> None:
    _, bundle, plan, graph, _ = graph_fixture
    assignment_ids = {
        value.assignment_id
        for value in (
            bundle.required_assignments + bundle.optional_assignments
        )
    }
    resource_ids = {
        value.resource_id for value in bundle.resource_summaries
    }
    segment_ids = {
        segment.segment_id
        for assignment in (
            bundle.required_assignments + bundle.optional_assignments
        )
        for segment in assignment.source_segments
    }

    for value in graph.nodes + graph.edges:
        assert value.provenance
        for provenance in value.provenance:
            assert provenance.curriculum_id == bundle.curriculum_id
            assert provenance.unit_id == bundle.unit_id
            assert provenance.lesson_id == bundle.lesson_id
            assert provenance.bundle_digest == bundle.bundle_digest
            assert provenance.instruction_plan_digest == plan.digest
            assert (
                provenance.assignment_id is None
                or provenance.assignment_id in assignment_ids
            )
            assert (
                provenance.resource_id is None
                or provenance.resource_id in resource_ids
            )
            assert set(provenance.source_segment_ids) <= segment_ids


def test_unresolved_links_are_reported_without_inference(
    graph_fixture,
) -> None:
    _, _, _, graph, audit = graph_fixture
    questions = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.QUESTION
    ]
    activities = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.ACTIVITY
    ]
    inferred_alignment_edges = [
        value for value in graph.edges
        if value.relationship_type == GraphRelationshipType.ALIGNED_TO
    ]

    assert len(audit.questions_without_objective_links) == len(questions)
    assert set(audit.activities_without_objective_links) == {
        value.node_id for value in activities
    }
    assert inferred_alignment_edges == []
    assert all(
        value.relationship_basis != RelationshipBasis.EXPLICIT_SOURCE
        or value.relationship_type != GraphRelationshipType.ALIGNED_TO
        for value in graph.edges
    )


def test_no_legacy_generated_content_enters_graph(graph_fixture) -> None:
    _, _, _, graph, _ = graph_fixture
    payload = graph.model_dump_json()

    assert "generated_instructional_guidance" not in payload
    assert "legacy_generated" not in payload


def test_validation_detects_digest_tampering(graph_fixture) -> None:
    _, bundle, plan, graph, audit = graph_fixture
    tampered = graph.model_copy(update={"graph_digest": "tampered"})
    findings = validate_relationship_graph(
        tampered, audit, bundle, plan
    )

    assert any(value.code == "graph_digest_invalid" for value in findings)
    assert any(
        value.code == "audit_graph_digest_invalid" for value in findings
    )


def test_service_is_read_only_and_markdown_is_deterministic(
    graph_fixture,
) -> None:
    root, bundle, plan, graph, audit = graph_fixture
    bundle_path = root / "prepared_source_bundle.json"
    plan_path = root / "source_grounded_instruction_plan.json"
    output = root / "graph-output"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    bundle_before = bundle_path.read_bytes()
    plan_before = plan_path.read_bytes()
    service = InstructionalRelationshipGraphService()

    first = service.build(
        bundle_path=bundle_path,
        instruction_plan_path=plan_path,
        output_directory=output,
    )
    first_bytes = {
        value.name: value.read_bytes()
        for value in (
            first.graph_json_path,
            first.graph_markdown_path,
            first.audit_json_path,
            first.audit_markdown_path,
        )
    }
    second = service.build(
        bundle_path=bundle_path,
        instruction_plan_path=plan_path,
        output_directory=output,
    )

    assert bundle_path.read_bytes() == bundle_before
    assert plan_path.read_bytes() == plan_before
    assert first.graph == graph == second.graph
    assert first.audit == audit == second.audit
    assert first_bytes == {
        value.name: value.read_bytes()
        for value in (
            second.graph_json_path,
            second.graph_markdown_path,
            second.audit_json_path,
            second.audit_markdown_path,
        )
    }
    assert first.graph_markdown_path.read_text(
        encoding="utf-8"
    ) == relationship_graph_markdown(graph, audit)
    assert {value.name for value in output.iterdir()} == {
        "instructional_relationship_graph.json",
        "instructional_relationship_graph.md",
        "instructional_relationship_graph_audit.json",
        "instructional_relationship_graph_audit.md",
    }
    assert not (output / "lesson.json").exists()
    assert not (output / "slides.json").exists()
    assert not (output / "speaker_notes.json").exists()
