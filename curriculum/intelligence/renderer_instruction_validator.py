"""Validation for provider-neutral renderer instruction packages."""

from __future__ import annotations

from collections import Counter

from curriculum.intelligence.ids import content_digest
from schemas.presentation_spec_schema import (
    ApprovalStatus,
    ContentElementType,
    PresentationSpec,
    PresentationValidationIssue,
    SlideType,
    ValidationSeverity,
    ValidationStatus,
)
from schemas.renderer_instruction_schema import (
    InstructionLayout,
    RendererInstructionPackage,
    RendererInstructionValidationReport,
)


EXPECTED_LAYOUTS = {
    "title": "title",
    "agenda": "agenda",
    "essential_question": "essential_question",
    "learning_objectives": "objectives_cards",
    "background_knowledge": "concept_web",
    "vocabulary": "vocabulary_cards",
    "map_or_geography": "map_focus",
    "identity_or_concept": "concept_web",
    "author_or_text_preview": "title_with_visual",
    "windows_and_mirrors": "comparison",
    "reading_purpose": "reading_chunk",
    "reading_chunk": "reading_chunk",
    "reading_checkpoint": "reading_checkpoint",
    "discussion": "discussion_prompt",
    "theme_analysis": "comparison",
    "text_evidence": "evidence_analysis",
    "activity_book": "two_column",
    "writing_task": "two_column",
    "grammar": "two_column",
    "morphology": "three_card",
    "reflection": "reflection",
    "exit_ticket": "exit_ticket",
    "homework": "homework",
    "teacher_only": "teacher_only",
}


def _reference_key(value) -> str:
    return content_digest(value.model_dump(mode="json"))


def _source_element_text(element) -> str:
    if element.text:
        return element.text
    if element.items:
        marker = (
            "1."
            if element.element_type == ContentElementType.numbered_list
            else "•"
        )
        return "\n".join(f"{marker} {item}" for item in element.items)
    return "\n".join(" | ".join(row) for row in element.table_rows)


