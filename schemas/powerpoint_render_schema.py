"""Strict contracts for isolated editable PowerPoint rendering."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from schemas.pasted_lesson_schema import StrictModel


POWERPOINT_RENDERER_VERSION = "powerpoint-instruction-renderer-v1"
POWERPOINT_RENDER_SCHEMA_VERSION = "1.0"


class PowerPointRenderStatus(str, Enum):
    complete = "complete"
    failed = "failed"


class NotesSupportStatus(str, Enum):
    native_verified = "native_verified"
    fallback_only = "fallback_only"


class PowerPointRenderOptions(StrictModel):
    filename: str = "teacheros_presentation.pptx"
    local_assets: dict[str, str] = Field(default_factory=dict)
    include_presenter_reference_footer: bool = False
    minimum_body_font_size: float = Field(default=16, ge=14)
    render_previews: bool = False


class PowerPointRenderWarning(StrictModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    slide_id: Optional[str] = None
    block_id: Optional[str] = None


class FontSubstitution(StrictModel):
    role: str = Field(min_length=1)
    requested: str = Field(min_length=1)
    rendered: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RenderedAsset(StrictModel):
    asset_id: str = Field(min_length=1)
    slide_id: str = Field(min_length=1)
    disposition: str = Field(min_length=1)
    local_path: Optional[str] = None
    file_digest: Optional[str] = None


class PowerPointValidationReport(StrictModel):
    valid: bool
    issues: list[PowerPointRenderWarning] = Field(default_factory=list)
    expected_slide_count: int = Field(ge=0)
    actual_slide_count: int = Field(ge=0)
    expected_slide_ids: list[str] = Field(default_factory=list)
    rendered_slide_ids: list[str] = Field(default_factory=list)
    expected_titles: list[str] = Field(default_factory=list)
    located_titles: list[str] = Field(default_factory=list)
    canvas_width_inches: float = Field(gt=0)
    canvas_height_inches: float = Field(gt=0)
    native_notes_verified: bool = False
    office_package_valid: bool = False
    external_relationships: list[str] = Field(default_factory=list)


class PowerPointRenderResult(StrictModel):
    render_id: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    notes_fallback_path: str = Field(min_length=1)
    preview_directory: Optional[str] = None
    presentation_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    slide_count: int = Field(ge=0)
    rendered_slide_ids: list[str] = Field(default_factory=list)
    warnings: list[PowerPointRenderWarning] = Field(default_factory=list)
    unsupported_features: list[PowerPointRenderWarning] = Field(
        default_factory=list
    )
    font_substitutions: list[FontSubstitution] = Field(default_factory=list)
    overflow_report: list[PowerPointRenderWarning] = Field(default_factory=list)
    asset_report: list[RenderedAsset] = Field(default_factory=list)
    validation_report: PowerPointValidationReport
    notes_support_status: NotesSupportStatus
    renderer_version: str = POWERPOINT_RENDERER_VERSION
    file_digest: str = Field(min_length=1)
    status: PowerPointRenderStatus = PowerPointRenderStatus.complete
    schema_version: str = POWERPOINT_RENDER_SCHEMA_VERSION


__all__ = [
    "FontSubstitution", "NotesSupportStatus",
    "POWERPOINT_RENDERER_VERSION", "POWERPOINT_RENDER_SCHEMA_VERSION",
    "PowerPointRenderOptions", "PowerPointRenderResult",
    "PowerPointRenderStatus", "PowerPointRenderWarning",
    "PowerPointValidationReport", "RenderedAsset",
]
