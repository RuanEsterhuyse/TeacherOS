"""Curriculum-agnostic contracts for verified instructional relationships."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.curriculum_intelligence_schema import ValidationFinding


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GraphNodeType(str, Enum):
    LESSON = "lesson"
    PHASE = "phase"
    OBJECTIVE = "objective"
    STANDARD = "standard"
    TEACHER_ACTION = "teacher_action"
    STUDENT_ACTION = "student_action"
    QUESTION = "question"
    ANSWER = "answer"
    ACTIVITY = "activity"
    READING = "reading"
    HOMEWORK = "homework"
    ASSIGNMENT = "assignment"
    RESOURCE = "resource"
    SOURCE_SEGMENT = "source_segment"


class GraphRelationshipType(str, Enum):
    CONTAINS = "contains"
    OCCURS_DURING = "occurs_during"
    FOLLOWS = "follows"
    PRECEDES = "precedes"
    REFERENCES = "references"
    USES = "uses"
    REQUIRES = "requires"
    ASKS_ABOUT = "asks_about"
    ANSWERED_BY = "answered_by"
    ASSIGNED_AS = "assigned_as"
    SOURCED_FROM = "sourced_from"
    ALIGNED_TO = "aligned_to"
    SUPPORTED_BY = "supported_by"
    LOCATED_IN = "located_in"


class RelationshipBasis(str, Enum):
    EXPLICIT_SOURCE = "explicit_source_relationship"
    DETERMINISTIC_STRUCTURE = "deterministic_structure"


class GraphProvenance(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    resource_id: Optional[str] = None
    assignment_id: Optional[str] = None
    source_segment_ids: list[str] = Field(default_factory=list)
    resource_checksum: Optional[str] = None
    resource_version: Optional[str] = None
    extraction_version: Optional[str] = None
    bundle_digest: str = Field(min_length=1)
    instruction_plan_digest: str = Field(min_length=1)
    printed_coordinates: list[str] = Field(default_factory=list)
    pdf_page_numbers: list[int] = Field(default_factory=list)
    display_page_numbers: list[int] = Field(default_factory=list)
    start_character_offset: Optional[int] = Field(default=None, ge=0)
    end_character_offset: Optional[int] = Field(default=None, ge=0)
    source_content_digest: Optional[str] = None


class InstructionalGraphNode(StrictModel):
    node_id: str = Field(min_length=1)
    node_type: GraphNodeType
    label: str = Field(min_length=1)
    sequence_number: Optional[int] = Field(default=None, ge=1)
    source_identifier: Optional[str] = None
    content_digest: str = Field(min_length=1)
    provenance: list[GraphProvenance] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class InstructionalGraphEdge(StrictModel):
    edge_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relationship_type: GraphRelationshipType
    relationship_basis: RelationshipBasis
    provenance: list[GraphProvenance] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class UnresolvedInstructionalRelationship(StrictModel):
    category: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_type: GraphNodeType
    reason: str = Field(min_length=1)


class InstructionalRelationshipGraphAudit(StrictModel):
    lesson_id: str = Field(min_length=1)
    graph_digest: str = Field(min_length=1)
    objectives_with_explicit_standard_links: list[str] = Field(
        default_factory=list
    )
    objectives_without_explicit_standard_links: list[str] = Field(
        default_factory=list
    )
    questions_without_objective_links: list[str] = Field(default_factory=list)
    activities_without_objective_links: list[str] = Field(
        default_factory=list
    )
    unresolved_relationships: list[
        UnresolvedInstructionalRelationship
    ] = Field(default_factory=list)
    warnings: list[ValidationFinding] = Field(default_factory=list)
    audit_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


class InstructionalRelationshipGraph(StrictModel):
    curriculum_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    bundle_digest: str = Field(min_length=1)
    instruction_plan_digest: str = Field(min_length=1)
    nodes: list[InstructionalGraphNode]
    edges: list[InstructionalGraphEdge]
    warnings: list[ValidationFinding] = Field(default_factory=list)
    graph_digest: str = Field(min_length=1)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


__all__ = [
    "GraphNodeType",
    "GraphProvenance",
    "GraphRelationshipType",
    "InstructionalGraphEdge",
    "InstructionalGraphNode",
    "InstructionalRelationshipGraph",
    "InstructionalRelationshipGraphAudit",
    "RelationshipBasis",
    "UnresolvedInstructionalRelationship",
]
