"""Curriculum Analyzer structured output."""

from pydantic import BaseModel, Field
from schemas.generation_common import Finding


class CurriculumAnalyzerOutput(BaseModel):
    request_id: str
    central_learning_goal: Finding
    supporting_goals: list[Finding] = Field(default_factory=list)
    prerequisite_knowledge: list[Finding] = Field(default_factory=list)
    instructional_sequence: list[Finding] = Field(default_factory=list)
    likely_misconceptions: list[Finding] = Field(default_factory=list)
    cognitive_demands: list[Finding] = Field(default_factory=list)
    vocabulary_demands: list[Finding] = Field(default_factory=list)
    discussion_demands: list[Finding] = Field(default_factory=list)
    assessment_opportunities: list[Finding] = Field(default_factory=list)
    essential_content: list[Finding] = Field(default_factory=list)
    optional_content: list[Finding] = Field(default_factory=list)
    timing_conflicts: list[str] = Field(default_factory=list)
    fidelity_risks: list[str] = Field(default_factory=list)
