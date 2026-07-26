"""Teacher-readable, source-grounded lesson intelligence contracts."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContentClassification(str, Enum):
    PUBLISHER_SOURCE = "publisher_source"
    TEACHEROS_INTERPRETATION = "teacheros_interpretation"
    TEACHEROS_AI_SUPPORT = "teacheros_ai_support"
    SOURCE_LIMITATION = "source_limitation"


class AnswerProvenanceStatus(str, Enum):
    SAME_SECTION = "publisher_answer_same_section"
    ELSEWHERE = "publisher_answer_elsewhere_in_guide"
    GUIDANCE = "publisher_guidance_not_full_answer"
    NOT_LOCATED = "publisher_answer_not_located"
    TEACHEROS = "teacheros_suggested_response"


class PackageCitation(StrictModel):
    resource_id: str
    source_document: str
    pdf_page_number: int = Field(ge=0)
    display_page_number: int = Field(ge=1)
    printed_page: Optional[str] = None
    stable_source_id: str
    match_evidence: list[str] = Field(default_factory=list)


class ClassifiedContent(StrictModel):
    text: str
    classification: ContentClassification
    citations: list[PackageCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def publisher_content_has_provenance(self) -> "ClassifiedContent":
        if (
            self.classification == ContentClassification.PUBLISHER_SOURCE
            and not self.citations
        ):
            raise ValueError("Publisher content requires page provenance.")
        return self


class ObjectiveGuide(StrictModel):
    objective_id: str
    publisher_objective: ClassifiedContent
    student_friendly_interpretation: ClassifiedContent
    evidence_of_mastery: ClassifiedContent
    phase_ids: list[str]


class LanguageDemand(StrictModel):
    phase_id: str
    language_function: str
    language_domain: str
    language_forms: list[str]
    likely_eld_difficulty: str
    supports: list[str]
    classification: ContentClassification = ContentClassification.TEACHEROS_INTERPRETATION


class VocabularyGuideEntry(StrictModel):
    word: str
    publisher_definition: Optional[ClassifiedContent] = None
    student_friendly_explanation: ClassifiedContent
    example: ClassifiedContent
    non_example: Optional[ClassifiedContent] = None
    morphology: Optional[ClassifiedContent] = None
    pronunciation: Optional[str] = None
    misconception: str
    eld_support: str
    visual_suggestion: str


class PhaseGuide(StrictModel):
    phase_id: str
    sequence: int
    title: str
    duration_minutes: Optional[int]
    purpose: ClassifiedContent
    teacher_actions: list[ClassifiedContent]
    student_actions: list[ClassifiedContent]
    materials: list[str]
    source_pages: list[PackageCitation]
    transition_in: ClassifiedContent
    watch_for: ClassifiedContent
    check_for_understanding: ClassifiedContent
    differentiation: list[ClassifiedContent]
    language_support: ClassifiedContent
    transition_out: ClassifiedContent


class QuestionGuideItem(StrictModel):
    question_id: str
    sequence: int
    phase_id: str
    question: ClassifiedContent
    interaction_format: str
    publisher_answer: Optional[ClassifiedContent] = None
    answer_provenance_status: AnswerProvenanceStatus
    teacheros_suggested_response: Optional[ClassifiedContent] = None
    teacher_explanation: ClassifiedContent
    support_rationale: ClassifiedContent
    text_evidence: Optional[ClassifiedContent] = None
    likely_incomplete_responses: list[str]
    misconception: str
    follow_up: str
    check_for_understanding: str
    sentence_frame: str
    differentiation_or_extension: str


class ActivityGuide(StrictModel):
    assignment_id: str
    name: str
    purpose: ClassifiedContent
    teacher_directions: ClassifiedContent
    student_task: ClassifiedContent
    expected_product: ClassifiedContent
    publisher_guidance: Optional[ClassifiedContent] = None
    common_difficulty: str
    language_support: str
    completion_check: str
    citations: list[PackageCitation]


class ReadingGuide(StrictModel):
    assignment_id: str
    title: str
    page_reference: str
    purpose: ClassifiedContent
    verified_summary: Optional[ClassifiedContent] = None
    important_ideas: list[ClassifiedContent]
    comprehension_difficulties: list[str]
    pause_points: list[str]
    think_alouds: list[ClassifiedContent]
    text_evidence_to_notice: list[ClassifiedContent]
    vocabulary_in_context: list[str]
    eld_scaffolds: list[str]
    source_available: bool
    limitations: list[ClassifiedContent]
    citations: list[PackageCitation]


class SlidePromptSpecification(StrictModel):
    slide_number: int
    title: str
    student_facing_content: list[str]
    teacher_notes: list[str]
    purpose: str
    question_ids: list[str]
    answer_guidance: list[str]
    visual_recommendation: str
    interaction_format: str
    provenance_references: list[str]


class LessonIdentity(StrictModel):
    curriculum_program: str
    grade: str
    unit: str
    lesson_number: int
    lesson_title: str
    estimated_duration_minutes: int
    source_document_identity: str
    source_page_range: str


class LessonIntelligencePackage(StrictModel):
    identity: LessonIdentity
    generated_at: str
    bundle_digest: str
    canonical_source_digest: str
    instruction_plan_digest: str
    relationship_graph_digest: str
    package_digest: str
    lesson_at_a_glance: list[ClassifiedContent]
    objectives: list[ObjectiveGuide]
    standards: list[ClassifiedContent]
    language_demands: list[LanguageDemand]
    before_you_teach: list[ClassifiedContent]
    vocabulary: list[VocabularyGuideEntry]
    phases: list[PhaseGuide]
    reading_guides: list[ReadingGuide]
    questions: list[QuestionGuideItem]
    activities: list[ActivityGuide]
    discussion_facilitation: list[ClassifiedContent]
    differentiation_and_eld: dict[str, list[ClassifiedContent]]
    checks_for_understanding: list[ClassifiedContent]
    assessment_and_evidence: list[ClassifiedContent]
    homework_and_closing: list[ClassifiedContent]
    teacher_preparation_checklist: dict[str, list[str]]
    provenance_index: list[PackageCitation]
    slide_specifications: list[SlidePromptSpecification]
    source_limitations: list[ClassifiedContent]
    cached_support_used: bool


__all__ = [
    "ActivityGuide", "AnswerProvenanceStatus", "ClassifiedContent",
    "ContentClassification", "LanguageDemand", "LessonIdentity",
    "LessonIntelligencePackage", "ObjectiveGuide", "PackageCitation",
    "PhaseGuide", "QuestionGuideItem", "ReadingGuide",
    "SlidePromptSpecification", "VocabularyGuideEntry",
]
