"""Deterministic graph construction from verified curriculum intelligence."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.instruction_plan import validate_instruction_plan
from curriculum.intelligence.snapshot import write_json
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    ReadinessState,
    ValidationFinding,
)
from schemas.instructional_relationship_graph_schema import (
    GraphNodeType,
    GraphProvenance,
    GraphRelationshipType,
    InstructionalGraphEdge,
    InstructionalGraphNode,
    InstructionalRelationshipGraph,
    InstructionalRelationshipGraphAudit,
    RelationshipBasis,
    UnresolvedInstructionalRelationship,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
    PreparedResourceSummary,
    PreparedSourceAssignment,
    PreparedSourceSegment,
)
from schemas.source_grounded_instruction_schema import (
    InstructionSourceProvenance,
    SourceGroundedInstructionPlan,
)


GRAPH_SCHEMA_VERSION = "1.0"
GRAPH_BUILDER_VERSION = "1.0"


@dataclass(frozen=True)
class RelationshipGraphResult:
    graph: InstructionalRelationshipGraph
    audit: InstructionalRelationshipGraphAudit
    graph_json_path: Path
    graph_markdown_path: Path
    audit_json_path: Path
    audit_markdown_path: Path


def _finding(
    code: str,
    message: str,
    reference_id: str,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=FindingSeverity.ERROR,
        message=message,
        reference_id=reference_id,
    )


def _printed_coordinates(
    assignment: PreparedSourceAssignment,
) -> list[str]:
    return [
        f"{value.reference_system}:{value.value}"
        for value in assignment.original_curriculum_references
        if value.reference_system in {
            "printed_page",
            "story_relative_page",
            "document_label",
        }
    ]


def _instruction_provenance(
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    values: list[InstructionSourceProvenance],
) -> list[GraphProvenance]:
    return [
        GraphProvenance(
            curriculum_id=bundle.curriculum_id,
            unit_id=bundle.unit_id,
            lesson_id=bundle.lesson_id,
            resource_id=value.resource_id,
            assignment_id=value.assignment_id,
            source_segment_ids=value.segment_ids,
            resource_checksum=value.resource_checksum,
            resource_version=value.resource_version,
            extraction_version=value.extraction_version,
            bundle_digest=bundle.bundle_digest,
            instruction_plan_digest=plan.digest,
            printed_coordinates=value.curriculum_references,
            pdf_page_numbers=value.pdf_page_numbers,
            display_page_numbers=value.display_page_numbers,
            start_character_offset=value.start_character_offset,
            end_character_offset=value.end_character_offset,
            source_content_digest=value.exact_text_digest,
        )
        for value in values
    ]


def _assignment_provenance(
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    assignment: PreparedSourceAssignment,
) -> list[GraphProvenance]:
    resource = next(
        value
        for value in bundle.resource_summaries
        if value.resource_id == assignment.resource_id
    )
    page_provenance = [
        value
        for segment in assignment.source_segments
        for value in segment.provenance
    ]
    return [GraphProvenance(
        curriculum_id=bundle.curriculum_id,
        unit_id=bundle.unit_id,
        lesson_id=bundle.lesson_id,
        resource_id=assignment.resource_id,
        assignment_id=assignment.assignment_id,
        source_segment_ids=assignment.text_segment_ids,
        resource_checksum=resource.stored_checksum,
        resource_version=resource.source_version,
        extraction_version=resource.extraction_version,
        bundle_digest=bundle.bundle_digest,
        instruction_plan_digest=plan.digest,
        printed_coordinates=_printed_coordinates(assignment),
        pdf_page_numbers=sorted({
            value.pdf_page_number
            for value in page_provenance
            if value.pdf_page_number is not None
        }),
        display_page_numbers=sorted({
            value.display_page_number
            for value in page_provenance
            if value.display_page_number is not None
        }),
        source_content_digest=content_digest([
            value.exact_text for value in assignment.source_segments
        ]),
    )]


def _resource_provenance(
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    resource: PreparedResourceSummary,
) -> list[GraphProvenance]:
    return [GraphProvenance(
        curriculum_id=bundle.curriculum_id,
        unit_id=bundle.unit_id,
        lesson_id=bundle.lesson_id,
        resource_id=resource.resource_id,
        resource_checksum=resource.stored_checksum,
        resource_version=resource.source_version,
        extraction_version=resource.extraction_version,
        bundle_digest=bundle.bundle_digest,
        instruction_plan_digest=plan.digest,
        source_content_digest=content_digest({
            "resource_id": resource.resource_id,
            "checksum": resource.stored_checksum,
        }),
    )]


def _segment_provenance(
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    assignment: PreparedSourceAssignment,
    segment: PreparedSourceSegment,
) -> list[GraphProvenance]:
    resource = next(
        value
        for value in bundle.resource_summaries
        if value.resource_id == segment.resource_id
    )
    return [GraphProvenance(
        curriculum_id=bundle.curriculum_id,
        unit_id=bundle.unit_id,
        lesson_id=bundle.lesson_id,
        resource_id=segment.resource_id,
        assignment_id=assignment.assignment_id,
        source_segment_ids=[segment.segment_id],
        resource_checksum=resource.stored_checksum,
        resource_version=resource.source_version,
        extraction_version=resource.extraction_version,
        bundle_digest=bundle.bundle_digest,
        instruction_plan_digest=plan.digest,
        printed_coordinates=_printed_coordinates(assignment),
        pdf_page_numbers=sorted({
            value.pdf_page_number
            for value in segment.provenance
            if value.pdf_page_number is not None
        }),
        display_page_numbers=sorted({
            value.display_page_number
            for value in segment.provenance
            if value.display_page_number is not None
        }),
        source_content_digest=content_digest(segment.exact_text),
    )]


def _node(
    node_type: GraphNodeType,
    label: str,
    source_identifier: str,
    provenance: list[GraphProvenance],
    *,
    sequence_number: int | None = None,
    metadata: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> InstructionalGraphNode:
    metadata = metadata or {}
    return InstructionalGraphNode(
        node_id=stable_id(
            "graph-node", node_type.value, source_identifier
        ),
        node_type=node_type,
        label=label,
        sequence_number=sequence_number,
        source_identifier=source_identifier,
        content_digest=content_digest({
            "node_type": node_type.value,
            "label": label,
            "source_identifier": source_identifier,
            "sequence_number": sequence_number,
            "metadata": metadata,
        }),
        provenance=provenance,
        metadata=metadata,
        warnings=warnings or [],
    )


def _edge(
    source_node_id: str,
    target_node_id: str,
    relationship_type: GraphRelationshipType,
    relationship_basis: RelationshipBasis,
    provenance: list[GraphProvenance],
    *,
    warnings: list[str] | None = None,
) -> InstructionalGraphEdge:
    return InstructionalGraphEdge(
        edge_id=stable_id(
            "graph-edge",
            source_node_id,
            relationship_type.value,
            target_node_id,
            relationship_basis.value,
        ),
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relationship_type=relationship_type,
        relationship_basis=relationship_basis,
        provenance=provenance,
        confidence=1,
        warnings=warnings or [],
    )


def _graph_digest(graph: InstructionalRelationshipGraph) -> str:
    return content_digest(
        graph.model_dump(mode="json", exclude={"graph_digest"})
    )


def _audit_digest(audit: InstructionalRelationshipGraphAudit) -> str:
    return content_digest(
        audit.model_dump(mode="json", exclude={"audit_digest"})
    )


def _role_type(
    assignment: PreparedSourceAssignment,
    resource: PreparedResourceSummary,
) -> GraphNodeType | None:
    if resource.resource_type == "activity_resource":
        return GraphNodeType.ACTIVITY
    if assignment.assignment_type in {
        "assigned_reading",
        "background_reading",
    }:
        return GraphNodeType.READING
    if assignment.assignment_type == "homework":
        return GraphNodeType.HOMEWORK
    return None


class InstructionalRelationshipGraphBuilder:
    """Build only relationships explicit in source or plan structure."""

    def build(
        self,
        bundle: PreparedCurriculumSourceBundle,
        plan: SourceGroundedInstructionPlan,
    ) -> tuple[
        InstructionalRelationshipGraph,
        InstructionalRelationshipGraphAudit,
    ]:
        if bundle.readiness_state != ReadinessState.SOURCE_READY:
            raise ValueError("Prepared bundle must be source_ready.")
        plan_findings = validate_instruction_plan(plan, bundle)
        if plan_findings:
            raise ValueError(
                "Instruction plan validation failed before graph build: "
                + "; ".join(value.message for value in plan_findings)
            )
        if plan.bundle_digest != bundle.bundle_digest:
            raise ValueError("Instruction plan and bundle digests do not match.")

        nodes: list[InstructionalGraphNode] = []
        edges: list[InstructionalGraphEdge] = []
        node_by_source: dict[tuple[GraphNodeType, str], InstructionalGraphNode] = {}

        def add_node(value: InstructionalGraphNode) -> InstructionalGraphNode:
            key = (value.node_type, value.source_identifier or value.node_id)
            existing = node_by_source.get(key)
            if existing is not None:
                return existing
            node_by_source[key] = value
            nodes.append(value)
            return value

        def add_edge(value: InstructionalGraphEdge) -> None:
            if not any(item.edge_id == value.edge_id for item in edges):
                edges.append(value)

        lesson_provenance = _instruction_provenance(
            bundle, plan, plan.provenance
        )
        lesson_node = add_node(_node(
            GraphNodeType.LESSON,
            plan.lesson_title,
            plan.lesson_id,
            lesson_provenance,
            metadata={
                "curriculum_id": plan.curriculum_id,
                "unit_id": plan.unit_id,
                "total_duration_minutes": plan.total_duration_minutes,
            },
            warnings=[value.message for value in plan.warnings],
        ))

        resources = {
            value.resource_id: value for value in bundle.resource_summaries
        }
        resource_nodes = {}
        for resource in bundle.resource_summaries:
            resource_nodes[resource.resource_id] = add_node(_node(
                GraphNodeType.RESOURCE,
                resource.title,
                resource.resource_id,
                _resource_provenance(bundle, plan, resource),
                metadata={
                    "resource_type": resource.resource_type,
                    "source_available": resource.source_available,
                    "current": resource.current,
                },
                warnings=resource.warnings,
            ))

        assignments = (
            bundle.required_assignments + bundle.optional_assignments
        )
        assignment_nodes = {}
        role_nodes = {}
        segment_nodes = {}
        for assignment in assignments:
            provenance = _assignment_provenance(bundle, plan, assignment)
            assignment_node = add_node(_node(
                GraphNodeType.ASSIGNMENT,
                assignment.title,
                assignment.assignment_id,
                provenance,
                metadata={
                    "assignment_type": assignment.assignment_type,
                    "instructional_purpose": assignment.instructional_purpose,
                    "required_status": assignment.required_status,
                    "available": assignment.available,
                    "curriculum_references": [
                        value.model_dump(mode="json")
                        for value in assignment.original_curriculum_references
                    ],
                },
                warnings=assignment.warnings,
            ))
            assignment_nodes[assignment.assignment_id] = assignment_node
            add_edge(_edge(
                lesson_node.node_id,
                assignment_node.node_id,
                GraphRelationshipType.CONTAINS,
                RelationshipBasis.DETERMINISTIC_STRUCTURE,
                provenance,
            ))
            resource_node = resource_nodes[assignment.resource_id]
            add_edge(_edge(
                assignment_node.node_id,
                resource_node.node_id,
                GraphRelationshipType.SOURCED_FROM,
                RelationshipBasis.EXPLICIT_SOURCE,
                provenance,
            ))
            for segment in assignment.source_segments:
                segment_node = add_node(_node(
                    GraphNodeType.SOURCE_SEGMENT,
                    segment.title,
                    segment.segment_id,
                    _segment_provenance(
                        bundle, plan, assignment, segment
                    ),
                    sequence_number=segment.sequence,
                    metadata={
                        "segment_type": segment.segment_type,
                        "resource_id": segment.resource_id,
                    },
                ))
                segment_nodes[segment.segment_id] = segment_node
                add_edge(_edge(
                    assignment_node.node_id,
                    segment_node.node_id,
                    GraphRelationshipType.SOURCED_FROM,
                    RelationshipBasis.EXPLICIT_SOURCE,
                    provenance,
                ))
                add_edge(_edge(
                    segment_node.node_id,
                    resource_node.node_id,
                    GraphRelationshipType.LOCATED_IN,
                    RelationshipBasis.EXPLICIT_SOURCE,
                    segment_node.provenance,
                ))
            role_type = _role_type(
                assignment, resources[assignment.resource_id]
            )
            if role_type is not None:
                role_node = add_node(_node(
                    role_type,
                    assignment.title,
                    assignment.assignment_id,
                    provenance,
                    metadata={
                        "assignment_id": assignment.assignment_id,
                        "assignment_type": assignment.assignment_type,
                        "curriculum_references": [
                            value.model_dump(mode="json")
                            for value in (
                                assignment.original_curriculum_references
                            )
                        ],
                    },
                ))
                role_nodes[assignment.assignment_id] = role_node
                add_edge(_edge(
                    assignment_node.node_id,
                    role_node.node_id,
                    GraphRelationshipType.ASSIGNED_AS,
                    RelationshipBasis.EXPLICIT_SOURCE,
                    provenance,
                ))

        phase_nodes = {}
        question_nodes = {}
        answer_nodes = {}
        activity_node_ids = []
        for phase in plan.instructional_phases:
            phase_provenance = _instruction_provenance(
                bundle, plan, phase.provenance
            )
            phase_node = add_node(_node(
                GraphNodeType.PHASE,
                phase.phase_title,
                phase.id,
                phase_provenance,
                sequence_number=phase.sequence,
                metadata={
                    "phase_type": phase.phase_type,
                    "day_label": phase.day_label,
                    "duration_minutes": phase.duration_minutes,
                    "grouping": phase.grouping,
                },
                warnings=phase.warnings,
            ))
            phase_nodes[phase.id] = phase_node
            add_edge(_edge(
                lesson_node.node_id,
                phase_node.node_id,
                GraphRelationshipType.CONTAINS,
                RelationshipBasis.DETERMINISTIC_STRUCTURE,
                phase_provenance,
            ))
            for assignment_id in phase.referenced_assignment_ids:
                assignment_node = assignment_nodes[assignment_id]
                add_edge(_edge(
                    phase_node.node_id,
                    assignment_node.node_id,
                    GraphRelationshipType.USES,
                    RelationshipBasis.EXPLICIT_SOURCE,
                    phase_provenance,
                ))
                role_node = role_nodes.get(assignment_id)
                if role_node is not None:
                    add_edge(_edge(
                        phase_node.node_id,
                        role_node.node_id,
                        GraphRelationshipType.USES,
                        RelationshipBasis.EXPLICIT_SOURCE,
                        phase_provenance,
                    ))
                    if role_node.node_type == GraphNodeType.ACTIVITY:
                        activity_node_ids.append(role_node.node_id)
            for action in phase.teacher_actions + phase.student_actions:
                node_type = (
                    GraphNodeType.TEACHER_ACTION
                    if action.actor == "teacher"
                    else GraphNodeType.STUDENT_ACTION
                )
                action_provenance = _instruction_provenance(
                    bundle, plan, action.provenance
                )
                action_node = add_node(_node(
                    node_type,
                    action.exact_text,
                    action.id,
                    action_provenance,
                    metadata={"actor": action.actor},
                ))
                add_edge(_edge(
                    phase_node.node_id,
                    action_node.node_id,
                    GraphRelationshipType.CONTAINS,
                    RelationshipBasis.DETERMINISTIC_STRUCTURE,
                    action_provenance,
                ))
                add_edge(_edge(
                    action_node.node_id,
                    phase_node.node_id,
                    GraphRelationshipType.OCCURS_DURING,
                    RelationshipBasis.DETERMINISTIC_STRUCTURE,
                    action_provenance,
                ))
            for question in phase.questions:
                question_provenance = _instruction_provenance(
                    bundle, plan, question.provenance
                )
                prompt_form = (
                    "imperative_prompt"
                    if "?" not in question.question_text
                    else "question"
                )
                context = (
                    "guided_reading"
                    if phase.phase_type == "reading"
                    else "discussion"
                )
                question_node = add_node(_node(
                    GraphNodeType.QUESTION,
                    question.question_text,
                    question.id,
                    question_provenance,
                    metadata={
                        "question_type": question.question_type,
                        "prompt_form": prompt_form,
                        "instructional_context": context,
                        "source_answer_count": len(question.answers),
                    },
                ))
                question_nodes[question.id] = question_node
                add_edge(_edge(
                    phase_node.node_id,
                    question_node.node_id,
                    GraphRelationshipType.CONTAINS,
                    RelationshipBasis.DETERMINISTIC_STRUCTURE,
                    question_provenance,
                ))
                add_edge(_edge(
                    question_node.node_id,
                    phase_node.node_id,
                    GraphRelationshipType.OCCURS_DURING,
                    RelationshipBasis.DETERMINISTIC_STRUCTURE,
                    question_provenance,
                ))
                for provenance in question.provenance:
                    assignment_node = assignment_nodes[
                        provenance.assignment_id
                    ]
                    add_edge(_edge(
                        question_node.node_id,
                        assignment_node.node_id,
                        GraphRelationshipType.SOURCED_FROM,
                        RelationshipBasis.EXPLICIT_SOURCE,
                        question_provenance,
                    ))
                    for segment_id in provenance.segment_ids:
                        add_edge(_edge(
                            question_node.node_id,
                            segment_nodes[segment_id].node_id,
                            GraphRelationshipType.SOURCED_FROM,
                            RelationshipBasis.EXPLICIT_SOURCE,
                            question_provenance,
                        ))
                reading_roles = [
                    role_nodes[value]
                    for value in phase.referenced_assignment_ids
                    if value in role_nodes
                    and role_nodes[value].node_type
                    == GraphNodeType.READING
                ]
                if phase.phase_type == "reading" and len(reading_roles) == 1:
                    add_edge(_edge(
                        question_node.node_id,
                        reading_roles[0].node_id,
                        GraphRelationshipType.ASKS_ABOUT,
                        RelationshipBasis.DETERMINISTIC_STRUCTURE,
                        question_provenance,
                    ))
                for answer in question.answers:
                    answer_provenance = _instruction_provenance(
                        bundle, plan, answer.provenance
                    )
                    answer_node = add_node(_node(
                        GraphNodeType.ANSWER,
                        answer.exact_text,
                        answer.id,
                        answer_provenance,
                        metadata={"question_id": question.id},
                    ))
                    answer_nodes[answer.id] = answer_node
                    add_edge(_edge(
                        question_node.node_id,
                        answer_node.node_id,
                        GraphRelationshipType.ANSWERED_BY,
                        RelationshipBasis.EXPLICIT_SOURCE,
                        answer_provenance,
                    ))

        ordered_phases = [
            phase_nodes[value.id] for value in plan.instructional_phases
        ]
        for previous, following in zip(
            ordered_phases, ordered_phases[1:]
        ):
            provenance = previous.provenance + following.provenance
            add_edge(_edge(
                previous.node_id,
                following.node_id,
                GraphRelationshipType.PRECEDES,
                RelationshipBasis.DETERMINISTIC_STRUCTURE,
                provenance,
            ))
            add_edge(_edge(
                following.node_id,
                previous.node_id,
                GraphRelationshipType.FOLLOWS,
                RelationshipBasis.DETERMINISTIC_STRUCTURE,
                provenance,
            ))

        objective_nodes = {}
        objectives_with_standards = []
        objectives_without_standards = []
        for objective in plan.objectives:
            provenance = _instruction_provenance(
                bundle, plan, objective.provenance
            )
            objective_node = add_node(_node(
                GraphNodeType.OBJECTIVE,
                objective.exact_text,
                objective.id,
                provenance,
                metadata={
                    "explicit_standard_references":
                    objective.standard_references,
                },
            ))
            objective_nodes[objective.id] = objective_node
            add_edge(_edge(
                lesson_node.node_id,
                objective_node.node_id,
                GraphRelationshipType.CONTAINS,
                RelationshipBasis.DETERMINISTIC_STRUCTURE,
                provenance,
            ))
            if objective.standard_references:
                objectives_with_standards.append(objective_node.node_id)
            else:
                objectives_without_standards.append(objective_node.node_id)
            for standard in objective.standard_references:
                standard_node = add_node(_node(
                    GraphNodeType.STANDARD,
                    standard,
                    standard,
                    provenance,
                    metadata={"explicit_in_objective": True},
                ))
                add_edge(_edge(
                    objective_node.node_id,
                    standard_node.node_id,
                    GraphRelationshipType.ALIGNED_TO,
                    RelationshipBasis.EXPLICIT_SOURCE,
                    provenance,
                ))

        graph = InstructionalRelationshipGraph(
            curriculum_id=bundle.curriculum_id,
            unit_id=bundle.unit_id,
            lesson_id=bundle.lesson_id,
            bundle_digest=bundle.bundle_digest,
            instruction_plan_digest=plan.digest,
            nodes=nodes,
            edges=edges,
            warnings=plan.warnings,
            graph_digest="pending",
            schema_version=GRAPH_SCHEMA_VERSION,
            builder_version=GRAPH_BUILDER_VERSION,
        )
        graph = graph.model_copy(update={
            "graph_digest": _graph_digest(graph)
        })

        unresolved = []
        for node_id in objectives_without_standards:
            unresolved.append(UnresolvedInstructionalRelationship(
                category="objective_without_explicit_standard_link",
                source_node_id=node_id,
                target_type=GraphNodeType.STANDARD,
                reason=(
                    "No standard code is directly represented in the source "
                    "objective."
                ),
            ))
        for node in question_nodes.values():
            unresolved.append(UnresolvedInstructionalRelationship(
                category="question_without_explicit_objective_link",
                source_node_id=node.node_id,
                target_type=GraphNodeType.OBJECTIVE,
                reason=(
                    "The verified source does not explicitly align this "
                    "question to an objective."
                ),
            ))
        for node_id in sorted(set(activity_node_ids)):
            unresolved.append(UnresolvedInstructionalRelationship(
                category="activity_without_explicit_objective_link",
                source_node_id=node_id,
                target_type=GraphNodeType.OBJECTIVE,
                reason=(
                    "The verified source does not explicitly align this "
                    "activity to an objective."
                ),
            ))
        audit = InstructionalRelationshipGraphAudit(
            lesson_id=plan.lesson_id,
            graph_digest=graph.graph_digest,
            objectives_with_explicit_standard_links=(
                objectives_with_standards
            ),
            objectives_without_explicit_standard_links=(
                objectives_without_standards
            ),
            questions_without_objective_links=[
                value.node_id for value in question_nodes.values()
            ],
            activities_without_objective_links=sorted(
                set(activity_node_ids)
            ),
            unresolved_relationships=unresolved,
            warnings=plan.warnings,
            audit_digest="pending",
            schema_version=GRAPH_SCHEMA_VERSION,
            builder_version=GRAPH_BUILDER_VERSION,
        )
        audit = audit.model_copy(update={
            "audit_digest": _audit_digest(audit)
        })
        findings = validate_relationship_graph(graph, audit, bundle, plan)
        if findings:
            raise ValueError(
                "Instructional relationship graph validation failed: "
                + "; ".join(value.message for value in findings)
            )
        return graph, audit


def validate_relationship_graph(
    graph: InstructionalRelationshipGraph,
    audit: InstructionalRelationshipGraphAudit,
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
) -> list[ValidationFinding]:
    findings = []
    if bundle.readiness_state != ReadinessState.SOURCE_READY:
        findings.append(_finding(
            "bundle_not_source_ready",
            "The graph requires a source_ready bundle.",
            bundle.lesson_id,
        ))
    if validate_instruction_plan(plan, bundle):
        findings.append(_finding(
            "instruction_plan_invalid",
            "The source-grounded instruction plan is invalid.",
            plan.lesson_id,
        ))
    node_ids = [value.node_id for value in graph.nodes]
    edge_ids = [value.edge_id for value in graph.edges]
    if len(node_ids) != len(set(node_ids)):
        findings.append(_finding(
            "duplicate_node_id", "Graph node IDs are not unique.", graph.lesson_id
        ))
    if len(edge_ids) != len(set(edge_ids)):
        findings.append(_finding(
            "duplicate_edge_id", "Graph edge IDs are not unique.", graph.lesson_id
        ))
    known_nodes = set(node_ids)
    if any(
        value.source_node_id not in known_nodes
        or value.target_node_id not in known_nodes
        for value in graph.edges
    ):
        findings.append(_finding(
            "edge_endpoint_missing",
            "At least one graph edge endpoint does not exist.",
            graph.lesson_id,
        ))
    phase_nodes = sorted(
        (
            value for value in graph.nodes
            if value.node_type == GraphNodeType.PHASE
        ),
        key=lambda value: value.sequence_number or 0,
    )
    if [value.sequence_number for value in phase_nodes] != list(
        range(1, len(plan.instructional_phases) + 1)
    ):
        findings.append(_finding(
            "phase_sequence_invalid",
            "Graph phase sequence does not match the instruction plan.",
            graph.lesson_id,
        ))
    expected_order = {
        (
            phase_nodes[index].node_id,
            phase_nodes[index + 1].node_id,
            GraphRelationshipType.PRECEDES,
        )
        for index in range(len(phase_nodes) - 1)
    } | {
        (
            phase_nodes[index + 1].node_id,
            phase_nodes[index].node_id,
            GraphRelationshipType.FOLLOWS,
        )
        for index in range(len(phase_nodes) - 1)
    }
    actual_order = {
        (
            value.source_node_id,
            value.target_node_id,
            value.relationship_type,
        )
        for value in graph.edges
        if value.relationship_type in {
            GraphRelationshipType.PRECEDES,
            GraphRelationshipType.FOLLOWS,
        }
    }
    if actual_order != expected_order:
        findings.append(_finding(
            "phase_order_edges_invalid",
            "Precedes/follows edges do not exactly represent phase order.",
            graph.lesson_id,
        ))
    expected_questions = sum(
        len(value.questions) for value in plan.instructional_phases
    )
    expected_answers = sum(
        len(question.answers)
        for phase in plan.instructional_phases
        for question in phase.questions
    )
    question_nodes = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.QUESTION
    ]
    answer_nodes = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.ANSWER
    ]
    if len(question_nodes) != expected_questions:
        findings.append(_finding(
            "question_count_mismatch",
            "Graph question count differs from the instruction plan.",
            graph.lesson_id,
        ))
    if len(answer_nodes) != expected_answers:
        findings.append(_finding(
            "answer_count_mismatch",
            "Graph answer count differs from the instruction plan.",
            graph.lesson_id,
        ))
    answered_question_ids = {
        value.source_node_id
        for value in graph.edges
        if value.relationship_type == GraphRelationshipType.ANSWERED_BY
    }
    for question in question_nodes:
        has_source_answer = bool(
            question.metadata.get("source_answer_count")
        )
        if (question.node_id in answered_question_ids) != has_source_answer:
            findings.append(_finding(
                "unanswered_question_link_invalid",
                "Answer links do not preserve source answer availability.",
                question.node_id,
            ))
    assignments = {
        value.assignment_id: value
        for value in (
            bundle.required_assignments + bundle.optional_assignments
        )
    }
    resources = {
        value.resource_id for value in bundle.resource_summaries
    }
    segments = {
        segment.segment_id
        for assignment in assignments.values()
        for segment in assignment.source_segments
    }
    for item in graph.nodes + graph.edges:
        reference_id = (
            item.node_id
            if isinstance(item, InstructionalGraphNode)
            else item.edge_id
        )
        for provenance in item.provenance:
            if (
                provenance.assignment_id is not None
                and provenance.assignment_id not in assignments
            ):
                findings.append(_finding(
                    "assignment_reference_invalid",
                    "Graph provenance references an unknown assignment.",
                    reference_id,
                ))
            if (
                provenance.resource_id is not None
                and provenance.resource_id not in resources
            ):
                findings.append(_finding(
                    "resource_reference_invalid",
                    "Graph provenance references an unknown resource.",
                    reference_id,
                ))
            if not set(provenance.source_segment_ids).issubset(segments):
                findings.append(_finding(
                    "segment_reference_invalid",
                    "Graph provenance references an unknown source segment.",
                    reference_id,
                ))
            if (
                provenance.bundle_digest != bundle.bundle_digest
                or provenance.instruction_plan_digest != plan.digest
            ):
                findings.append(_finding(
                    "graph_provenance_digest_invalid",
                    "Graph provenance references the wrong source snapshot.",
                    reference_id,
                ))
    reading_nodes = {
        value.node_id: value
        for value in graph.nodes
        if value.node_type == GraphNodeType.READING
    }
    homework_nodes = {
        value.node_id: value
        for value in graph.nodes
        if value.node_type == GraphNodeType.HOMEWORK
    }
    if set(reading_nodes).intersection(homework_nodes):
        findings.append(_finding(
            "reading_homework_collapsed",
            "Reading and homework graph nodes are not distinct.",
            graph.lesson_id,
        ))
    phase_type_by_node = {
        value.node_id: value.metadata.get("phase_type")
        for value in phase_nodes
    }
    if any(
        value.source_node_id in phase_type_by_node
        and value.target_node_id in homework_nodes
        and phase_type_by_node[value.source_node_id] != "homework"
        for value in graph.edges
        if value.relationship_type == GraphRelationshipType.USES
    ):
        findings.append(_finding(
            "homework_linked_to_non_homework_phase",
            "Homework is incorrectly linked to a non-homework phase.",
            graph.lesson_id,
        ))
    if graph.graph_digest != _graph_digest(graph):
        findings.append(_finding(
            "graph_digest_invalid",
            "Graph digest does not match graph content.",
            graph.lesson_id,
        ))
    if audit.graph_digest != graph.graph_digest:
        findings.append(_finding(
            "audit_graph_digest_invalid",
            "Graph audit references the wrong graph digest.",
            graph.lesson_id,
        ))
    if audit.audit_digest != _audit_digest(audit):
        findings.append(_finding(
            "audit_digest_invalid",
            "Graph audit digest does not match audit content.",
            graph.lesson_id,
        ))
    return findings


def relationship_graph_markdown(
    graph: InstructionalRelationshipGraph,
    audit: InstructionalRelationshipGraphAudit,
) -> str:
    node_counts = Counter(value.node_type.value for value in graph.nodes)
    edge_counts = Counter(
        value.relationship_type.value for value in graph.edges
    )
    nodes = {value.node_id: value for value in graph.nodes}
    phases = sorted(
        (
            value for value in graph.nodes
            if value.node_type == GraphNodeType.PHASE
        ),
        key=lambda value: value.sequence_number or 0,
    )
    lines = [
        "# Instructional Relationship Graph",
        "",
        "## Graph Summary",
        "",
        f"- Lesson ID: `{graph.lesson_id}`",
        f"- Nodes: {len(graph.nodes)}",
        f"- Edges: {len(graph.edges)}",
        f"- Graph digest: `{graph.graph_digest}`",
        f"- Bundle digest: `{graph.bundle_digest}`",
        f"- Instruction-plan digest: `{graph.instruction_plan_digest}`",
        "",
        "## Node Counts by Type",
        "",
    ]
    lines.extend(
        f"- {key}: {value}" for key, value in sorted(node_counts.items())
    )
    lines.extend(["", "## Edge Counts by Relationship", ""])
    lines.extend(
        f"- {key}: {value}" for key, value in sorted(edge_counts.items())
    )
    lines.extend(["", "## Complete Ordered Phase Chain", ""])
    lines.extend(
        f"{value.sequence_number}. {value.label}" for value in phases
    )
    lines.extend(["", "## Objective and Standard Links", ""])
    objective_edges = [
        value for value in graph.edges
        if value.relationship_type == GraphRelationshipType.ALIGNED_TO
    ]
    lines.extend(
        f"- {nodes[value.source_node_id].label} → "
        f"{nodes[value.target_node_id].label}"
        for value in objective_edges
    )
    if not objective_edges:
        lines.append("- None explicitly represented.")
    lines.extend(["", "## Question and Answer Links", ""])
    answer_edges = [
        value for value in graph.edges
        if value.relationship_type == GraphRelationshipType.ANSWERED_BY
    ]
    lines.extend(
        f"- {nodes[value.source_node_id].label} → "
        f"{nodes[value.target_node_id].label}"
        for value in answer_edges
    )
    unanswered = [
        value for value in graph.nodes
        if value.node_type == GraphNodeType.QUESTION
        and value.node_id not in {
            edge.source_node_id for edge in answer_edges
        }
    ]
    lines.extend(
        f"- Unanswered in source: {value.label}" for value in unanswered
    )
    lines.extend(["", "## Reading and Homework Links", ""])
    for value in graph.nodes:
        if value.node_type in {
            GraphNodeType.READING, GraphNodeType.HOMEWORK
        }:
            lines.append(
                f"- {value.node_type.value}: {value.label} "
                f"(`{value.node_id}`)"
            )
    lines.extend(["", "## Resource and Assignment Links", ""])
    resource_edges = [
        value for value in graph.edges
        if value.relationship_type in {
            GraphRelationshipType.SOURCED_FROM,
            GraphRelationshipType.USES,
            GraphRelationshipType.ASSIGNED_AS,
            GraphRelationshipType.LOCATED_IN,
        }
    ]
    lines.extend(
        f"- {nodes[value.source_node_id].label} "
        f"—{value.relationship_type.value}→ "
        f"{nodes[value.target_node_id].label}"
        for value in resource_edges
    )
    lines.extend(["", "## Unresolved Relationships", ""])
    lines.extend(
        f"- {value.category}: {nodes[value.source_node_id].label} — "
        f"{value.reason}"
        for value in audit.unresolved_relationships
    )
    if not audit.unresolved_relationships:
        lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    lines.extend(
        f"- **{value.code}**: {value.message}"
        for value in graph.warnings
    )
    if not graph.warnings:
        lines.append("- None.")
    lines.extend([
        "",
        "## Digests",
        "",
        f"- Graph: `{graph.graph_digest}`",
        f"- Audit: `{audit.audit_digest}`",
    ])
    return "\n".join(lines).strip() + "\n"


def relationship_graph_audit_markdown(
    audit: InstructionalRelationshipGraphAudit,
) -> str:
    lines = [
        "# Instructional Relationship Graph Audit",
        "",
        f"- Lesson ID: `{audit.lesson_id}`",
        f"- Graph digest: `{audit.graph_digest}`",
        f"- Audit digest: `{audit.audit_digest}`",
        "",
        "## Objective Resolution",
        "",
        "- Objectives with explicit standards: "
        f"{len(audit.objectives_with_explicit_standard_links)}",
        "- Objectives without explicit standards: "
        f"{len(audit.objectives_without_explicit_standard_links)}",
        "",
        "## Unresolved Instructional Relationships",
        "",
    ]
    lines.extend(
        f"- {value.category}: `{value.source_node_id}` → "
        f"{value.target_type.value}; {value.reason}"
        for value in audit.unresolved_relationships
    )
    if not audit.unresolved_relationships:
        lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    lines.extend(
        f"- **{value.code}**: {value.message}" for value in audit.warnings
    )
    if not audit.warnings:
        lines.append("- None.")
    return "\n".join(lines).strip() + "\n"


class InstructionalRelationshipGraphService:
    def build(
        self,
        *,
        bundle_path: str | Path,
        instruction_plan_path: str | Path,
        output_directory: str | Path,
    ) -> RelationshipGraphResult:
        bundle = PreparedCurriculumSourceBundle.model_validate_json(
            Path(bundle_path).read_text(encoding="utf-8")
        )
        plan = SourceGroundedInstructionPlan.model_validate_json(
            Path(instruction_plan_path).read_text(encoding="utf-8")
        )
        graph, audit = InstructionalRelationshipGraphBuilder().build(
            bundle, plan
        )
        output = Path(output_directory)
        graph_json_path = write_json(
            output / "instructional_relationship_graph.json", graph
        )
        graph_markdown_path = (
            output / "instructional_relationship_graph.md"
        )
        graph_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        graph_markdown_path.write_text(
            relationship_graph_markdown(graph, audit),
            encoding="utf-8",
        )
        audit_json_path = write_json(
            output / "instructional_relationship_graph_audit.json",
            audit,
        )
        audit_markdown_path = (
            output / "instructional_relationship_graph_audit.md"
        )
        audit_markdown_path.write_text(
            relationship_graph_audit_markdown(audit),
            encoding="utf-8",
        )
        return RelationshipGraphResult(
            graph=graph,
            audit=audit,
            graph_json_path=graph_json_path,
            graph_markdown_path=graph_markdown_path,
            audit_json_path=audit_json_path,
            audit_markdown_path=audit_markdown_path,
        )


__all__ = [
    "GRAPH_BUILDER_VERSION",
    "GRAPH_SCHEMA_VERSION",
    "InstructionalRelationshipGraphBuilder",
    "InstructionalRelationshipGraphService",
    "RelationshipGraphResult",
    "relationship_graph_audit_markdown",
    "relationship_graph_markdown",
    "validate_relationship_graph",
]
