"""Human-readable formatting for curriculum mapping proposals."""

from schemas.curriculum_mapping_proposal_schema import (
    LessonResourceMappingManifest,
    ProposalStatus,
)


def lesson_mapping_review_markdown(
    manifest: LessonResourceMappingManifest,
) -> str:
    lines = [
        "# Lesson 2 Mapping Review", "",
        "## Lesson overview", "",
        f"- Curriculum: {manifest.curriculum}",
        f"- Grade: {manifest.grade}",
        f"- Unit: {manifest.unit_number}",
        f"- Lesson: {manifest.lesson_number} — {manifest.lesson_title}",
        "",
        "## Teacher Guide boundary", "",
        f"- PDF pages, zero-based: {manifest.teacher_guide_pdf_start_page}–{manifest.teacher_guide_pdf_end_page}",
        f"- Printed pages: {manifest.teacher_guide_printed_start_page}–{manifest.teacher_guide_printed_end_page}",
        "",
    ]
    sections = [
        ("## Proposed instructional-text assignments", {"assigned_reading", "prior_lesson_homework_review", "translation_reference", "refrane_reference", "story_notes"}),
        ("## Activity Book assignments", {"prior_lesson_activity_review", "vocabulary_resource", "homework_writing", "grammar_practice_and_homework", "writing_plan", "homework_writing_plan"}),
        ("## Proposed answer-key matches", {"prior_lesson_activity_answer_key", "publisher_answer_key"}),
        ("## Homework assignments", {"homework_writing", "grammar_practice_and_homework", "homework_writing_plan"}),
        ("## Online resources", {"online_teacher_resources", "classroom_map"}),
    ]
    for heading, roles in sections:
        lines += [heading, ""]
        selected = [
            item for item in manifest.assignments if item.resource_role in roles
        ]
        for item in selected:
            evidence = item.evidence[0]
            page_range = (
                f"{item.proposed_pdf_start_page}–{item.proposed_pdf_end_page}"
                if item.proposed_pdf_start_page is not None else "Unresolved"
            )
            lines += [
                f"### {item.title_or_label}", "",
                f"- Curriculum reference: {item.curriculum_reference}",
                f"- Proposed source: {item.resolved_resource_id or 'No exact registered resource'}",
                f"- Proposed PDF pages, zero-based: {page_range}",
                f"- Source heading: {evidence.source_heading or 'Not available'}",
                f"- Status: `{item.verification_status.value}`",
                f"- Human review note: {item.reviewer_note or 'Not applicable'}",
                f"- Confidence: {item.confidence:.2f}",
                f"- Beginning excerpt: {evidence.beginning_excerpt or 'Not available'}",
                f"- Ending excerpt: {evidence.ending_excerpt or 'Not available'}",
                f"- Why it appears to match: {'; '.join(evidence.evidence_notes) or item.resolution_method}",
                f"- Ambiguity or risk: {'; '.join(item.ambiguity_notes) or 'No unresolved ambiguity.'}",
                "- Review decision: [ ] approve  [ ] revise  [ ] reject",
                "",
            ]
    lines += ["## Unresolved references", ""]
    lines += [f"- {value}" for value in manifest.unresolved_references]
    lines += ["", "## Decisions required before generation", ""]
    review_items = [
        item for item in manifest.assignments
        if item.verification_status in {
            ProposalStatus.PROPOSED_FOR_REVIEW,
            ProposalStatus.UNRESOLVED,
        }
    ]
    lines += [
        f"- [ ] {item.title_or_label}: confirm, revise, or reject "
        f"`{item.proposed_pdf_start_page}–{item.proposed_pdf_end_page}`."
        if item.proposed_pdf_start_page is not None
        else f"- [ ] {item.title_or_label}: provide an approved source asset or mark unavailable."
        for item in review_items
    ]
    lines += ["", "## Warnings", ""]
    lines += [f"- {warning}" for warning in manifest.warnings]
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["lesson_mapping_review_markdown"]