def validate_renderer_instruction_package(
    package: RendererInstructionPackage,
    presentation_spec: PresentationSpec,
) -> RendererInstructionValidationReport:
    """Validate exact association, coverage, layout, notes, assets, and bounds."""
    issues: list[PresentationValidationIssue] = []
    if presentation_spec.approval_status != ApprovalStatus.approved:
        issues.append(PresentationValidationIssue(
            code="unapproved_presentation_spec",
            severity=ValidationSeverity.error,
            message="Renderer input PresentationSpec is not approved.",
        ))
    if presentation_spec.validation_status not in {
        ValidationStatus.passed,
        ValidationStatus.passed_with_warnings,
    }:
        issues.append(PresentationValidationIssue(
            code="invalid_presentation_spec",
            severity=ValidationSeverity.error,
            message="Renderer input PresentationSpec is not valid.",
        ))
    for actual, expected, field in (
        (package.presentation_id, presentation_spec.presentation_id,
         "presentation_id"),
        (package.playbook_id, presentation_spec.playbook_id, "playbook_id"),
        (package.source_id, presentation_spec.source_id, "source_id"),
    ):
        if actual != expected:
            issues.append(PresentationValidationIssue(
                code="renderer_association_mismatch",
                severity=ValidationSeverity.error,
                message=f"{field} does not match the approved PresentationSpec.",
            ))

    expected_ids = [slide.slide_id for slide in presentation_spec.slides]
    actual_ids = [slide.slide_id for slide in package.slides]
    if actual_ids != expected_ids:
        issues.append(PresentationValidationIssue(
            code="slide_order_or_count_mismatch",
            severity=ValidationSeverity.error,
            message="Renderer instructions must preserve exact slide order and count.",
        ))
    if Counter(actual_ids) != Counter(expected_ids):
        issues.append(PresentationValidationIssue(
            code="slide_coverage_mismatch",
            severity=ValidationSeverity.error,
            message="Every source slide must be represented exactly once.",
        ))

    source_by_id = {
        slide.slide_id: slide for slide in presentation_spec.slides
    }
    known_references = {
        _reference_key(reference)
        for slide in presentation_spec.slides
        for reference in (
            slide.source_references
            + slide.speaker_notes.source_references
            + [
                element.source_reference
                for element in slide.student_facing_content
                if element.source_reference is not None
            ]
            + (
                [slide.visual_spec.source_reference]
                if slide.visual_spec
                and slide.visual_spec.source_reference is not None
                else []
            )
        )
    }
    represented_elements: set[str] = set()
    block_ids: set[str] = set()
    for slide in package.slides:
        source = source_by_id.get(slide.slide_id)
        if source is None:
            continue
        expected_layout = EXPECTED_LAYOUTS[source.slide_type.value]
        if slide.layout_type.value != expected_layout:
            issues.append(PresentationValidationIssue(
                code="invalid_layout_for_slide_type",
                severity=ValidationSeverity.error,
                message=(
                    f"{source.slide_type.value} requires layout {expected_layout}."
                ),
                slide_id=slide.slide_id,
            ))
        if slide.slide_number != source.slide_number:
            issues.append(PresentationValidationIssue(
                code="slide_number_mismatch",
                severity=ValidationSeverity.error,
                message="Renderer slide number differs from source.",
                slide_id=slide.slide_id,
            ))
        if slide.timing != source.estimated_minutes:
            issues.append(PresentationValidationIssue(
                code="timing_not_preserved",
                severity=ValidationSeverity.error,
                message="Renderer slide timing differs from source.",
                slide_id=slide.slide_id,
            ))
        if not slide.text_blocks:
            issues.append(PresentationValidationIssue(
                code="missing_required_text_block",
                severity=ValidationSeverity.error,
                message="Renderer slide has no title text block.",
                slide_id=slide.slide_id,
            ))
        elif not slide.text_blocks[0].text.strip():
            issues.append(PresentationValidationIssue(
                code="empty_required_text",
                severity=ValidationSeverity.error,
                message="Renderer title text is empty.",
                slide_id=slide.slide_id,
            ))
        expected_elements = {
            element.element_id for element in source.student_facing_content
        }
        actual_element_counts = Counter(slide.source_content_element_ids)
        actual_elements = set(actual_element_counts)
        if (
            actual_elements != expected_elements
            or any(count != 1 for count in actual_element_counts.values())
        ):
            issues.append(PresentationValidationIssue(
                code="required_content_loss",
                severity=ValidationSeverity.error,
                message="Student-facing source elements were dropped or invented.",
                slide_id=slide.slide_id,
            ))
        represented_elements.update(actual_elements)
        source_elements = {
            element.element_id: element
            for element in source.student_facing_content
        }
        rendered_element_counts: Counter[str] = Counter()
        for block in slide.text_blocks:
            if block.block_id in block_ids:
                issues.append(PresentationValidationIssue(
                    code="duplicate_block_id",
                    severity=ValidationSeverity.error,
                    message="Renderer block IDs must be unique.",
                    slide_id=slide.slide_id,
                ))
            block_ids.add(block.block_id)
            if (
                block.source_element_id is not None
                and block.source_element_id not in expected_elements
            ):
                issues.append(PresentationValidationIssue(
                    code="orphan_text_block",
                    severity=ValidationSeverity.error,
                    message="Text block references an unknown source element.",
                    slide_id=slide.slide_id,
                ))
            elif block.source_element_id is not None:
                rendered_element_counts[block.source_element_id] += 1
                if block.text != _source_element_text(
                    source_elements[block.source_element_id]
                ):
                    issues.append(PresentationValidationIssue(
                        code="source_text_mutated",
                        severity=ValidationSeverity.error,
                        message="Renderer text differs from its source element.",
                        slide_id=slide.slide_id,
                    ))
            if (
                block.source_reference is not None
                and _reference_key(block.source_reference)
                not in known_references
            ):
                issues.append(PresentationValidationIssue(
                    code="unsupported_source_reference",
                    severity=ValidationSeverity.error,
                    message="Text block introduced an unsupported source reference.",
                    slide_id=slide.slide_id,
                ))
        if (
            rendered_element_counts
            != Counter({element_id: 1 for element_id in expected_elements})
        ):
            issues.append(PresentationValidationIssue(
                code="source_element_block_coverage_mismatch",
                severity=ValidationSeverity.error,
                message="Every source content element requires exactly one block.",
                slide_id=slide.slide_id,
            ))
        if slide.text_blocks and slide.text_blocks[0].text != source.title:
            issues.append(PresentationValidationIssue(
                code="slide_title_mutated",
                severity=ValidationSeverity.error,
                message="Renderer title differs from the source slide title.",
                slide_id=slide.slide_id,
            ))
        for block in slide.visual_blocks:
            if block.block_id in block_ids:
                issues.append(PresentationValidationIssue(
                    code="duplicate_block_id",
                    severity=ValidationSeverity.error,
                    message="Renderer block IDs must be unique.",
                    slide_id=slide.slide_id,
                ))
            block_ids.add(block.block_id)
            if not block.decorative and not block.alt_text:
                issues.append(PresentationValidationIssue(
                    code="missing_visual_alt_text",
                    severity=ValidationSeverity.error,
                    message="Meaningful visual is missing alt text.",
                    slide_id=slide.slide_id,
                ))
            if (
                block.source_reference is not None
                and _reference_key(block.source_reference)
                not in known_references
            ):
                issues.append(PresentationValidationIssue(
                    code="unsupported_source_reference",
                    severity=ValidationSeverity.error,
                    message="Visual block introduced an unsupported source reference.",
                    slide_id=slide.slide_id,
                ))
        notes = slide.notes_payload
        source_notes = source.speaker_notes
        if source.notes_required and not notes.plain_text_fallback:
            issues.append(PresentationValidationIssue(
                code="missing_required_notes",
                severity=ValidationSeverity.error,
                message="Required notes fallback is empty.",
                slide_id=slide.slide_id,
            ))
        if (
            notes.purpose != source_notes.purpose
            or notes.teacher_script != source_notes.teacher_script
            or notes.teacher_actions != source_notes.teacher_actions
            or notes.anticipated_responses
            != source_notes.anticipated_responses
            or notes.misconception_support
            != source_notes.misconception_support
            or notes.checks_for_understanding
            != source_notes.checks_for_understanding
            or notes.transition_language != source_notes.transition_language
            or notes.pacing_notes != source_notes.pacing_notes
            or notes.source_references != source_notes.source_references
            or notes.grounding_labels != source_notes.grounding_labels
        ):
            issues.append(PresentationValidationIssue(
                code="notes_content_not_preserved",
                severity=ValidationSeverity.error,
                message="Speaker-note instructional content changed.",
                slide_id=slide.slide_id,
            ))
        if (
            slide.source_references != source.source_references
            or slide.grounding_labels != source.grounding_labels
        ):
            issues.append(PresentationValidationIssue(
                code="slide_grounding_not_preserved",
                severity=ValidationSeverity.error,
                message="Slide source references or grounding labels changed.",
                slide_id=slide.slide_id,
            ))
        for rectangle in [
            *slide.text_blocks,
            *slide.visual_blocks,
        ]:
            if (
                rectangle.x + rectangle.width
                > package.canvas.width + 0.001
                or rectangle.y + rectangle.height
                > package.canvas.height + 0.001
            ):
                issues.append(PresentationValidationIssue(
                    code="block_outside_canvas",
                    severity=ValidationSeverity.error,
                    message="Renderer block exceeds canvas bounds.",
                    slide_id=slide.slide_id,
                ))

    assets_by_slide = Counter(
        asset.slide_id for asset in package.asset_manifest
    )
    for asset in package.asset_manifest:
        if (
            asset.source_reference is not None
            and _reference_key(asset.source_reference)
            not in known_references
        ):
            issues.append(PresentationValidationIssue(
                code="unsupported_source_reference",
                severity=ValidationSeverity.error,
                message="Asset manifest introduced an unsupported source reference.",
                slide_id=asset.slide_id,
            ))
    for slide in package.slides:
        if assets_by_slide[slide.slide_id] != 1:
            issues.append(PresentationValidationIssue(
                code="missing_asset_manifest_entry",
                severity=ValidationSeverity.error,
                message="Each slide requires exactly one asset-manifest disposition.",
                slide_id=slide.slide_id,
            ))
    if set(assets_by_slide) - set(actual_ids):
        issues.append(PresentationValidationIssue(
            code="orphan_asset_manifest_entry",
            severity=ValidationSeverity.error,
            message="Asset manifest references an unknown slide.",
        ))

    if package.canvas.width <= 0 or package.canvas.height <= 0:
        issues.append(PresentationValidationIssue(
            code="invalid_canvas",
            severity=ValidationSeverity.error,
            message="Canvas dimensions must be positive.",
        ))
    if (
        not package.theme.background_colors
        or not package.theme.heading_color
        or not package.theme.body_color
        or not package.theme.accent_colors
    ):
        issues.append(PresentationValidationIssue(
            code="invalid_theme_tokens",
            severity=ValidationSeverity.error,
            message="Compiled theme tokens are incomplete.",
        ))
    contract_layouts = {value.layout for value in package.layout_contracts}
    if contract_layouts != set(InstructionLayout):
        issues.append(PresentationValidationIssue(
            code="incomplete_layout_contract",
            severity=ValidationSeverity.error,
            message="The package must include every named layout contract.",
        ))

    errors = [
        issue for issue in issues
        if issue.severity == ValidationSeverity.error
    ]
    warnings = [
        issue for issue in issues
        if issue.severity == ValidationSeverity.warning
    ]
    status = (
        ValidationStatus.failed if errors
        else ValidationStatus.passed_with_warnings if warnings
        else ValidationStatus.passed
    )
    return RendererInstructionValidationReport(
        status=status,
        valid=not errors,
        issues=issues,
        expected_slide_count=len(presentation_spec.slides),
        represented_slide_count=len(package.slides),
        source_content_block_count=sum(
            len(slide.student_facing_content)
            for slide in presentation_spec.slides
        ),
        represented_content_block_count=len(represented_elements),
    )


__all__ = ["EXPECTED_LAYOUTS", "validate_renderer_instruction_package"]
