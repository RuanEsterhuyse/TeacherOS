"""Deterministic baseline analysis for isolated pasted lesson sources."""

from __future__ import annotations

import re
from typing import Any

from curriculum.intelligence.ids import stable_id
from schemas.pasted_lesson_schema import (
    BASELINE_ANALYZER_VERSION,
    AnalysisWarning,
    DiscussionQuestion,
    ExtractionSummary,
    PastedLessonSource,
    PlaybookActivity,
    PlaybookAnalysisResult,
    PlaybookGenerationMetadata,
    PlaybookLessonMetadata,
    SourceReference,
    TeacherPlaybook,
    VocabularyEntry,
)


ANALYZER_NAME = "deterministic-baseline"
DAY = re.compile(r"^Day\s+(\d+)\b", re.IGNORECASE)
ACTIVITY = re.compile(
    r"^(?:Activity(?:\s+\d+)?\s*[:.-]\s*)?"
    r"(?P<title>.+?)\s*"
    r"(?:\((?P<minutes_a>\d+)\s*(?:min|minutes)\)"
    r"|[—–-]\s*(?P<minutes_b>\d+)\s*(?:min|minutes))$",
    re.IGNORECASE,
)
REFERENCE_PATTERNS = (
    (
        "teacher_guide",
        re.compile(
            r"Teacher Guide\s*(?:pages?|pp?\.?)?\s*"
            r"(?P<start>\d+)(?:\s*[–-]\s*(?P<end>\d+))?",
            re.IGNORECASE,
        ),
    ),
    (
        "student_reader",
        re.compile(
            r"(?:Student Reader|Reader)\s*(?:pages?|pp?\.?)?\s*"
            r"(?P<start>\d+)(?:\s*[–-]\s*(?P<end>\d+))?",
            re.IGNORECASE,
        ),
    ),
)
ACTIVITY_REFERENCE = re.compile(
    r"\bActivity (?:Page|Book)\s+([A-Za-z0-9.-]+)",
    re.IGNORECASE,
)


SECTION_LABELS = {
    "lesson summary": "lesson_summary",
    "summary": "lesson_summary",
    "objectives": "objectives",
    "objective": "objectives",
    "essential question": "essential_question",
    "success criteria": "success_criteria",
    "materials": "materials",
    "vocabulary": "vocabulary",
    "teacher survival guide": "teacher_survival_guide",
    "homework": "homework",
    "assessment": "assessment",
    "end-of-day reflection": "end_of_day_reflection",
    "reflection": "end_of_day_reflection",
}
ACTIVITY_LABELS = {
    "purpose": "purpose",
    "teacher goal": "teacher_goal",
    "teacher script": "teacher_script",
    "question": "questions",
    "possible student response": "possible_student_responses",
    "possible student responses": "possible_student_responses",
    "teacher response": "teacher_responses",
    "teacher responses": "teacher_responses",
    "misconception": "misconceptions",
    "misconceptions": "misconceptions",
    "example": "examples",
    "examples": "examples",
    "eld support": "eld_supports",
    "eld supports": "eld_supports",
    "check for understanding": "checks_for_understanding",
    "checks for understanding": "checks_for_understanding",
    "look-for": "look_fors",
    "look-fors": "look_fors",
    "ready to move on": "ready_to_move_on_criteria",
    "ready-to-move-on criteria": "ready_to_move_on_criteria",
    "transition": "transition",
}


def _clean_line(value: str) -> str:
    return re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", value).strip()


def _label(value: str) -> tuple[str, str] | None:
    match = re.match(r"^([^:]{2,48}):\s*(.*)$", value)
    if not match:
        return None
    return match.group(1).strip().casefold(), match.group(2)


def _split_values(value: str) -> list[str]:
    if not value.strip():
        return []
    return [
        item.strip()
        for item in value.split(";")
        if item.strip()
    ]


def _references(value: str) -> list[SourceReference]:
    references = []
    for source_type, pattern in REFERENCE_PATTERNS:
        for match in pattern.finditer(value):
            start = int(match.group("start"))
            references.append(SourceReference(
                source_type=source_type,
                page_start=start,
                page_end=int(match.group("end") or start),
            ))
    for match in ACTIVITY_REFERENCE.finditer(value):
        references.append(SourceReference(
            source_type="activity_book",
            activity_reference=f"Activity Page {match.group(1)}",
        ))
    return references


