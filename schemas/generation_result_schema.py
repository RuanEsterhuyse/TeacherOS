"""End-to-end generation and validation results."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from schemas.generation_common import ValidationFinding


class LessonValidationReport(BaseModel):
    status: Literal["pass", "pass_with_warnings", "fail"]
    findings: list[ValidationFinding] = Field(default_factory=list)
    timing_total_minutes: int = Field(ge=0)
    slide_count: int = Field(ge=0)


class GenerationResult(BaseModel):
    request_id: str
    status: Literal["completed", "completed_with_warnings", "failed", "dry_run"]
    output_directory: str
    completed_stages: list[str] = Field(default_factory=list)
    failed_stage: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    validation_result: Optional[Literal["pass", "pass_with_warnings", "fail"]] = None
    slide_count: int = 0
    lesson: Optional[Any] = None
