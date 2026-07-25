"""Auditable AI enrichment for one verified instructional phase."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.instruction_plan import validate_instruction_plan
from curriculum.intelligence.instructional_intelligence_provider import (
    InstructionalIntelligenceProvider,
    OpenAIInstructionalIntelligenceProvider,
)
from curriculum.intelligence.relationship_graph import (
    validate_relationship_graph,
)
from curriculum.intelligence.snapshot import write_json
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    ReadinessState,
    ValidationFinding,
)
from schemas.instructional_relationship_graph_schema import (
    GraphNodeType,
    GraphRelationshipType,
    InstructionalGraphNode,
    InstructionalRelationshipGraph,
    InstructionalRelationshipGraphAudit,
)
from schemas.phase_teacher_support_schema import (
    GeneratedPhaseTeacherSupport,
    PhaseTeacherSupportContext,
    PhaseTeacherSupportContextReference,
    PhaseTeacherSupportDraft,
    PhaseTeacherSupportItem,
    PhaseTeacherSupportValidationReport,
    TeacherSupportContextEntity,
    TeacherSupportGenerationMetadata,
    TeacherSupportGenerationStatus,
    TeacherSupportOrigin,
    TeacherSupportQuestionContext,
    TeacherSupportReviewStatus,
    TeacherSupportType,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)
from schemas.source_grounded_instruction_schema import (
    SourceGroundedInstructionPlan,
)


SUPPORT_SCHEMA_VERSION = "1.0"
SUPPORT_BUILDER_VERSION = "1.0"
SUPPORT_VALIDATOR_VERSION = "1.0"
DEFAULT_PROMPT_VERSION = "1.0"
DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "brain"
    / "prompts"
    / "phase_teacher_support_v1.md"
)


@dataclass(frozen=True)
class PhaseTeacherSupportGenerationResult:
    status: TeacherSupportGenerationStatus
    cache_key: str
    reused: bool
    output_directory: Path
    context: PhaseTeacherSupportContext
    draft: PhaseTeacherSupportDraft | None
    validation: PhaseTeacherSupportValidationReport
    context_path: Path
    prompt_path: Path
    raw_response_path: Path | None
    draft_json_path: Path | None
    draft_markdown_path: Path | None
    validation_json_path: Path
    validation_markdown_path: Path


def _finding(
    code: str,
    severity: FindingSeverity,
    message: str,
    reference_id: str,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        reference_id=reference_id,
    )


def _context_digest(context: PhaseTeacherSupportContext) -> str:
    return content_digest(
        context.model_dump(mode="json", exclude={"context_digest"})
    )


def _content_digest(draft: PhaseTeacherSupportDraft) -> str:
    return content_digest([
        value.model_dump(mode="json") for value in draft.support_sections
    ])


def _draft_digest(draft: PhaseTeacherSupportDraft) -> str:
    payload = draft.model_dump(mode="json", exclude={"digest"})
    payload.pop("generated_at", None)
    metadata = payload.get("generation_metadata", {})
    metadata.pop("provider_usage", None)
    return content_digest(payload)


def _validation_digest(
    report: PhaseTeacherSupportValidationReport,
) -> str:
    return content_digest(
        report.model_dump(mode="json", exclude={"validation_digest"})
    )


def _entity(
    node: InstructionalGraphNode,
    *,
    exact_content: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TeacherSupportContextEntity:
    merged = dict(node.metadata)
    merged.update(metadata or {})
    return TeacherSupportContextEntity(
        node_id=node.node_id,
        source_identifier=node.source_identifier or node.node_id,
        entity_type=node.node_type.value,
        label=node.label,
        exact_content=exact_content,
        metadata=merged,
        provenance=node.provenance,
    )


class PhaseTeacherSupportContextBuilder:
    """Select only graph-verified context for one phase."""

    def build(
        self,
        bundle: PreparedCurriculumSourceBundle,
        plan: SourceGroundedInstructionPlan,
        graph: InstructionalRelationshipGraph,
        graph_audit: InstructionalRelationshipGraphAudit,
        *,
        phase_id: str,
    ) -> PhaseTeacherSupportContext:
        if bundle.readiness_state != ReadinessState.SOURCE_READY:
            raise ValueError("Prepared bundle must be source_ready.")
        if validate_instruction_plan(plan, bundle):
            raise ValueError("Source-grounded instruction plan is invalid.")
        if validate_relationship_graph(
            graph, graph_audit, bundle, plan
        ):
            raise ValueError("Instructional relationship graph is invalid.")
        phase = next(
            (
                value for value in plan.instructional_phases
                if value.id == phase_id
            ),
            None,
        )
        if phase is None:
            raise ValueError(f"Unknown instructional phase: {phase_id}")
        nodes = {value.node_id: value for value in graph.nodes}
        phase_node = next(
            value
            for value in graph.nodes
            if value.node_type == GraphNodeType.PHASE
            and value.source_identifier == phase_id
        )
        outgoing = [
            value for value in graph.edges
            if value.source_node_id == phase_node.node_id
        ]
        contained_ids = {
            value.target_node_id
            for value in outgoing
            if value.relationship_type == GraphRelationshipType.CONTAINS
        }
        used_ids = {
            value.target_node_id
            for value in outgoing
            if value.relationship_type == GraphRelationshipType.USES
        }
        teacher_nodes = sorted(
            (
                nodes[value] for value in contained_ids
                if nodes[value].node_type == GraphNodeType.TEACHER_ACTION
            ),
            key=lambda value: value.node_id,
        )
        student_nodes = sorted(
            (
                nodes[value] for value in contained_ids
                if nodes[value].node_type == GraphNodeType.STUDENT_ACTION
            ),
            key=lambda value: value.node_id,
        )
        question_nodes = sorted(
            (
                nodes[value] for value in contained_ids
                if nodes[value].node_type == GraphNodeType.QUESTION
            ),
            key=lambda value: next(
                index
                for index, question in enumerate(phase.questions)
                if question.id == value.source_identifier
            ),
        )
        answer_edges = {
            value.source_node_id: value.target_node_id
            for value in graph.edges
            if value.relationship_type
            == GraphRelationshipType.ANSWERED_BY
            and value.source_node_id in {
                question.node_id for question in question_nodes
            }
        }
        questions = []
        for node in question_nodes:
            answer_id = answer_edges.get(node.node_id)
            answer_node = nodes[answer_id] if answer_id else None
            questions.append(TeacherSupportQuestionContext(
                node_id=node.node_id,
                source_identifier=node.source_identifier or node.node_id,
                question_text=node.label,
                question_type=node.metadata.get("question_type"),
                prompt_form=node.metadata["prompt_form"],
                answer_node_ids=[answer_id] if answer_id else [],
                source_answers=[answer_node.label] if answer_node else [],
                provenance=node.provenance,
            ))

        assignments_by_id = {
            value.assignment_id: value
            for value in (
                bundle.required_assignments + bundle.optional_assignments
            )
        }
        graph_assignment_nodes = {
            value.source_identifier: value
            for value in graph.nodes
            if value.node_type == GraphNodeType.ASSIGNMENT
        }
        assignment_ids = {
            nodes[value].source_identifier
            for value in used_ids
            if nodes[value].node_type == GraphNodeType.ASSIGNMENT
        }
        assignment_ids.update(
            provenance.assignment_id
            for node in [
                phase_node, *teacher_nodes, *student_nodes, *question_nodes
            ]
            for provenance in node.provenance
            if provenance.assignment_id
        )
        excluded = []
        safe_assignment_ids = set()
        for assignment_id in assignment_ids:
            assignment = assignments_by_id[assignment_id]
            resource = next(
                value
                for value in bundle.resource_summaries
                if value.resource_id == assignment.resource_id
            )
            is_homework = (
                assignment.assignment_type == "homework"
                and resource.resource_type != "activity_resource"
            )
            if is_homework:
                excluded.append(
                    f"Excluded homework assignment {assignment.assignment_id}."
                )
            else:
                safe_assignment_ids.add(assignment_id)

        assignment_nodes = [
            graph_assignment_nodes[value]
            for value in sorted(safe_assignment_ids)
        ]
        reading_nodes = [
            nodes[value]
            for value in sorted(used_ids)
            if nodes[value].node_type == GraphNodeType.READING
            and nodes[value].source_identifier in safe_assignment_ids
        ]
        activity_nodes = [
            nodes[value]
            for value in sorted(used_ids)
            if nodes[value].node_type == GraphNodeType.ACTIVITY
            and nodes[value].source_identifier in safe_assignment_ids
        ]
        resource_ids = {
            assignments_by_id[value].resource_id
            for value in safe_assignment_ids
        }
        resource_nodes = [
            value
            for value in graph.nodes
            if value.node_type == GraphNodeType.RESOURCE
            and value.source_identifier in resource_ids
        ]
        segment_ids = {
            segment_id
            for assignment_id in safe_assignment_ids
            for segment_id in assignments_by_id[
                assignment_id
            ].text_segment_ids
        }
        segment_ids.update(
            segment_id
            for node in [
                phase_node, *teacher_nodes, *student_nodes, *question_nodes
            ]
            for provenance in node.provenance
            for segment_id in provenance.source_segment_ids
        )
        segment_nodes = {
            value.source_identifier: value
            for value in graph.nodes
            if value.node_type == GraphNodeType.SOURCE_SEGMENT
            and value.source_identifier in segment_ids
        }
        segment_content = {
            segment.segment_id: segment.exact_text
            for assignment in assignments_by_id.values()
            for segment in assignment.source_segments
            if segment.segment_id in segment_ids
        }
        teacher_guide_assignment_ids = {
            value.assignment_id
            for value in bundle.required_assignments
            if value.assignment_type == "defines_lesson"
        }
        segment_assignment = {
            segment.segment_id: assignment.assignment_id
            for assignment in assignments_by_id.values()
            for segment in assignment.source_segments
        }
        source_segments = []
        for segment_id in sorted(segment_nodes):
            exact_content = segment_content[segment_id]
            if (
                segment_assignment.get(segment_id)
                in teacher_guide_assignment_ids
            ):
                exact_content = phase.exact_source_text
            source_segments.append(_entity(
                segment_nodes[segment_id],
                exact_content=exact_content,
                metadata={
                    "selection_scope": (
                        "selected_phase_excerpt"
                        if segment_assignment.get(segment_id)
                        in teacher_guide_assignment_ids
                        else "explicitly_linked_segment"
                    )
                },
            ))

        objective_ids = {
            value.target_node_id
            for value in outgoing
            if value.relationship_type in {
                GraphRelationshipType.ALIGNED_TO,
                GraphRelationshipType.SUPPORTED_BY,
            }
            and nodes[value.target_node_id].node_type
            == GraphNodeType.OBJECTIVE
        }
        objective_nodes = [nodes[value] for value in sorted(objective_ids)]
        standard_ids = {
            value.target_node_id
            for value in graph.edges
            if value.source_node_id in objective_ids
            and value.relationship_type
            == GraphRelationshipType.ALIGNED_TO
            and nodes[value.target_node_id].node_type
            == GraphNodeType.STANDARD
        }
        standard_nodes = [nodes[value] for value in sorted(standard_ids)]
        if not objective_nodes:
            excluded.append(
                "No phase-specific objective links are verified; lesson-level "
                "objectives were not inferred into this phase."
            )

        context = PhaseTeacherSupportContext(
            curriculum_id=bundle.curriculum_id,
            unit_id=bundle.unit_id,
            lesson_id=bundle.lesson_id,
            phase_id=phase.id,
            phase_node_id=phase_node.node_id,
            phase_title=phase.phase_title,
            phase_sequence=phase.sequence,
            explicit_duration_minutes=phase.duration_minutes,
            grouping=phase.grouping,
            prepared_bundle_digest=bundle.bundle_digest,
            instruction_plan_digest=plan.digest,
            relationship_graph_digest=graph.graph_digest,
            teacher_actions=[
                _entity(value, exact_content=value.label)
                for value in teacher_nodes
            ],
            student_actions=[
                _entity(value, exact_content=value.label)
                for value in student_nodes
            ],
            objectives=[_entity(value) for value in objective_nodes],
            standards=[_entity(value) for value in standard_nodes],
            questions=questions,
            readings=[_entity(value) for value in reading_nodes],
            activities=[_entity(value) for value in activity_nodes],
            assignments=[_entity(value) for value in assignment_nodes],
            resources=[_entity(value) for value in resource_nodes],
            source_segments=source_segments,
            warnings=graph.warnings,
            excluded_relationships=excluded,
            context_digest="pending",
            schema_version=SUPPORT_SCHEMA_VERSION,
            builder_version=SUPPORT_BUILDER_VERSION,
        )
        return context.model_copy(update={
            "context_digest": _context_digest(context)
        })


def _allowed_support_types() -> set[TeacherSupportType]:
    return set(TeacherSupportType)


def _validation_findings(
    draft: PhaseTeacherSupportDraft,
    context: PhaseTeacherSupportContext,
    graph: InstructionalRelationshipGraph,
    *,
    prompt_version: str,
    provider: str,
    model: str,
) -> list[ValidationFinding]:
    findings = []

    def add(code: str, message: str, reference: str) -> None:
        findings.append(_finding(
            code, FindingSeverity.ERROR, message, reference
        ))

    if draft.phase_id != context.phase_id:
        add(
            "phase_id_mismatch",
            "Generated support targets a different instructional phase.",
            draft.phase_id,
        )
    if draft.source_context.context_digest != context.context_digest:
        add(
            "context_digest_mismatch",
            "Generated support references a different source context.",
            draft.phase_id,
        )
    if draft.prompt_version != prompt_version:
        add(
            "prompt_version_mismatch",
            "Generated support records the wrong prompt version.",
            draft.phase_id,
        )
    if draft.provider != provider or draft.model != model:
        add(
            "provider_metadata_mismatch",
            "Generated support records the wrong provider or model.",
            draft.phase_id,
        )
    if draft.content_origin != TeacherSupportOrigin.AI_GENERATED:
        add(
            "origin_invalid",
            "Generated content must be labeled as AI teacher support.",
            draft.phase_id,
        )
    if (
        draft.review_status
        != TeacherSupportReviewStatus.DRAFT_UNREVIEWED
    ):
        add(
            "review_status_invalid",
            "Generated support must begin as draft_unreviewed.",
            draft.phase_id,
        )
    section_types = [value.support_type for value in draft.support_sections]
    if (
        len(section_types) != len(_allowed_support_types())
        or set(section_types) != _allowed_support_types()
    ):
        add(
            "required_sections_invalid",
            "Exactly the six allowed support section types are required.",
            draft.phase_id,
        )
    node_ids = {value.node_id for value in graph.nodes}
    allowed_by_type = {
        "linked_phase_ids": {context.phase_node_id},
        "linked_objective_ids": {
            value.node_id for value in context.objectives
        },
        "linked_question_ids": {
            value.node_id for value in context.questions
        },
        "linked_activity_ids": {
            value.node_id for value in context.activities
        },
        "linked_reading_ids": {
            value.node_id for value in context.readings
        },
        "linked_resource_ids": {
            value.node_id for value in context.resources
        },
        "linked_source_segment_ids": {
            value.node_id for value in context.source_segments
        },
    }
    generic = {
        "encourage students",
        "differentiate as needed",
        "check for understanding",
    }
    impersonation = (
        "the teacher guide says",
        "the teacher guide requires",
        "the publisher says",
        "the publisher requires",
        "publisher-authored support",
        "publisher question:",
        "publisher answer:",
    )
    prohibited_activity = (
        "required activity",
        "students must complete a new",
        "add a new required",
    )
    for item in draft.support_sections:
        reference = item.support_id
        if item.origin != TeacherSupportOrigin.AI_GENERATED:
            add(
                "support_origin_invalid",
                "Every support item must be labeled as AI-generated.",
                reference,
            )
        if (
            item.review_status
            != TeacherSupportReviewStatus.DRAFT_UNREVIEWED
        ):
            add(
                "support_review_status_invalid",
                "Every support item must remain draft_unreviewed.",
                reference,
            )
        for field, allowed in allowed_by_type.items():
            values = set(getattr(item, field))
            if not values.issubset(node_ids) or not values.issubset(allowed):
                add(
                    "linked_id_invalid",
                    f"{field} contains an unknown or unrelated node ID.",
                    reference,
                )
        if set(item.linked_phase_ids) != {context.phase_node_id}:
            add(
                "unrelated_phase_link",
                "Support may link only to the selected phase.",
                reference,
            )
        evidence_links = (
            item.linked_question_ids
            + item.linked_activity_ids
            + item.linked_reading_ids
            + item.linked_resource_ids
            + item.linked_source_segment_ids
        )
        if not evidence_links:
            add(
                "support_has_no_verified_link",
                "Support must link to verified phase evidence.",
                reference,
            )
        normalized = re.sub(r"\s+", " ", item.content).strip().casefold()
        if len(normalized) < 40 or normalized in generic:
            add(
                "generic_boilerplate",
                "Support is empty or generic rather than phase-specific.",
                reference,
            )
        if re.search(r"\b\d+\s*(?:minutes?|mins?)\b", normalized):
            add(
                "generated_timing_change",
                "Generated support must not introduce or restate timing.",
                reference,
            )
        if any(value in normalized for value in impersonation):
            add(
                "publisher_content_impersonation",
                "Generated support must not impersonate publisher content.",
                reference,
            )
        if any(value in normalized for value in prohibited_activity):
            add(
                "invented_required_activity",
                "Generated support must not introduce a required activity.",
                reference,
            )
        if "the correct answer is" in normalized:
            add(
                "generated_publisher_answer",
                "Generated support must not present a new authoritative answer.",
                reference,
            )
    if draft.prepared_bundle_digest != context.prepared_bundle_digest:
        add(
            "bundle_digest_mismatch",
            "Generated support references the wrong prepared bundle.",
            draft.phase_id,
        )
    if draft.instruction_plan_digest != context.instruction_plan_digest:
        add(
            "plan_digest_mismatch",
            "Generated support references the wrong instruction plan.",
            draft.phase_id,
        )
    if (
        draft.relationship_graph_digest
        != context.relationship_graph_digest
    ):
        add(
            "graph_digest_mismatch",
            "Generated support references the wrong relationship graph.",
            draft.phase_id,
        )
    if draft.content_digest != _content_digest(draft):
        add(
            "content_digest_invalid",
            "Teacher-support content digest is invalid.",
            draft.phase_id,
        )
    if draft.digest != _draft_digest(draft):
        add(
            "draft_digest_invalid",
            "Teacher-support artifact digest is invalid.",
            draft.phase_id,
        )
    return findings


def validate_phase_teacher_support(
    draft: PhaseTeacherSupportDraft,
    context: PhaseTeacherSupportContext,
    graph: InstructionalRelationshipGraph,
    *,
    prompt_version: str,
    provider: str,
    model: str,
) -> PhaseTeacherSupportValidationReport:
    findings = _validation_findings(
        draft,
        context,
        graph,
        prompt_version=prompt_version,
        provider=provider,
        model=model,
    )
    status = "fail" if findings else "pass"
    report = PhaseTeacherSupportValidationReport(
        status=status,
        phase_id=context.phase_id,
        context_digest=context.context_digest,
        draft_digest=draft.digest,
        findings=findings,
        validated_support_types=sorted(
            {value.support_type for value in draft.support_sections},
            key=lambda value: value.value,
        ),
        validation_digest="pending",
        schema_version=SUPPORT_SCHEMA_VERSION,
        validator_version=SUPPORT_VALIDATOR_VERSION,
    )
    return report.model_copy(update={
        "validation_digest": _validation_digest(report)
    })


def _failure_report(
    context: PhaseTeacherSupportContext,
    code: str,
    message: str,
) -> PhaseTeacherSupportValidationReport:
    report = PhaseTeacherSupportValidationReport(
        status="fail",
        phase_id=context.phase_id,
        context_digest=context.context_digest,
        findings=[_finding(
            code,
            FindingSeverity.ERROR,
            message,
            context.phase_id,
        )],
        validation_digest="pending",
        schema_version=SUPPORT_SCHEMA_VERSION,
        validator_version=SUPPORT_VALIDATOR_VERSION,
    )
    return report.model_copy(update={
        "validation_digest": _validation_digest(report)
    })


def _cache_key(
    context: PhaseTeacherSupportContext,
    *,
    prompt_version: str,
    provider: str,
    model: str,
    prompt_contract_digest: str,
    generation_parameters: dict[str, Any],
) -> str:
    return content_digest({
        "curriculum_id": context.curriculum_id,
        "unit_id": context.unit_id,
        "lesson_id": context.lesson_id,
        "phase_id": context.phase_id,
        "bundle_digest": context.prepared_bundle_digest,
        "instruction_plan_digest": context.instruction_plan_digest,
        "relationship_graph_digest": context.relationship_graph_digest,
        "context_digest": context.context_digest,
        "prompt_version": prompt_version,
        "provider": provider,
        "model": model,
        "prompt_contract_digest": prompt_contract_digest,
        "generation_parameters": generation_parameters,
    })


def phase_teacher_support_markdown(
    draft: PhaseTeacherSupportDraft,
    context: PhaseTeacherSupportContext,
    validation: PhaseTeacherSupportValidationReport,
) -> str:
    lines = [
        f"# Phase Teacher Support Draft: {draft.phase_title}",
        "",
        "> AI-generated teacher support. Draft and unreviewed. This is not "
        "publisher-authored curriculum.",
        "",
        "## Verified Curriculum Context",
        "",
        f"- Phase: {context.phase_sequence}. {context.phase_title}",
        f"- Explicit duration: {context.explicit_duration_minutes} minutes",
        f"- Questions: {len(context.questions)}",
        "- Source-provided answers: "
        f"{sum(len(value.source_answers) for value in context.questions)}",
        f"- Readings: {', '.join(value.label for value in context.readings)}",
        f"- Context digest: `{context.context_digest}`",
        "",
        "## AI-Generated Teacher Support",
        "",
    ]
    for item in draft.support_sections:
        lines.extend([
            f"### {item.support_type.value}: {item.title}",
            "",
            item.content,
            "",
            f"- Intended use: {item.intended_use}",
            f"- Evidence summary: {item.evidence_summary}",
            f"- Origin: `{item.origin.value}`",
            f"- Review status: `{item.review_status.value}`",
            f"- Support ID: `{item.support_id}`",
            "",
        ])
    lines.extend(["## Warnings", ""])
    lines.extend(
        f"- **{value.code}**: {value.message}"
        for value in draft.warnings
    )
    if not draft.warnings:
        lines.append("- None.")
    lines.extend([
        "",
        "## Validation",
        "",
        f"- Status: **{validation.status}**",
    ])
    lines.extend(
        f"- **{value.code}**: {value.message}"
        for value in validation.findings
    )
    if not validation.findings:
        lines.append("- No blockers.")
    lines.extend([
        "",
        "## Generation Metadata",
        "",
        f"- Provider: `{draft.provider}`",
        f"- Model: `{draft.model}`",
        f"- Prompt version: `{draft.prompt_version}`",
        f"- Content digest: `{draft.content_digest}`",
        f"- Artifact digest: `{draft.digest}`",
    ])
    return "\n".join(lines).strip() + "\n"


def phase_teacher_support_validation_markdown(
    validation: PhaseTeacherSupportValidationReport,
) -> str:
    lines = [
        "# Phase Teacher Support Validation",
        "",
        f"- Phase ID: `{validation.phase_id}`",
        f"- Status: **{validation.status}**",
        f"- Context digest: `{validation.context_digest}`",
        f"- Draft digest: `{validation.draft_digest or 'unavailable'}`",
        f"- Validation digest: `{validation.validation_digest}`",
        "",
        "## Findings",
        "",
    ]
    lines.extend(
        f"- **{value.severity.value} — {value.code}**: {value.message}"
        for value in validation.findings
    )
    if not validation.findings:
        lines.append("- None.")
    return "\n".join(lines).strip() + "\n"


class GroundedInstructionalIntelligenceService:
    """Generate and cache one isolated phase-support draft."""

    def __init__(
        self,
        provider: InstructionalIntelligenceProvider | None = None,
        *,
        prompt_path: str | Path = DEFAULT_PROMPT_PATH,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ) -> None:
        self.provider = provider
        self.prompt_path = Path(prompt_path)
        self.prompt_version = prompt_version

    def _provider(
        self,
    ) -> tuple[InstructionalIntelligenceProvider | None, str, str, str | None]:
        if self.provider is not None:
            return (
                self.provider,
                self.provider.provider_name,
                self.provider.model_name,
                None,
            )
        try:
            provider = OpenAIInstructionalIntelligenceProvider()
            return (
                provider,
                provider.provider_name,
                provider.model_name,
                None,
            )
        except Exception as error:
            from config.settings import get_settings

            error_text = str(error)
            safe_error = (
                error_text
                if "API_KEY" in error_text
                else (
                    "Provider configuration is unavailable "
                    f"({type(error).__name__})."
                )
            )
            return (
                None,
                "openai",
                get_settings().teacheros_model,
                safe_error,
            )

    def generate(
        self,
        *,
        bundle_path: str | Path,
        instruction_plan_path: str | Path,
        relationship_graph_path: str | Path,
        relationship_graph_audit_path: str | Path,
        phase_id: str,
        output_directory: str | Path,
        generation_parameters: dict[str, Any] | None = None,
    ) -> PhaseTeacherSupportGenerationResult:
        generation_parameters = generation_parameters or {
            "max_context_characters": 1_000_000,
            "provider_parameters": {},
        }
        bundle = PreparedCurriculumSourceBundle.model_validate_json(
            Path(bundle_path).read_text(encoding="utf-8")
        )
        plan = SourceGroundedInstructionPlan.model_validate_json(
            Path(instruction_plan_path).read_text(encoding="utf-8")
        )
        graph = InstructionalRelationshipGraph.model_validate_json(
            Path(relationship_graph_path).read_text(encoding="utf-8")
        )
        graph_audit = (
            InstructionalRelationshipGraphAudit.model_validate_json(
                Path(relationship_graph_audit_path).read_text(
                    encoding="utf-8"
                )
            )
        )
        context = PhaseTeacherSupportContextBuilder().build(
            bundle,
            plan,
            graph,
            graph_audit,
            phase_id=phase_id,
        )
        prompt_contract = self.prompt_path.read_text(encoding="utf-8")
        prompt_contract_digest = content_digest(prompt_contract)
        provider, provider_name, model_name, provider_error = self._provider()
        cache_key = _cache_key(
            context,
            prompt_version=self.prompt_version,
            provider=provider_name,
            model=model_name,
            prompt_contract_digest=prompt_contract_digest,
            generation_parameters=generation_parameters,
        )
        target = Path(output_directory) / cache_key
        target.mkdir(parents=True, exist_ok=True)
        context_path = write_json(
            target / "phase_teacher_support_context.json", context
        )
        prompt_artifact = target / "phase_teacher_support_prompt.md"
        prompt_artifact.write_text(prompt_contract, encoding="utf-8")
        raw_path = target / "phase_teacher_support_raw_response.json"
        draft_path = target / "phase_teacher_support_draft.json"
        draft_md_path = target / "phase_teacher_support_draft.md"
        validation_path = (
            target / "phase_teacher_support_validation.json"
        )
        validation_md_path = (
            target / "phase_teacher_support_validation.md"
        )

        if draft_path.is_file() and validation_path.is_file():
            try:
                cached_draft = PhaseTeacherSupportDraft.model_validate_json(
                    draft_path.read_text(encoding="utf-8")
                )
                cached_validation = (
                    PhaseTeacherSupportValidationReport.model_validate_json(
                        validation_path.read_text(encoding="utf-8")
                    )
                )
                current_validation = validate_phase_teacher_support(
                    cached_draft,
                    context,
                    graph,
                    prompt_version=self.prompt_version,
                    provider=provider_name,
                    model=model_name,
                )
                if (
                    cached_validation.status == "pass"
                    and current_validation.status == "pass"
                ):
                    return PhaseTeacherSupportGenerationResult(
                        status=TeacherSupportGenerationStatus.CACHE_HIT_VALID,
                        cache_key=cache_key,
                        reused=True,
                        output_directory=target,
                        context=context,
                        draft=cached_draft,
                        validation=current_validation,
                        context_path=context_path,
                        prompt_path=prompt_artifact,
                        raw_response_path=(
                            raw_path if raw_path.is_file() else None
                        ),
                        draft_json_path=draft_path,
                        draft_markdown_path=draft_md_path,
                        validation_json_path=validation_path,
                        validation_markdown_path=validation_md_path,
                    )
            except (OSError, ValidationError, ValueError, json.JSONDecodeError):
                pass

        def failure(
            status: TeacherSupportGenerationStatus,
            code: str,
            message: str,
        ) -> PhaseTeacherSupportGenerationResult:
            validation = _failure_report(context, code, message)
            write_json(validation_path, validation)
            validation_md_path.write_text(
                phase_teacher_support_validation_markdown(validation),
                encoding="utf-8",
            )
            return PhaseTeacherSupportGenerationResult(
                status=status,
                cache_key=cache_key,
                reused=False,
                output_directory=target,
                context=context,
                draft=None,
                validation=validation,
                context_path=context_path,
                prompt_path=prompt_artifact,
                raw_response_path=(
                    raw_path if raw_path.is_file() else None
                ),
                draft_json_path=None,
                draft_markdown_path=None,
                validation_json_path=validation_path,
                validation_markdown_path=validation_md_path,
            )

        context_size = len(context.model_dump_json())
        max_context = int(
            generation_parameters.get("max_context_characters", 1_000_000)
        )
        if context_size > max_context:
            return failure(
                TeacherSupportGenerationStatus.VALIDATION_BLOCKED,
                "context_too_large",
                f"Selected context is {context_size} bytes; maximum is "
                f"{max_context}.",
            )
        if provider is None:
            return failure(
                TeacherSupportGenerationStatus.PROVIDER_UNAVAILABLE,
                "provider_unavailable",
                provider_error or "Instructional-intelligence provider unavailable.",
            )
        try:
            response = provider.generate_phase_teacher_support(
                context, prompt_contract
            )
        except Exception as error:
            return failure(
                TeacherSupportGenerationStatus.PROVIDER_ERROR,
                "provider_error",
                "Instructional-intelligence provider failed "
                f"({type(error).__name__}).",
            )
        raw_payload = response.raw_payload
        raw_digest = content_digest(raw_payload)
        write_json(raw_path, {
            "provider": provider_name,
            "model": model_name,
            "prompt_version": self.prompt_version,
            "raw_response_digest": raw_digest,
            "raw_payload": raw_payload,
        })
        try:
            if isinstance(raw_payload, str):
                raw_payload = json.loads(raw_payload)
            generated = GeneratedPhaseTeacherSupport.model_validate(
                raw_payload
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
            return failure(
                TeacherSupportGenerationStatus.RESPONSE_INVALID,
                "response_invalid",
                f"Provider response is not valid structured support: {error}",
            )
        if (
            generated.phase_id != context.phase_id
            or generated.source_context_digest != context.context_digest
        ):
            return failure(
                TeacherSupportGenerationStatus.VALIDATION_BLOCKED,
                "generated_identity_mismatch",
                "Provider response does not match the selected phase context.",
            )
        support_items = [
            PhaseTeacherSupportItem(
                support_id=stable_id(
                    "phase-support",
                    context.context_digest,
                    value.support_type.value,
                    value.title,
                    re.sub(r"\s+", " ", value.content).strip(),
                    *value.linked_phase_ids,
                    *value.linked_question_ids,
                    *value.linked_activity_ids,
                    *value.linked_reading_ids,
                    *value.linked_resource_ids,
                    *value.linked_source_segment_ids,
                ),
                **value.model_dump(),
            )
            for value in generated.support_sections
        ]
        parsed_digest = content_digest(generated.model_dump(mode="json"))
        phase = next(
            value
            for value in plan.instructional_phases
            if value.id == phase_id
        )
        included_node_ids = sorted({
            context.phase_node_id,
            *[
                value.node_id
                for group in (
                    context.teacher_actions,
                    context.student_actions,
                    context.objectives,
                    context.standards,
                    context.readings,
                    context.activities,
                    context.assignments,
                    context.resources,
                    context.source_segments,
                )
                for value in group
            ],
            *[value.node_id for value in context.questions],
            *[
                answer_id
                for value in context.questions
                for answer_id in value.answer_node_ids
            ],
        })
        provisional = PhaseTeacherSupportDraft(
            curriculum_id=context.curriculum_id,
            unit_id=context.unit_id,
            lesson_id=context.lesson_id,
            phase_id=context.phase_id,
            phase_title=phase.phase_title,
            instruction_plan_digest=context.instruction_plan_digest,
            relationship_graph_digest=context.relationship_graph_digest,
            prepared_bundle_digest=context.prepared_bundle_digest,
            schema_version=SUPPORT_SCHEMA_VERSION,
            builder_version=SUPPORT_BUILDER_VERSION,
            prompt_version=self.prompt_version,
            provider=provider_name,
            model=model_name,
            generated_at=datetime.now(timezone.utc),
            generation_status=TeacherSupportGenerationStatus.GENERATED_VALID,
            review_status=TeacherSupportReviewStatus.DRAFT_UNREVIEWED,
            content_origin=TeacherSupportOrigin.AI_GENERATED,
            source_context=PhaseTeacherSupportContextReference(
                context_digest=context.context_digest,
                context_artifact=context_path.name,
                phase_node_id=context.phase_node_id,
                included_node_ids=included_node_ids,
            ),
            support_sections=support_items,
            warnings=context.warnings,
            blockers=[],
            generation_metadata=TeacherSupportGenerationMetadata(
                cache_key=cache_key,
                input_context_digest=context.context_digest,
                prompt_contract_digest=prompt_contract_digest,
                raw_response_digest=raw_digest,
                parsed_response_digest=parsed_digest,
                generation_parameters=generation_parameters,
                retry_count=response.retry_count,
                validation_result="pending",
                provider_usage=response.usage,
            ),
            content_digest="pending",
            digest="pending",
        )
        provisional = provisional.model_copy(update={
            "content_digest": _content_digest(provisional)
        })
        provisional = provisional.model_copy(update={
            "digest": _draft_digest(provisional)
        })
        initial_findings = _validation_findings(
            provisional,
            context,
            graph,
            prompt_version=self.prompt_version,
            provider=provider_name,
            model=model_name,
        )
        final_status = (
            TeacherSupportGenerationStatus.VALIDATION_BLOCKED
            if initial_findings
            else TeacherSupportGenerationStatus.GENERATED_VALID
        )
        final = provisional.model_copy(update={
            "generation_status": final_status,
            "blockers": initial_findings,
            "generation_metadata": provisional.generation_metadata.model_copy(
                update={
                    "validation_result": (
                        "fail" if initial_findings else "pass"
                    )
                }
            ),
            "digest": "pending",
        })
        final = final.model_copy(update={"digest": _draft_digest(final)})
        validation = validate_phase_teacher_support(
            final,
            context,
            graph,
            prompt_version=self.prompt_version,
            provider=provider_name,
            model=model_name,
        )
        write_json(draft_path, final)
        write_json(validation_path, validation)
        draft_md_path.write_text(
            phase_teacher_support_markdown(final, context, validation),
            encoding="utf-8",
        )
        validation_md_path.write_text(
            phase_teacher_support_validation_markdown(validation),
            encoding="utf-8",
        )
        return PhaseTeacherSupportGenerationResult(
            status=final_status,
            cache_key=cache_key,
            reused=False,
            output_directory=target,
            context=context,
            draft=final,
            validation=validation,
            context_path=context_path,
            prompt_path=prompt_artifact,
            raw_response_path=raw_path,
            draft_json_path=draft_path,
            draft_markdown_path=draft_md_path,
            validation_json_path=validation_path,
            validation_markdown_path=validation_md_path,
        )


__all__ = [
    "DEFAULT_PROMPT_PATH",
    "DEFAULT_PROMPT_VERSION",
    "GroundedInstructionalIntelligenceService",
    "PhaseTeacherSupportContextBuilder",
    "PhaseTeacherSupportGenerationResult",
    "phase_teacher_support_markdown",
    "phase_teacher_support_validation_markdown",
    "validate_phase_teacher_support",
]
