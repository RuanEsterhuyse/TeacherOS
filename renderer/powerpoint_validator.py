"""Structural validation for generated TeacherOS PowerPoint files."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from schemas.powerpoint_render_schema import (
    PowerPointRenderWarning,
    PowerPointValidationReport,
)
from schemas.renderer_instruction_schema import RendererInstructionPackage


def validate_powerpoint(
    path: Path,
    package: RendererInstructionPackage,
    manifest_path: Path,
) -> PowerPointValidationReport:
    issues: list[PowerPointRenderWarning] = []
    office_valid = path.is_file() and zipfile.is_zipfile(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    external: list[str] = []
    slide_xml_count = 0
    if office_valid:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            slide_xml_count = len([
                name for name in names
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ])
            for name in names:
                if name.endswith(".rels"):
                    text = archive.read(name).decode("utf-8", "replace")
                    if 'TargetMode="External"' in text:
                        external.append(name)
    else:
        issues.append(PowerPointRenderWarning(
            code="invalid_office_package",
            message="Generated output is not a valid Office ZIP package.",
        ))
    expected_ids = [slide.slide_id for slide in package.slides]
    rendered_ids = manifest.get("rendered_slide_ids", [])
    if slide_xml_count != len(package.slides):
        issues.append(PowerPointRenderWarning(
            code="slide_count_mismatch",
            message="Generated PPTX does not preserve the exact slide count.",
        ))
    if rendered_ids != expected_ids:
        issues.append(PowerPointRenderWarning(
            code="slide_order_mismatch",
            message="Generated PPTX does not preserve exact slide order.",
        ))
    if external:
        issues.append(PowerPointRenderWarning(
            code="external_relationship",
            message="Generated PPTX contains external file relationships.",
        ))
    expected_titles = [
        slide.text_blocks[0].text for slide in package.slides
    ]
    located_titles = [
        title for title in expected_titles
        if title in manifest.get("inspection", "")
    ]
    if located_titles != expected_titles:
        issues.append(PowerPointRenderWarning(
            code="missing_expected_title",
            message="One or more expected slide titles were not found.",
        ))
    if any(count < 4 for count in manifest.get("shape_counts", [])):
        issues.append(PowerPointRenderWarning(
            code="empty_required_slide",
            message="A generated slide has fewer than the required objects.",
        ))
    return PowerPointValidationReport(
        valid=not issues,
        issues=issues,
        expected_slide_count=len(package.slides),
        actual_slide_count=slide_xml_count,
        expected_slide_ids=expected_ids,
        rendered_slide_ids=rendered_ids,
        expected_titles=expected_titles,
        located_titles=located_titles,
        canvas_width_inches=package.canvas.width,
        canvas_height_inches=package.canvas.height,
        native_notes_verified=bool(manifest.get("notes_verified")),
        office_package_valid=office_valid,
        external_relationships=external,
    )


__all__ = ["validate_powerpoint"]
