"""Human-readable formatting for curriculum mapping proposals."""

from __future__ import annotations

import re

from schemas.curriculum_mapping_proposal_schema import (
    LessonResourceMappingManifest,
    ProposalStatus,
)


def _decision_items(
    manifest: LessonResourceMappingManifest,
):
    uncertain = [
        item for item in manifest.assignments
        if item.verification_status in {
            ProposalStatus.PROPOSED_FOR_REVIEW,
            ProposalStatus.UNRESOLVED,
            ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES,
        }
    ]
    seen = set()
    output = []
    for item in uncertain:
        numbers = [
            int(value)
            for reference in item.referenced_printed_pages
            for value in re.findall(r"\d+", reference)
        ]
        key = (
            item.resource_role,
            item.evidence[0].source_heading,
            numbers[0] if numbers else None,
            numbers[-1] if numbers else None,
            item.proposed_pdf_start_page,
            item.proposed_pdf_end_page,
        )
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def lesson_mapping_review_markdown(
    manifest: LessonResourceMappingManifest,
) -> str:
    lines = [
        f"# Lesson {manifest.lesson_number} Mapping Review", "",
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
        ("## Proposed instructional-text assignments", {
            "assigned_reading", "guided_reading_range",
            "assessment_reading",
            "prior_lesson_homework_review", "translation_reference",
            "refrane_reference", "story_notes",
        }),
        ("## Activity Book assignments", {
            "prior_lesson_activity_review", "shared_review_activity",
            "activity_resource", "vocabulary_resource",
            "homework_writing", "grammar_practice_and_homework",
            "writing_plan", "homework_writing_plan",
        }),
        ("## Proposed answer-key matches", {
            "prior_lesson_activity_answer_key",
            "shared_review_answer_key", "publisher_answer_key",
        }),
        ("## Online, chart, and physical resources", {
            "online_teacher_resources", "classroom_map",
            "teacher_chart", "assessment_resource",
        }),
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
                f"- Required status: `{item.required_status}`",
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
    review_items = _decision_items(manifest)
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


def consolidated_mapping_review_markdown(
    manifests: list[LessonResourceMappingManifest],
    *,
    failures: dict[int, str] | None = None,
) -> str:
    failures = failures or {}
    lines = [
        "# Unit 1 Lessons 3–9 Mapping Review",
        "",
        "## Executive summary",
        "",
        "| Lesson | Total | Deterministic | Proposed | Unresolved | "
        "Unavailable | Answer keys | Human decisions |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for manifest in manifests:
        statuses = [
            assignment.verification_status
            for assignment in manifest.assignments
        ]
        decisions = len(_decision_items(manifest))
        lines.append(
            f"| {manifest.lesson_number} | {len(statuses)} | "
            f"{statuses.count(ProposalStatus.DETERMINISTICALLY_VERIFIED)} | "
            f"{statuses.count(ProposalStatus.PROPOSED_FOR_REVIEW)} | "
            f"{statuses.count(ProposalStatus.UNRESOLVED)} | "
            f"{statuses.count(ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES)} | "
            f"{sum('answer_key' in item.resource_role for item in manifest.assignments)} | "
            f"{decisions} |"
        )
    for lesson, message in sorted(failures.items()):
        lines.append(
            f"| {lesson} | FAILED | — | — | — | — | — | — |"
        )
        lines.append(f"\n- Lesson {lesson} failure: {message}")

    for manifest in manifests:
        lines += [
            "",
            f"## Lesson {manifest.lesson_number} decisions",
            "",
        ]
        uncertain = _decision_items(manifest)
        if not uncertain:
            lines.append("- No human decisions.")
            continue
        for item in uncertain:
            evidence = item.evidence[0]
            page_range = (
                f"{item.proposed_pdf_start_page}–"
                f"{item.proposed_pdf_end_page}"
                if item.proposed_pdf_start_page is not None
                else "Unavailable or unresolved"
            )
            lines += [
                f"### {item.title_or_label}",
                "",
                f"- Publisher reference: {item.curriculum_reference}",
                f"- Proposed registered resource: "
                f"{item.resolved_resource_id or 'None'}",
                f"- Proposed PDF range: {page_range}",
                f"- Heading: {evidence.source_heading or 'Not available'}",
                f"- Beginning excerpt: "
                f"{evidence.beginning_excerpt or 'Not available'}",
                f"- Ending excerpt: "
                f"{evidence.ending_excerpt or 'Not available'}",
                f"- Reason it appears correct: "
                f"{'; '.join(evidence.evidence_notes) or item.resolution_method}",
                f"- Risk or ambiguity: "
                f"{'; '.join(item.ambiguity_notes) or 'None recorded.'}",
                "- Suggested decision: approve only if the proposed "
                "source equivalence is confirmed; otherwise revise or reject.",
                "- Review: [ ] approve  [ ] revise  [ ] reject",
                "",
            ]

    unavailable = [
        (manifest.lesson_number, item)
        for manifest in manifests
        for item in manifest.assignments
        if item.verification_status
        == ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES
    ]
    lines += ["", "## Unavailable teacher-supplied resources", ""]
    lines += (
        [
            f"- Lesson {lesson}: {item.curriculum_reference}"
            for lesson, item in unavailable
        ]
        or ["- None."]
    )
    lines += ["", "## Unresolved references", ""]
    unresolved = [
        f"Lesson {manifest.lesson_number}: {reference}"
        for manifest in manifests
        for reference in manifest.unresolved_references
    ]
    lines += unresolved or ["- None."]
    lines += ["", "## Cross-lesson conflicts detected", ""]
    lines.append(
        "- Earlier Activity Pages are retained only when the current "
        "Teacher Guide segment explicitly identifies them as review work."
    )
    lines += [
        "",
        "## Decisions required before production generation",
        "",
    ]
    for manifest in manifests:
        count = len(_decision_items(manifest))
        lines.append(
            f"- Lesson {manifest.lesson_number}: {count} decisions."
        )
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "consolidated_mapping_review_markdown",
    "lesson_mapping_review_markdown",
]
