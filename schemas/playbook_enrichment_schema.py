"""Strict contracts for optional, source-grounded playbook enrichment."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field, model_validator

from schemas.pasted_lesson_schema import (
    AnalysisWarning,
    PlaybookAnalysisResult,
    PastedLessonSource,
    SourceReference,
    StrictModel,
    TeacherPlaybook,
    utc_now,
)


PLAYBOOK_ENRICHMENT_SCHEMA_VERSION = "1.0"
PLAYBOOK_ENRICHMENT_VERSION = "teacher-playbook-enrichment-v1"
GENERATED_GUIDANCE_LABEL = "[Generated guidance — review]"


class DetailLevel(str, Enum):
    focused = "focused"
    comprehensive = "comprehensive"


class EnrichmentStatus(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


class TeacherApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class PlaybookEnrichmentOptions(StrictModel):
    detail_level: DetailLevel = DetailLevel.comprehensive
    include_teacher_scripts: bool = True
    include_possible_student_responses: bool = True
    include_misconceptions: bool = True
    include_eld_supports: bool = True
    include_checks_for_understanding: bool = True
    include_transition_language: bool = True
    include_teacher_reflection: bool = True
    preserve_original_wording: bool = True
    strict_grounding: bool = True


class PlaybookEnrichmentContext(StrictModel):
    source: PastedLessonSource
    baseline: PlaybookAnalysisResult
    options: PlaybookEnrichmentOptions


class GeneratedPlaybookEnrichment(StrictModel):
    enriched_playbook: TeacherPlaybook
    source_backed_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    omitted_unsupported_fields: list[str] = Field(default_factory=list)


class ProviderMetadata(StrictModel):
    provider_name: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    usage: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)


class UnsupportedClaim(StrictModel):
    field_path: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    action: str = "rejected"


class ActivitySourceCoverage(StrictModel):
    activity_id: str = Field(min_length=1)
    retained_source_references: list[SourceReference] = Field(
        default_factory=list
    )
    baseline_reference_count: int = Field(ge=0)
    retained_reference_count: int = Field(ge=0)
    fully_retained: bool


class GroundingReport(StrictModel):
    source_backed_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    omitted_unsupported_fields: list[str] = Field(default_factory=list)
    retained_source_references: list[SourceReference] = Field(
        default_factory=list
    )
    added_teacher_guidance: list[str] = Field(default_factory=list)
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    unsupported_claims_rejected: list[UnsupportedClaim] = Field(
        default_factory=list
    )
    source_coverage_by_activity: list[ActivitySourceCoverage] = Field(
        default_factory=list
    )


class PlaybookEnrichmentResult(StrictModel):
    enrichment_id: str = Field(min_length=1)
    status: EnrichmentStatus
    enriched_playbook: TeacherPlaybook
    grounding_report: GroundingReport
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    unsupported_claims: list[UnsupportedClaim] = Field(default_factory=list)
    source_coverage: list[ActivitySourceCoverage] = Field(default_factory=list)
    provider_metadata: Optional[ProviderMetadata] = None
    enrichment_version: str = PLAYBOOK_ENRICHMENT_VERSION
    baseline_preserved: bool = False
    failure_reason: Optional[str] = None


class ApprovedPlaybookEnrichment(StrictModel):
    enrichment_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    baseline_analyzer_version: str = Field(min_length=1)
    enrichment_version: str = PLAYBOOK_ENRICHMENT_VERSION
    enriched_playbook: TeacherPlaybook
    provider_metadata: ProviderMetadata
    generated_at: datetime = Field(default_factory=utc_now)
    grounding_summary: GroundingReport
    teacher_approval_status: TeacherApprovalStatus
    approved_at: Optional[datetime] = None
    schema_version: str = PLAYBOOK_ENRICHMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_approval(self) -> "ApprovedPlaybookEnrichment":
        if self.teacher_approval_status == TeacherApprovalStatus.approved:
            if self.approved_at is None:
                raise ValueError("Approved enrichments require approved_at.")
        return self


__all__ = [
    "ActivitySourceCoverage",
    "ApprovedPlaybookEnrichment",
    "DetailLevel",
    "EnrichmentStatus",
    "GENERATED_GUIDANCE_LABEL",
    "GeneratedPlaybookEnrichment",
    "GroundingReport",
    "PLAYBOOK_ENRICHMENT_SCHEMA_VERSION",
    "PLAYBOOK_ENRICHMENT_VERSION",
    "PlaybookEnrichmentContext",
    "PlaybookEnrichmentOptions",
    "PlaybookEnrichmentResult",
    "ProviderMetadata",
    "TeacherApprovalStatus",
    "UnsupportedClaim",
]
