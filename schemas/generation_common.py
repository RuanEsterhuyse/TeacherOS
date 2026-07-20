"""Shared, source-conscious generation primitives."""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    citation: str = Field(min_length=1)
    source_type: str = "teacher_guide"


class Finding(BaseModel):
    text: str = Field(min_length=1)
    source_references: list[str] = Field(default_factory=list)
    is_inference: bool = False


class GenerationMetadata(BaseModel):
    request_id: str
    model: str
    attribution: str
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    total_tokens: Optional[int] = Field(default=None, ge=0)


class ValidationFinding(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    slide_id: Optional[str] = None
