"""Renderer-ready Lesson Package contract."""

from typing import Optional
from pydantic import BaseModel, Field, model_validator
from schemas.generation_common import GenerationMetadata
from schemas.slide_specification_schema import SlideSpecificationItem

CKLA_ATTRIBUTION = ("This work is based on an original work of the Core Knowledge Foundation made available "
    "under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. This does not "
    "imply endorsement by the Core Knowledge Foundation.")


class LessonPackageMetadata(BaseModel):
    title: str
    grade: str
    unit: str
    lesson_number: int = Field(ge=1)
    curriculum_name: str = "CKLA"
    objectives: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    attribution: str


class PackageVocabulary(BaseModel):
    term: str
    definition: str
    context: Optional[str] = None


class PackageActivity(BaseModel):
    activity_id: str
    title: str
    instructions: str
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    interaction: Optional[str] = None


class PackageAssessment(BaseModel):
    title: str
    assessment_type: str
    instructions: str
    success_criteria: list[str] = Field(default_factory=list)


class PackageHomework(BaseModel):
    title: str
    instructions: str


class LessonPackage(BaseModel):
    package_id: str
    lesson_metadata: LessonPackageMetadata
    lesson_overview: str = ""
    total_timing: int = Field(ge=0)
    materials: list[str] = Field(default_factory=list)
    vocabulary: list[PackageVocabulary] = Field(default_factory=list)
    slide_order: list[str]
    slides: list[SlideSpecificationItem]
    homework: list[PackageHomework] = Field(default_factory=list)
    activities: list[PackageActivity] = Field(default_factory=list)
    assessments: list[PackageAssessment] = Field(default_factory=list)
    activity_references: list[str] = Field(default_factory=list)
    reader_references: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    unresolved_warnings: list[str] = Field(default_factory=list)
    generation_metadata: GenerationMetadata

    @model_validator(mode="after")
    def package_consistency(self):
        ids = [slide.slide_id for slide in self.slides]
        if self.slide_order != ids:
            raise ValueError("slide_order must exactly match slides")
        if len(ids) != len(set(ids)):
            raise ValueError("slide IDs must be unique")
        if self.lesson_metadata.curriculum_name == "CKLA" and self.lesson_metadata.attribution != CKLA_ATTRIBUTION:
            raise ValueError("CKLA attribution statement is missing or altered")
        return self