def _deduplicate_references(
    values: list[SourceReference],
) -> list[SourceReference]:
    unique = {}
    for value in values:
        key = (
            value.source_type,
            value.page_start,
            value.page_end,
            value.section,
            value.activity_reference,
        )
        unique[key] = value
    return list(unique.values())


def _new_activity(
    source: PastedLessonSource,
    title: str,
    sequence: int,
    day: int | None,
    duration: int | None,
) -> dict[str, Any]:
    return {
        "activity_id": stable_id(
            "pasted-playbook-activity",
            source.source_id,
            str(sequence),
            title,
        ),
        "title": title,
        "instructional_day": day,
        "duration_minutes": duration,
        "purpose": None,
        "teacher_goal": None,
        "teacher_script": [],
        "questions": [],
        "possible_student_responses": [],
        "teacher_responses": [],
        "misconceptions": [],
        "examples": [],
        "eld_supports": [],
        "checks_for_understanding": [],
        "look_fors": [],
        "ready_to_move_on_criteria": [],
        "transition": None,
        "source_references": [],
    }


def analyze_pasted_lesson(
    source: PastedLessonSource,
) -> PlaybookAnalysisResult:
    """Extract only explicit, mechanically identifiable lesson information."""
    lines = source.teacher_guide_text.splitlines()
    fields: dict[str, Any] = {
        "lesson_summary": None,
        "objectives": [],
        "essential_question": None,
        "success_criteria": [],
        "materials": [],
        "vocabulary": [],
        "teacher_survival_guide": [],
        "homework": [],
        "assessment": [],
        "end_of_day_reflection": [],
    }
    activities: list[dict[str, Any]] = []
    days: list[int] = []
    references: list[SourceReference] = []
    unclassified: list[str] = []
    classified_count = 0
    current_day: int | None = None
    current_activity: dict[str, Any] | None = None
    current_section: str | None = None

    if source.teacher_guide_page_start is not None:
        references.append(SourceReference(
            source_type="teacher_guide",
            page_start=source.teacher_guide_page_start,
            page_end=source.teacher_guide_page_end,
            section=source.lesson_title,
        ))

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        clean = _clean_line(stripped)
        line_references = _references(clean)
        references.extend(line_references)
        if current_activity is not None:
            current_activity["source_references"].extend(line_references)

        day_match = DAY.match(clean)
        if day_match:
            current_day = int(day_match.group(1))
            if current_day not in days:
                days.append(current_day)
            current_activity = None
            current_section = None
            classified_count += 1
            continue

        label = _label(clean)
        if label and label[0] in SECTION_LABELS:
            current_section = SECTION_LABELS[label[0]]
            current_activity = None
            value = label[1].strip()
            if value:
                if current_section in {
                    "lesson_summary",
                    "essential_question",
                }:
                    fields[current_section] = value
                elif current_section == "vocabulary":
                    fields[current_section].extend(
                        VocabularyEntry(term=item)
                        for item in _split_values(value)
                    )
                else:
                    fields[current_section].extend(_split_values(value))
                current_section = None
            classified_count += 1
            continue

        activity_match = ACTIVITY.match(clean)
        is_activity_heading = (
            activity_match is not None
            and (
                clean.casefold().startswith("activity")
                or current_day is not None
            )
        )
        if is_activity_heading:
            title = activity_match.group("title").strip()
            title = re.sub(
                r"^Activity(?:\s+\d+)?\s*[:.-]\s*",
                "",
                title,
                flags=re.IGNORECASE,
            )
            duration = int(
                activity_match.group("minutes_a")
                or activity_match.group("minutes_b")
            )
            current_activity = _new_activity(
                source,
                title,
                len(activities) + 1,
                current_day,
                duration,
            )
            current_activity["source_references"].extend(line_references)
            activities.append(current_activity)
            current_section = None
            classified_count += 1
            continue

        if (
            current_activity is not None
            and label
            and label[0] in ACTIVITY_LABELS
        ):
            field = ACTIVITY_LABELS[label[0]]
            value = label[1].strip()
            if field == "questions" and value:
                current_activity[field].append(
                    DiscussionQuestion(prompt=value)
                )
            elif field in {"purpose", "teacher_goal", "transition"}:
                current_activity[field] = value or None
            elif value:
                current_activity[field].extend(_split_values(value))
            classified_count += 1
            continue

        if current_section:
            if current_section in {"lesson_summary", "essential_question"}:
                if fields[current_section] is None:
                    fields[current_section] = clean
                    classified_count += 1
                    continue
            elif current_section == "vocabulary":
                fields[current_section].extend(
                    VocabularyEntry(term=item)
                    for item in _split_values(clean)
                )
                classified_count += 1
                continue
            else:
                fields[current_section].extend(_split_values(clean))
                classified_count += 1
                continue

        if clean.casefold() in {
            "lesson agenda",
            "agenda",
            "lesson overview",
        }:
            classified_count += 1
            continue
        if line_references:
            classified_count += 1
            continue
        unclassified.append(raw)

    for activity in activities:
        activity["source_references"] = _deduplicate_references(
            activity["source_references"]
        )
    references = _deduplicate_references(references)
    warnings = []
    required_checks = (
        ("instructional_days", days, "No instructional day headings found."),
        ("activities", activities, "No timed activity headings found."),
        ("objectives", fields["objectives"], "No explicit objectives found."),
        ("materials", fields["materials"], "No explicit materials found."),
        ("vocabulary", fields["vocabulary"], "No explicit vocabulary found."),
        (
            "essential_question",
            fields["essential_question"],
            "No explicit essential question found.",
        ),
        (
            "success_criteria",
            fields["success_criteria"],
            "No explicit success criteria found.",
        ),
    )
    for field, value, message in required_checks:
        if not value:
            warnings.append(AnalysisWarning(
                code=f"{field}_not_found",
                field=field,
                message=message,
            ))
    if unclassified:
        warnings.append(AnalysisWarning(
            code="unclassified_source_text",
            field="unclassified_sections",
            message=(
                f"{len(unclassified)} source lines were preserved without "
                "classification."
            ),
        ))

    confidence = {
        "lesson_metadata": 1.0,
        "page_range": (
            1.0 if source.teacher_guide_page_start is not None else 0.0
        ),
        "instructional_days": 0.95 if days else 0.0,
        "activities": 0.9 if activities else 0.0,
        "objectives": 0.9 if fields["objectives"] else 0.0,
        "materials": 0.9 if fields["materials"] else 0.0,
        "vocabulary": 0.85 if fields["vocabulary"] else 0.0,
        "source_references": 0.9 if references else 0.0,
    }
    playbook_id = stable_id(
        "teacher-playbook",
        source.source_id,
        BASELINE_ANALYZER_VERSION,
    )
    playbook = TeacherPlaybook(
        playbook_id=playbook_id,
        source_id=source.source_id,
        lesson_metadata=PlaybookLessonMetadata(
            grade=source.grade,
            unit=source.unit,
            lesson_number=source.lesson_number,
            lesson_title=source.lesson_title,
            teacher_guide_page_start=source.teacher_guide_page_start,
            teacher_guide_page_end=source.teacher_guide_page_end,
        ),
        lesson_summary=fields["lesson_summary"],
        instructional_days=days,
        objectives=list(dict.fromkeys(fields["objectives"])),
        essential_question=fields["essential_question"],
        success_criteria=list(dict.fromkeys(fields["success_criteria"])),
        materials=list(dict.fromkeys(fields["materials"])),
        vocabulary=list({
            value.term.casefold(): value
            for value in fields["vocabulary"]
        }.values()),
        teacher_survival_guide=list(dict.fromkeys(
            fields["teacher_survival_guide"]
        )),
        activities=[
            PlaybookActivity.model_validate(value) for value in activities
        ],
        homework=list(dict.fromkeys(fields["homework"])),
        assessment=list(dict.fromkeys(fields["assessment"])),
        end_of_day_reflection=list(dict.fromkeys(
            fields["end_of_day_reflection"]
        )),
        source_references=references,
        generation_metadata=PlaybookGenerationMetadata(
            analyzer_name=ANALYZER_NAME,
            analyzer_version=BASELINE_ANALYZER_VERSION,
            generated_at=source.created_at,
            source_schema_version=source.schema_version,
        ),
    )
    return PlaybookAnalysisResult(
        playbook=playbook,
        warnings=warnings,
        unclassified_sections=unclassified,
        extraction_summary=ExtractionSummary(
            detected_activity_count=len(activities),
            detected_day_count=len(days),
            detected_reference_count=len(references),
            classified_line_count=classified_count,
            unclassified_line_count=len(unclassified),
            confidence_by_field=confidence,
        ),
    )


__all__ = [
    "ANALYZER_NAME",
    "analyze_pasted_lesson",
]
