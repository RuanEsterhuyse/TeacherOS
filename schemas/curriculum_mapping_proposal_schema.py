"""Review-only curriculum resource assignment proposals."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposalStatus(str, Enum):
    DETERMINISTICALLY_VERIFIED = "deterministically_verified"
    HUMAN_REVIEWED_OVERRIDE = "human_reviewed_override"
    PROPOSED_FOR_REVIEW = "proposed_for_review"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class MappingEvidence(StrictModel):
    teacher_guide_pdf_page: int = Field(ge=0)
    teacher_guide_printed_page: Optional[str] = None
    exact_reference_text: str = Field(min_length=1)
    source_heading: Optional[str] = None
    beginning_excerpt: Optional[str] = None
    ending_excerpt: Optional[str] = None
    evidence_notes: list[str] = Field(default_factory=list)


class ResourceAssignmentProposal(StrictModel):
    assignment_id: str = Field(min_length=1)
    unit_number: int = Field(ge=1)
    lesson_number: int = Field(ge=1)
    resource_role: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    curriculum_reference: str = Field(min_length=1)
    title_or_label: str = Field(min_length=1)
    referenced_printed_pages: list[str] = Field(default_factory=list)
    resolved_resource_id: Optional[str] = None
    proposed_pdf_start_page: Optional[int] = Field(default=None, ge=0)
    proposed_pdf_end_page: Optional[int] = Field(default=None, ge=0)
    resolution_method: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    verification_status: ProposalStatus
    evidence: list[MappingEvidence] = Field(min_length=1)
    ambiguity_notes: list[str] = Field(default_factory=list)
    human_review_required: bool
    reviewer_note: Optional[str] = None

    @model_validator(mode="after")
    def status_is_consistent(self) -> "ResourceAssignmentProposal":
        if (
            self.proposed_pdf_start_page is None
        ) != (self.proposed_pdf_end_page is None):
            raise ValueError("A proposed PDF range requires both endpoints.")
        if (
            self.proposed_pdf_start_page is not None
            and self.proposed_pdf_end_page < self.proposed_pdf_start_page
        ):
            raise ValueError("Proposed PDF range is reversed.")
        if (
            self.verification_status == ProposalStatus.PROPOSED_FOR_REVIEW
            and not self.human_review_required
        ):
            raise ValueError("Proposed mappings must require human review.")
        if (
            self.verification_status == ProposalStatus.DETERMINISTICALLY_VERIFIED
            and self.human_review_required
        ):
            raise ValueError("Deterministic mappings cannot require approval.")
        if self.verification_status == ProposalStatus.HUMAN_REVIEWED_OVERRIDE:
            if self.human_review_required:
                raise ValueError("Reviewed mappings cannot require approval.")
            if not self.reviewer_note:
                raise ValueError("Reviewed mappings require a reviewer note.")
        return self


class LessonResourceMappingManifest(StrictModel):
    curriculum: str = Field(min_length=1)
    grade: str = Field(min_length=1)
    unit_number: int = Field(ge=1)
    lesson_number: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    teacher_guide_resource_id: str = Field(min_length=1)
    teacher_guide_pdf_start_page: int = Field(ge=0)
    teacher_guide_pdf_end_page: int = Field(ge=0)
    teacher_guide_printed_start_page: Optional[int] = Field(default=None, ge=1)
    teacher_guide_printed_end_page: Optional[int] = Field(default=None, ge=1)
    assignments: list[ResourceAssignmentProposal] = Field(min_length=1)
    unresolved_references: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    schema_version: str = "1.0"
    builder_version: str = "1.0"


__all__ = [
    "LessonResourceMappingManifest", "MappingEvidence", "ProposalStatus",
    "ResourceAssignmentProposal",
]
