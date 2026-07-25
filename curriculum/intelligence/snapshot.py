"""Deterministic JSON snapshots and readiness inspector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from schemas.curriculum_intelligence_schema import (
    CurriculumLesson,
    ReadinessReport,
    ResourceAssignment,
    SourceCoordinateMapping,
)


def _payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _payload(item) for key, item in value.items()}
    return value


def write_json(path: str | Path, value: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            _payload(value),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def readiness_markdown(
    lesson: CurriculumLesson,
    resources: list,
    assignments: list[ResourceAssignment],
    report: ReadinessReport,
    coordinate_mappings: list[SourceCoordinateMapping] | None = None,
) -> str:
    coordinate_mappings = coordinate_mappings or []
    mappings_by_id = {value.id: value for value in coordinate_mappings}
    lines = [
        f"# Curriculum Source Readiness: {lesson.title}",
        "",
        f"- Lesson ID: `{lesson.id}`",
        f"- State: **{report.state.value}**",
        "- Achieved states: "
        + ", ".join(value.value for value in report.achieved_states),
        (
            "- Required assignments resolved: "
            f"{report.resolved_required_assignment_count}/"
            f"{report.required_assignment_count}"
        ),
        "",
        "## Registered Resources",
        "",
    ]
    lines.extend(
        f"- **{resource.title}** — {resource.resource_type}; "
        f"{resource.page_count} PDF pages; "
        f"{resource.extraction_status.value}; `{resource.id}`"
        for resource in resources
    )
    lines.extend(["", "## Assignments", ""])
    for item in assignments:
        coordinates = []
        if item.pdf_page_numbers:
            coordinates.append(
                "PDF zero-based " + ", ".join(map(str, item.pdf_page_numbers))
            )
        if item.display_page_numbers:
            coordinates.append(
                "PDF display " + ", ".join(map(str, item.display_page_numbers))
            )
        if item.printed_page_references:
            coordinates.append(
                "printed " + ", ".join(item.printed_page_references)
            )
        if item.document_labels:
            coordinates.append(
                "document label " + ", ".join(item.document_labels)
            )
        if item.story_relative_page_references:
            coordinates.append(
                "story-relative "
                + ", ".join(item.story_relative_page_references)
            )
        if item.section_references:
            coordinates.append(
                "section " + ", ".join(item.section_references)
            )
        lines.extend([
            f"### {item.title}",
            f"- Status: **{item.resolution_status.value}**",
            f"- Type: {item.assignment_type}",
            f"- Requirement: {item.required_status}",
            f"- Confidence: {item.confidence:.2f}",
            "- Coordinates: " + ("; ".join(coordinates) or "unresolved"),
            "- Segments: "
            + (", ".join(f"`{value}`" for value in item.segment_ids) or "none"),
            "- Coordinate mappings: "
            + (
                ", ".join(
                    f"`{mapping_id}` "
                    f"({mappings_by_id[mapping_id].mapping_method.value}, "
                    f"{mappings_by_id[mapping_id].review_status.value})"
                    for mapping_id in item.coordinate_mapping_ids
                    if mapping_id in mappings_by_id
                )
                or "none"
            ),
            "- Warnings: "
            + ("; ".join(item.warnings) if item.warnings else "none"),
            "",
        ])
    lines.extend(["## Verified Coordinate Overrides", ""])
    verified_mappings = [
        value
        for value in coordinate_mappings
        if value.review_status.value == "verified"
    ]
    assignments_by_id = {value.id: value for value in assignments}
    for mapping in verified_mappings:
        assignment = assignments_by_id.get(mapping.assignment_id)
        assignment_title = (
            assignment.title if assignment is not None else mapping.assignment_id
        )
        lines.extend([
            f"### {assignment_title}",
            (
                f"- Curriculum reference: {mapping.reference_system} "
                f"`{mapping.reference_value}`"
            ),
            (
                "- PDF range: zero-based "
                f"{mapping.target_pdf_start_page}–"
                f"{mapping.target_pdf_end_page}; display "
                f"{mapping.target_display_start_page}–"
                f"{mapping.target_display_end_page}"
            ),
            "- Segment range: "
            + " → ".join(f"`{value}`" for value in mapping.target_segment_ids),
            f"- Mapping method: {mapping.mapping_method.value}",
            f"- Review state: {mapping.review_status.value}",
            f"- Reviewer note: {mapping.reviewer_note}",
            "- Warnings: "
            + ("; ".join(mapping.warnings) if mapping.warnings else "none"),
            "",
        ])
    if not verified_mappings:
        lines.extend(["- None.", ""])
    assessment_assignments = [
        item
        for item in assignments
        if item.assignment_type in {"assessment", "exit_ticket"}
    ]
    lines.extend(["## Assessment and Exit Sources", ""])
    if assessment_assignments:
        lines.extend(f"- {item.title}" for item in assessment_assignments)
    else:
        lines.append(
            "- No explicit assessment-book or exit-ticket source assignment "
            "was identified for this lesson."
        )
    lines.append("")
    lines.extend(["## Blockers", ""])
    lines.extend(
        f"- **{item.code}**: {item.message}" for item in report.blockers
    )
    if not report.blockers:
        lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    lines.extend(
        f"- **{item.code}**: {item.message}" for item in report.warnings
    )
    if not report.warnings:
        lines.append("- None.")
    return "\n".join(lines).strip() + "\n"


__all__ = ["readiness_markdown", "write_json"]
