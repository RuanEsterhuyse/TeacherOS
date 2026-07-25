"""Deterministic phase-support policy and validated cache resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from curriculum.intelligence.grounded_instructional_intelligence import (
    DEFAULT_PROMPT_PATH,
    PhaseTeacherSupportContextBuilder,
    SUPPORT_BUILDER_VERSION,
    SUPPORT_SCHEMA_VERSION,
    _cache_key,
    validate_phase_teacher_support,
)
from curriculum.intelligence.ids import content_digest
from schemas.instructional_relationship_graph_schema import (
    InstructionalRelationshipGraph,
    InstructionalRelationshipGraphAudit,
)
from schemas.lesson_rendering_model_schema import (
    PhaseSupportManifestEntry,
    SupportRequirement,
    SupportStatus,
)
from schemas.phase_teacher_support_schema import PhaseTeacherSupportDraft
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)
from schemas.source_grounded_instruction_schema import (
    SourceGroundedInstructionPlan,
)


SUPPORT_POLICY_VERSION = "1.0"


class ExpectedPhaseSupportIdentity(BaseModel):
    """Caller-selected identity for exactly one Phase 4B cache artifact."""

    model_config = ConfigDict(extra="forbid")

    phase_id: str = Field(min_length=1)
    cache_key: str = Field(min_length=1)
    context_digest: str = Field(min_length=1)
    prepared_bundle_digest: str = Field(min_length=1)
    instruction_plan_digest: str = Field(min_length=1)
    relationship_graph_digest: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_content_digest: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    support_schema_version: str = SUPPORT_SCHEMA_VERSION
    support_builder_version: str = SUPPORT_BUILDER_VERSION
    content_digest: str = Field(min_length=1)
    draft_digest: str = Field(min_length=1)

_LESSON_ONE_POLICY = {
    1: (SupportRequirement.SKIP, "Source-only administrative preparation."),
    2: (SupportRequirement.GENERATE_OR_REUSE, "Teacher support is useful for conceptual introduction."),
    3: (SupportRequirement.GENERATE_OR_REUSE, "Teacher support is useful for text introduction."),
    4: (SupportRequirement.CURRICULUM_ONLY, "The short source reflection is sufficient."),
    5: (SupportRequirement.GENERATE_OR_REUSE, "Teacher support is useful for reading preparation."),
    6: (SupportRequirement.REUSE_VALID_CACHE, "Reuse the validated guided-reading support cache."),
    7: (SupportRequirement.GENERATE_OR_REUSE, "Teacher support is useful for discussion facilitation."),
    8: (SupportRequirement.SKIP, "Homework remains publisher-controlled."),
}


def support_policy(sequence: int) -> tuple[SupportRequirement, str]:
    """Return the approved deterministic Lesson 1 policy."""
    return _LESSON_ONE_POLICY.get(
        sequence,
        (SupportRequirement.CURRICULUM_ONLY, "No enrichment policy is defined; use publisher content."),
    )


def resolve_phase_support(
    bundle: PreparedCurriculumSourceBundle,
    plan: SourceGroundedInstructionPlan,
    graph: InstructionalRelationshipGraph,
    graph_audit: InstructionalRelationshipGraphAudit,
    *,
    cache_directory: str | Path | None,
    expected_support_identities: dict[
        str, ExpectedPhaseSupportIdentity
    ] | None = None,
    prompt_path: str | Path = DEFAULT_PROMPT_PATH,
) -> tuple[list[PhaseSupportManifestEntry], dict[str, PhaseTeacherSupportDraft]]:
    """Resolve only digest-valid, currently valid support without using mtimes."""
    expected_support_identities = expected_support_identities or {}
    prompt_digest = content_digest(Path(prompt_path).read_text(encoding="utf-8"))
    root = Path(cache_directory) if cache_directory else None
    manifests: list[PhaseSupportManifestEntry] = []
    resolved: dict[str, PhaseTeacherSupportDraft] = {}

    for phase in plan.instructional_phases:
        requirement, reason = support_policy(phase.sequence)
        if requirement == SupportRequirement.SKIP:
            manifests.append(PhaseSupportManifestEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                requirement=requirement, status=SupportStatus.NOT_APPLICABLE,
                reason=reason,
            ))
            continue
        if requirement == SupportRequirement.CURRICULUM_ONLY:
            manifests.append(PhaseSupportManifestEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                requirement=requirement, status=SupportStatus.CURRICULUM_ONLY,
                reason=reason,
            ))
            continue

        identity = expected_support_identities.get(phase.id)
        rejected: list[str] = []
        invalid_expected_artifact = False
        draft = None
        draft_path = None
        cache_key = None
        if identity is not None:
            context = PhaseTeacherSupportContextBuilder().build(
                bundle, plan, graph, graph_audit, phase_id=phase.id
            )
            expected_key = _cache_key(
                context,
                prompt_version=identity.prompt_version,
                provider=identity.provider,
                model=identity.model,
                prompt_contract_digest=identity.prompt_content_digest,
                generation_parameters=identity.generation_parameters,
            )
            identity_errors = []
            if identity.phase_id != phase.id:
                identity_errors.append("phase identity mismatch")
            if identity.context_digest != context.context_digest:
                identity_errors.append("context digest mismatch")
            if identity.prepared_bundle_digest != bundle.bundle_digest:
                identity_errors.append("bundle digest mismatch")
            if identity.instruction_plan_digest != plan.digest:
                identity_errors.append("instruction-plan digest mismatch")
            if identity.relationship_graph_digest != graph.graph_digest:
                identity_errors.append("relationship-graph digest mismatch")
            if identity.prompt_content_digest != prompt_digest:
                identity_errors.append("prompt content digest mismatch")
            if identity.support_schema_version != SUPPORT_SCHEMA_VERSION:
                identity_errors.append("support schema version mismatch")
            if identity.support_builder_version != SUPPORT_BUILDER_VERSION:
                identity_errors.append("support builder version mismatch")
            if identity.cache_key != expected_key:
                identity_errors.append("calculated cache-key mismatch")
            if identity_errors:
                invalid_expected_artifact = True
                rejected.append(
                    "Expected support identity rejected: "
                    + "; ".join(identity_errors) + "."
                )
            elif root:
                directory = root / expected_key
                candidate_draft_path = (
                    directory / "phase_teacher_support_draft.json"
                )
                validation_path = (
                    directory / "phase_teacher_support_validation.json"
                )
                if not candidate_draft_path.is_file() or not validation_path.is_file():
                    rejected.append(
                        "The exact expected support artifact does not exist."
                    )
                else:
                    try:
                        candidate = PhaseTeacherSupportDraft.model_validate_json(
                            candidate_draft_path.read_text(encoding="utf-8")
                        )
                        saved_validation = json.loads(
                            validation_path.read_text(encoding="utf-8")
                        )
                        current = validate_phase_teacher_support(
                            candidate, context, graph,
                            prompt_version=identity.prompt_version,
                            provider=identity.provider,
                            model=identity.model,
                        )
                        field_matches = (
                            candidate.phase_id == identity.phase_id
                            and candidate.source_context.context_digest
                            == identity.context_digest
                            and candidate.prepared_bundle_digest
                            == identity.prepared_bundle_digest
                            and candidate.instruction_plan_digest
                            == identity.instruction_plan_digest
                            and candidate.relationship_graph_digest
                            == identity.relationship_graph_digest
                            and candidate.prompt_version
                            == identity.prompt_version
                            and candidate.provider == identity.provider
                            and candidate.model == identity.model
                            and candidate.schema_version
                            == identity.support_schema_version
                            and candidate.builder_version
                            == identity.support_builder_version
                            and candidate.generation_metadata.generation_parameters
                            == identity.generation_parameters
                            and candidate.generation_metadata.cache_key
                            == identity.cache_key
                            and candidate.content_digest
                            == identity.content_digest
                            and candidate.digest == identity.draft_digest
                        )
                        if (
                            not field_matches
                            or saved_validation.get("status") != "pass"
                            or current.status != "pass"
                        ):
                            invalid_expected_artifact = True
                            rejected.append(
                                "The exact expected support artifact failed "
                                "identity, digest, or current validation."
                            )
                        else:
                            draft = candidate
                            draft_path = candidate_draft_path
                            cache_key = expected_key
                    except (
                        OSError, ValueError, ValidationError,
                        json.JSONDecodeError,
                    ) as error:
                        invalid_expected_artifact = True
                        rejected.append(
                            "The exact expected support artifact was rejected: "
                            f"{type(error).__name__}."
                        )

        if draft is not None and draft_path is not None and cache_key is not None:
            resolved[phase.id] = draft
            manifests.append(PhaseSupportManifestEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                requirement=requirement, status=SupportStatus.VALID_CACHE,
                reason=reason, cache_key=cache_key, draft_digest=draft.digest,
                content_digest=draft.content_digest,
                support_item_ids=[item.support_id for item in draft.support_sections],
                artifact_path=str(draft_path),
            ))
        else:
            status = (
                SupportStatus.INVALID_REJECTED
                if invalid_expected_artifact
                else SupportStatus.OPTIONAL_UNAVAILABLE
            )
            manifests.append(PhaseSupportManifestEntry(
                phase_id=phase.id, phase_sequence=phase.sequence,
                requirement=requirement, status=status, reason=reason,
                warnings=rejected or [
                    "Optional teacher support is unavailable; publisher content remains usable."
                ],
            ))
    return manifests, resolved


__all__ = [
    "ExpectedPhaseSupportIdentity", "SUPPORT_POLICY_VERSION",
    "resolve_phase_support", "support_policy",
]
