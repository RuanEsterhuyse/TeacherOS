"""Deterministic Teacher Guide instruction audit and plan construction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from curriculum.intelligence.bundle import validate_prepared_source_bundle
from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.snapshot import write_json
from schemas.curriculum_intelligence_schema import (
    FindingSeverity,
    ReadinessState,
    ValidationFinding,
)
from schemas.instruction_plan_comparison_schema import (
    InstructionComparisonItem,
    InstructionComparisonStatus,
    InstructionPlanComparison,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
    PreparedSourceAssignment,
)
from schemas.source_grounded_instruction_schema import (
    InstructionSequenceReference,
    InstructionSourceProvenance,
    SourceAction,
    SourceAnswer,
    SourceAuditFinding,
    SourceFindingCategory,
    SourceGroundedInstructionPhase,
    SourceGroundedInstructionPlan,
    SourceMaterial,
    SourceObjective,
    SourceQuestion,
)


PLAN_SCHEMA_VERSION = "1.0"
PLAN_BUILDER_VERSION = "1.0"

TIMED_HEADING_RE = re.compile(
    r"(?m)^(?P<title>[^\n]+?)\s+(?P<minutes>\d+)\s+minutes\s*$",
    re.IGNORECASE,
)
FOOTER_RE = re.compile(
    r"(?:Core Knowledge Language Arts.*?\d+|"
    r"\d+\s+Unit\s+\d+.*?Core Knowledge Language Arts)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InstructionPlanResult:
    plan: SourceGroundedInstructionPlan
    comparison: InstructionPlanComparison
    plan_json_path: Path
    plan_markdown_path: Path
    comparison_json_path: Path
    comparison_markdown_path: Path


def _flatten(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalized_span(text: str, value: str) -> tuple[int, int] | None:
    tokens = value.split()
    if not tokens:
        return None
    match = re.search(
        r"\s+".join(re.escape(token) for token in tokens),
        text,
    )
    return (match.start(), match.end()) if match else None


def _teacher_guide_assignment(
    bundle: PreparedCurriculumSourceBundle,
) -> PreparedSourceAssignment:
    matches = [
        value
        for value in bundle.required_assignments
        if value.assignment_type == "defines_lesson"
    ]
    if len(matches) != 1 or not matches[0].source_segments:
        raise ValueError(
            "Bundle must contain one available Teacher Guide assignment."
        )
    return matches[0]


def _provenance(
    bundle: PreparedCurriculumSourceBundle,
    assignment: PreparedSourceAssignment,
    exact_text: str,
    *,
    start: int | None = None,
    end: int | None = None,
) -> InstructionSourceProvenance:
    resource = next(
        value for value in bundle.resource_summaries
        if value.resource_id == assignment.resource_id
    )
    provenance = [
        value
        for segment in assignment.source_segments
        for value in segment.provenance
    ]
    return InstructionSourceProvenance(
        assignment_id=assignment.assignment_id,
        resource_id=assignment.resource_id,
        segment_ids=assignment.text_segment_ids,
        pdf_page_numbers=sorted({
            value.pdf_page_number for value in provenance
            if value.pdf_page_number is not None
        }),
        display_page_numbers=sorted({
            value.display_page_number for value in provenance
            if value.display_page_number is not None
        }),
        curriculum_references=[
            f"{value.reference_system}:{value.value}"
            for value in assignment.original_curriculum_references
        ],
        coordinate_mapping_ids=[
            value.mapping_id
            for value in assignment.coordinate_mapping_provenance
        ],
        resource_checksum=resource.stored_checksum,
        resource_version=resource.source_version,
        extraction_version=resource.extraction_version,
        bundle_digest=bundle.bundle_digest,
        start_character_offset=start,
        end_character_offset=end,
        exact_text_digest=content_digest(exact_text),
    )


def _phase_type(title: str) -> str:
    normalized = title.casefold()
    for keyword, value in (
        ("advance preparation", "teacher_preparation"),
        ("introduce the themes", "introduction"),
        ("introduce the book", "introduction"),
        ("introduce the story", "reading_preparation"),
        ("read the story", "reading"),
        ("discuss", "discussion"),
        ("wrap up", "reflection"),
        ("take-home", "homework"),
    ):
        if keyword in normalized:
            return value
    return "source_instruction"


def _paragraphs(text: str) -> list[tuple[str, int, int]]:
    output = []
    for match in re.finditer(r"(?:^|\n\s*\n)(.+?)(?=\n\s*\n|$)", text, re.S):
        raw = match.group(1).strip()
        if raw:
            start = match.start(1) + len(match.group(1)) - len(
                match.group(1).lstrip()
            )
            output.append((raw, start, match.end(1)))
    return output


def _answer_text(paragraph: str) -> str | None:
    value = _flatten(paragraph)
    if value.startswith("oo "):
        return value[3:].strip()
    match = re.search(
        r"\((?:Possible answer|possible answer|Answers? may include|"
        r"Answers? will vary but may include):\s*(.+)\)\s*$",
        value,
        re.I,
    )
    return match.group(1).strip() if match else None


def _extract_questions(
    phase_text: str,
    phase_start: int,
    bundle: PreparedCurriculumSourceBundle,
    assignment: PreparedSourceAssignment,
) -> tuple[list[SourceQuestion], set[int]]:
    parse_text = FOOTER_RE.sub("", phase_text)
    candidates: list[tuple[int, str, str | None, str | None]] = []
    labeled = re.compile(
        r"(?ms)^(?:[A-Z]+/)*(?P<type>Literal|Inferential|Evaluative)"
        r"[ \t\u2002]+(?P<question>.+?)(?=\n\s*\n)"
    )
    for match in labeled.finditer(parse_text):
        question = _flatten(match.group("question"))
        following = parse_text[match.end():]
        answer_match = re.match(
            r"\s*oo\s+(?P<answer>.+?)(?=\n\s*\n|$)",
            following,
            re.S,
        )
        answer = (
            _flatten(answer_match.group("answer"))
            if answer_match else None
        )
        candidates.append((
            match.start(),
            question,
            match.group("type").casefold(),
            answer,
        ))
    refrane = re.search(
        r"Ask:\s*(?P<question>[^?]+\?)\s*"
        r"\(Possible answer:\s*(?P<answer>.+?)\)\s*Tell students",
        parse_text,
        re.S,
    )
    if refrane:
        candidates.append((
            refrane.start("question"),
            _flatten(refrane.group("question")),
            None,
            _flatten(refrane.group("answer")),
        ))
    paragraphs = _paragraphs(parse_text)
    for index, (paragraph, start, _) in enumerate(paragraphs):
        flat = _flatten(paragraph)
        question = None
        if "Turn and Talk" in flat and "?" in flat:
            question = (
                flat.rsplit(".", 1)[-1].strip().split("?", 1)[0] + "?"
            )
        elif flat.startswith(("Could ", "How ")) and "?" in flat:
            question = flat.split("?", 1)[0] + "?"
        if question:
            if not re.search(r"\b[\w’'-]{2,}\b", question):
                question = None
        if question:
            answer = (
                _answer_text(paragraphs[index + 1][0])
                if index + 1 < len(paragraphs)
                else None
            )
            candidates.append((
                start, question, "discussion", answer
            ))
        if "following questions to lead a discussion:" in flat:
            after = flat.split(
                "following questions to lead a discussion:", 1
            )[1]
            candidates.extend(
                (start, value.strip(), "discussion", None)
                for value in re.findall(r"[^?]+\?", after)
            )
    questions = []
    seen = set()
    for _offset, question_text, question_type, answer in sorted(candidates):
        key = _flatten(question_text)
        if key in seen:
            continue
        seen.add(key)
        question_span = _normalized_span(phase_text, question_text)
        answers = []
        if answer:
            answer_span = _normalized_span(phase_text, answer)
            answers.append(SourceAnswer(
                id=stable_id(
                    "source-answer",
                    assignment.assignment_id,
                    question_text,
                    answer,
                ),
                exact_text=answer,
                provenance=[_provenance(
                    bundle,
                    assignment,
                    answer,
                    start=(
                        phase_start + answer_span[0]
                        if answer_span else None
                    ),
                    end=(
                        phase_start + answer_span[1]
                        if answer_span else None
                    ),
                )],
            ))
        questions.append(SourceQuestion(
            id=stable_id(
                "source-question",
                assignment.assignment_id,
                question_text,
            ),
            question_text=question_text,
            question_type=question_type,
            answers=answers,
            provenance=[_provenance(
                bundle,
                assignment,
                question_text,
                start=(
                    phase_start + question_span[0]
                    if question_span else None
                ),
                end=(
                    phase_start + question_span[1]
                    if question_span else None
                ),
            )],
            confidence=1,
        ))
    consumed = set()
    for index, (paragraph, _, _) in enumerate(_paragraphs(phase_text)):
        flat = _flatten(paragraph)
        if any(
            _flatten(question.question_text) in flat
            or any(_flatten(answer.exact_text) in flat for answer in question.answers)
            for question in questions
        ):
            consumed.add(index)
    return questions, consumed


def _extract_actions(
    phase_text: str,
    phase_start: int,
    consumed: set[int],
    bundle: PreparedCurriculumSourceBundle,
    assignment: PreparedSourceAssignment,
) -> tuple[list[SourceAction], list[SourceAction]]:
    teacher = []
    student = []
    for index, (paragraph, start, end) in enumerate(_paragraphs(phase_text)):
        if index in consumed:
            continue
        if "•" in paragraph:
            chunks = []
            for raw_chunk in paragraph.split("•")[1:]:
                lines = [
                    value.strip()
                    for value in raw_chunk.strip().splitlines()
                    if value.strip()
                ]
                while (
                    lines
                    and re.fullmatch(r"[A-Z][A-Za-z ]+", lines[-1])
                    and len(lines[-1].split()) <= 3
                ):
                    lines.pop()
                if lines:
                    chunks.append("•" + _flatten("\n".join(lines)))
        else:
            chunks = [_flatten(paragraph)]
        for flat in chunks:
            if (
                FOOTER_RE.fullmatch(flat)
                or re.match(r"^\d+\.\s", flat)
                or flat.startswith("Vocabulary Type ")
            ):
                continue
            explicit = (
                flat.startswith(("•", "oo ", "Note to Teacher:"))
                or re.match(
                    r"^(Tell|Have|Ask|Read|Remind|Display|Point|Explain|"
                    r"Ensure|Provide|Introduce|Encourage|Call|Write|Begin|"
                    r"Turn and Talk|Think-Pair-Share|As time permits)",
                    flat,
                    re.I,
                )
            )
            if not explicit:
                continue
            exact = flat.lstrip("•").strip()
            actor = (
                "student"
                if (
                    not re.match(r"^(Assign|Distribute)\b", exact, re.I)
                    and re.search(
                        r"\b(Have students|Ask students|student pairs|students "
                        r"(?:think|write|read|turn|share|follow|reference)|"
                        r"Think-Pair-Share|Turn and Talk)\b",
                        exact,
                        re.I,
                    )
                )
                else "teacher"
            )
            value = SourceAction(
                id=stable_id(
                    "source-action",
                    assignment.assignment_id,
                    actor,
                    exact,
                ),
                actor=actor,
                exact_text=exact,
                provenance=[_provenance(
                    bundle,
                    assignment,
                    exact,
                    start=phase_start + start,
                    end=phase_start + end,
                )],
            )
            (student if actor == "student" else teacher).append(value)
    return teacher, student


def _assignment_references(
    phase_text: str,
    bundle: PreparedCurriculumSourceBundle,
) -> list[PreparedSourceAssignment]:
    normalized = phase_text.casefold()
    resources = {
        value.resource_id: value for value in bundle.resource_summaries
    }
    output = []
    for assignment in (
        bundle.required_assignments + bundle.optional_assignments
    ):
        if assignment.assignment_type == "defines_lesson":
            continue
        references = [
            value.value.casefold()
            for value in assignment.original_curriculum_references
            if len(value.value) >= 3
        ]
        title_terms = [
            value.casefold()
            for value in (
                assignment.title,
                *[
                    reference.value
                    for reference in assignment.original_curriculum_references
                    if reference.reference_system == "section"
                ],
            )
        ]
        source_urls = {
            value.rstrip(".,")
            for segment in assignment.source_segments
            for value in re.findall(r"https?://\S+", segment.exact_text)
        }
        phase_urls = {
            value.rstrip(".,")
            for value in re.findall(r"https?://\S+", phase_text)
        }
        resource = resources.get(assignment.resource_id)
        resource_terms = (
            (
                resource.title.casefold(),
                resource.resource_type.replace("_", " ").casefold(),
            )
            if resource is not None
            else ()
        )
        online_resource_match = (
            "online resource" in normalized
            and any("online resource" in value for value in resource_terms)
        )
        if (
            any(value in normalized for value in references + title_terms)
            or bool(source_urls.intersection(phase_urls))
            or online_resource_match
        ):
            output.append(assignment)
    return output


def _phase_specs(text: str) -> list[tuple[str, int | None, str | None, int, int]]:
    specs = []
    advance_start = text.find("ADVANCE PREPARATION")
    day_one_start = text.find("\nDAY 1\n", advance_start)
    if advance_start >= 0 and day_one_start > advance_start:
        specs.append((
            "Advance Preparation",
            None,
            None,
            advance_start,
            day_one_start,
        ))
    matches = list(TIMED_HEADING_RE.finditer(text))
    subphases = [
        value for value in matches
        if not value.group("title").strip().isupper()
    ]
    structural_boundaries = [
        value.start() for value in matches
    ] + [
        value
        for marker in ("\nDAY 1\n", "\nDAY 2\n", "\nTake-Home Material\n")
        if (value := text.find(marker)) >= 0
    ] + [len(text)]
    for match in subphases:
        start = match.start()
        end = min(value for value in structural_boundaries if value > start)
        day_one = text.rfind("\nDAY 1\n", 0, start)
        day_two = text.rfind("\nDAY 2\n", 0, start)
        day_label = "Day 2" if day_two > day_one else "Day 1"
        specs.append((
            match.group("title").strip(),
            int(match.group("minutes")),
            day_label,
            start,
            end,
        ))
    take_home = text.find("\nTake-Home Material\n")
    if take_home >= 0:
        specs.append((
            "Take-Home Material",
            None,
            "Day 2",
            take_home + 1,
            len(text),
        ))
    return sorted(specs, key=lambda value: value[3])


def _finding(
    code: str,
    severity: FindingSeverity,
    message: str,
    reference_id: str,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        reference_id=reference_id,
    )


def _plan_digest(plan: SourceGroundedInstructionPlan) -> str:
    return content_digest(plan.model_dump(mode="json", exclude={"digest"}))


def validate_instruction_plan(
    plan: SourceGroundedInstructionPlan,
    bundle: PreparedCurriculumSourceBundle,
) -> list[ValidationFinding]:
    findings = []
    if bundle.readiness_state != ReadinessState.SOURCE_READY:
        findings.append(_finding(
            "bundle_not_source_ready",
            FindingSeverity.ERROR,
            "Instruction plan requires a source_ready bundle.",
            bundle.lesson_id,
        ))
    if validate_prepared_source_bundle(bundle):
        findings.append(_finding(
            "bundle_invalid",
            FindingSeverity.ERROR,
            "Prepared source bundle failed validation.",
            bundle.lesson_id,
        ))
    if [value.sequence for value in plan.instructional_phases] != list(
        range(1, len(plan.instructional_phases) + 1)
    ):
        findings.append(_finding(
            "phase_order_invalid",
            FindingSeverity.ERROR,
            "Instruction phases are not continuously ordered.",
            plan.lesson_id,
        ))
    assignment = _teacher_guide_assignment(bundle)
    segment_text = assignment.source_segments[0].exact_text
    grounded_segment_text = _flatten(FOOTER_RE.sub("", segment_text))
    assignments = {
        value.assignment_id: value
        for value in (
            bundle.required_assignments + bundle.optional_assignments
        )
    }
    resources = {
        value.resource_id: value for value in bundle.resource_summaries
    }

    def check_provenance(
        values: list[InstructionSourceProvenance],
        reference_id: str,
        exact_text: str,
    ) -> None:
        for value in values:
            source_assignment = assignments.get(value.assignment_id)
            source_resource = resources.get(value.resource_id)
            if (
                source_assignment is None
                or source_resource is None
                or value.resource_id != source_assignment.resource_id
                or not set(value.segment_ids).issubset(
                    source_assignment.text_segment_ids
                )
                or value.resource_checksum != source_resource.stored_checksum
                or value.resource_version != source_resource.source_version
                or value.extraction_version
                != source_resource.extraction_version
                or value.bundle_digest != bundle.bundle_digest
                or value.exact_text_digest != content_digest(exact_text)
                or (
                    value.start_character_offset is not None
                    and value.end_character_offset is not None
                    and value.start_character_offset
                    >= value.end_character_offset
                )
            ):
                findings.append(_finding(
                    "source_provenance_invalid",
                    FindingSeverity.ERROR,
                    f"Invalid source provenance: {reference_id}.",
                    reference_id,
                ))

    for phase in plan.instructional_phases:
        expected_id = stable_id(
            "source-phase",
            plan.lesson_id,
            phase.sequence,
            phase.phase_title,
            assignment.text_segment_ids[0],
        )
        if phase.id != expected_id:
            findings.append(_finding(
                "phase_id_invalid",
                FindingSeverity.ERROR,
                f"Phase ID is not deterministic: {phase.phase_title}.",
                phase.id,
            ))
        if phase.exact_source_text not in segment_text:
            findings.append(_finding(
                "phase_text_not_grounded",
                FindingSeverity.ERROR,
                f"Phase text is absent from Teacher Guide: {phase.phase_title}.",
                phase.id,
            ))
        for provenance in phase.provenance:
            if (
                provenance.assignment_id != assignment.assignment_id
                or provenance.resource_id != assignment.resource_id
                or provenance.bundle_digest != bundle.bundle_digest
            ):
                findings.append(_finding(
                    "phase_provenance_invalid",
                    FindingSeverity.ERROR,
                    f"Invalid provenance: {phase.phase_title}.",
                    phase.id,
                ))
        check_provenance(
            phase.provenance, phase.id, phase.exact_source_text
        )
        unknown_assignments = set(
            phase.referenced_assignment_ids
        ).difference(assignments)
        unknown_resources = set(
            phase.referenced_resource_ids
        ).difference(resources)
        expected_resources = {
            assignments[value].resource_id
            for value in phase.referenced_assignment_ids
            if value in assignments
        }
        if (
            unknown_assignments
            or unknown_resources
            or set(phase.referenced_resource_ids) != expected_resources
        ):
            findings.append(_finding(
                "phase_reference_invalid",
                FindingSeverity.ERROR,
                f"Unknown assignment or resource reference: {phase.phase_title}.",
                phase.id,
            ))
        if phase.duration_minutes is not None and not re.search(
            rf"{re.escape(phase.phase_title)}\s+"
            rf"{phase.duration_minutes}\s+minutes",
            phase.exact_source_text,
            re.IGNORECASE,
        ):
            findings.append(_finding(
                "timing_not_grounded",
                FindingSeverity.ERROR,
                f"Timing is absent from phase source: {phase.phase_title}.",
                phase.id,
            ))
        for action in phase.teacher_actions + phase.student_actions:
            check_provenance(
                action.provenance, action.id, action.exact_text
            )
        for question in phase.questions:
            check_provenance(
                question.provenance, question.id, question.question_text
            )
            if _flatten(question.question_text) not in grounded_segment_text:
                findings.append(_finding(
                    "question_not_grounded",
                    FindingSeverity.ERROR,
                    f"Question is absent from Teacher Guide: {question.id}.",
                    question.id,
                ))
            for answer in question.answers:
                check_provenance(
                    answer.provenance, answer.id, answer.exact_text
                )
                if _flatten(answer.exact_text) not in grounded_segment_text:
                    findings.append(_finding(
                        "answer_not_grounded",
                        FindingSeverity.ERROR,
                        f"Answer is absent from Teacher Guide: {answer.id}.",
                        answer.id,
                    ))
    for value in plan.objectives + plan.materials:
        check_provenance(value.provenance, value.id, value.exact_text)
        if _flatten(value.exact_text) not in grounded_segment_text:
            findings.append(_finding(
                "lesson_metadata_not_grounded",
                FindingSeverity.ERROR,
                f"Objective or material is absent from Teacher Guide: {value.id}.",
                value.id,
            ))
    if plan.digest != _plan_digest(plan):
        findings.append(_finding(
            "plan_digest_invalid",
            FindingSeverity.ERROR,
            "Instruction plan digest does not match its contents.",
            plan.lesson_id,
        ))
    return findings


class SourceGroundedInstructionPlanBuilder:
    """Extract only explicit Teacher Guide instructions without AI."""

    def build(
        self,
        bundle: PreparedCurriculumSourceBundle,
    ) -> SourceGroundedInstructionPlan:
        assignment = _teacher_guide_assignment(bundle)
        if bundle.readiness_state != ReadinessState.SOURCE_READY:
            raise ValueError("Prepared bundle must be source_ready.")
        if any(not value.available for value in bundle.required_assignments):
            raise ValueError("All required assignments must be available.")
        segment = assignment.source_segments[0]
        text = segment.exact_text
        guide_provenance = _provenance(
            bundle, assignment, text, start=0, end=len(text)
        )
        phases = []
        audit = []
        for sequence, (title, minutes, day, start, end) in enumerate(
            _phase_specs(text), start=1
        ):
            source_text = text[start:end].strip()
            phase_start = text.find(source_text, start)
            questions, consumed = _extract_questions(
                source_text,
                phase_start,
                bundle,
                assignment,
            )
            teacher_actions, student_actions = _extract_actions(
                source_text,
                phase_start,
                consumed,
                bundle,
                assignment,
            )
            references = _assignment_references(source_text, bundle)
            phase_type = _phase_type(title)
            assigned_readings = [
                value
                for value in bundle.required_assignments
                if value.assignment_type == "assigned_reading"
            ]
            if (
                phase_type == "reading"
                and len(assigned_readings) == 1
                and assigned_readings[0] not in references
            ):
                references.append(assigned_readings[0])
            activity_ids = [
                value.assignment_id for value in references
                if any(
                    resource.resource_id == value.resource_id
                    and resource.resource_type == "activity_resource"
                    for resource in bundle.resource_summaries
                )
            ]
            homework_ids = [
                value.assignment_id for value in references
                if value.assignment_type == "homework"
            ]
            grouping = [
                label for label in (
                    "turn_and_talk",
                    "think_pair_share",
                    "partners",
                    "small_groups",
                    "whole_class",
                )
                if {
                    "turn_and_talk": "turn and talk",
                    "think_pair_share": "think-pair-share",
                    "partners": "partner",
                    "small_groups": "group of",
                    "whole_class": "whole class",
                }[label] in source_text.casefold()
            ]
            phase = SourceGroundedInstructionPhase(
                id=stable_id(
                    "source-phase",
                    bundle.lesson_id,
                    sequence,
                    title,
                    assignment.text_segment_ids[0],
                ),
                sequence=sequence,
                phase_title=title,
                phase_type=phase_type,
                day_label=day,
                duration_minutes=minutes,
                exact_source_text=source_text,
                teacher_actions=teacher_actions,
                student_actions=student_actions,
                grouping=grouping,
                questions=questions,
                activity_assignment_ids=activity_ids,
                homework_assignment_ids=homework_ids,
                referenced_assignment_ids=[
                    value.assignment_id for value in references
                ],
                referenced_resource_ids=list(dict.fromkeys(
                    value.resource_id for value in references
                )),
                segment_ids=assignment.text_segment_ids,
                pdf_page_numbers=guide_provenance.pdf_page_numbers,
                provenance=[_provenance(
                    bundle,
                    assignment,
                    source_text,
                    start=phase_start,
                    end=phase_start + len(source_text),
                )],
                confidence=1,
                warnings=(
                    ["No explicit duration is stated for this phase."]
                    if minutes is None else []
                ),
            )
            phases.append(phase)
            audit.append(SourceAuditFinding(
                id=stable_id("source-audit", phase.id, "structure"),
                category=SourceFindingCategory.DETERMINISTIC_STRUCTURE,
                label=title,
                exact_text=title,
                provenance=phase.provenance,
                included_in_plan=True,
            ))
            if minutes is not None:
                audit.append(SourceAuditFinding(
                    id=stable_id("source-audit", phase.id, "timing"),
                    category=SourceFindingCategory.EXPLICIT_SOURCE_TIMING,
                    label=f"{title} timing",
                    exact_text=f"{title} {minutes} minutes",
                    provenance=phase.provenance,
                    included_in_plan=True,
                ))
            audit.extend(
                SourceAuditFinding(
                    id=stable_id("source-audit", value.id),
                    category=SourceFindingCategory.EXPLICIT_SOURCE_QUESTION,
                    label=value.question_text,
                    exact_text=value.question_text,
                    provenance=value.provenance,
                    included_in_plan=True,
                )
                for value in questions
            )
            audit.extend(
                SourceAuditFinding(
                    id=stable_id("source-audit", value.id),
                    category=SourceFindingCategory.EXPLICIT_SOURCE_INSTRUCTION,
                    label=value.exact_text[:120],
                    exact_text=value.exact_text,
                    provenance=value.provenance,
                    included_in_plan=True,
                )
                for value in teacher_actions + student_actions
            )

        objective_provenance = [_provenance(
            bundle, assignment, value
        ) for value in bundle.curriculum_lesson.objectives]
        objectives = [
            SourceObjective(
                id=stable_id(
                    "source-objective", bundle.lesson_id, value
                ),
                exact_text=value,
                standard_references=re.findall(
                    r"\b[A-Z]{1,3}\.\d+(?:\.\d+)?(?:\.[a-z])?\b",
                    value,
                ),
                provenance=[provenance],
            )
            for value, provenance in zip(
                bundle.curriculum_lesson.objectives,
                objective_provenance,
            )
        ]
        audit.extend(
            SourceAuditFinding(
                id=stable_id("source-audit", value.id),
                category=SourceFindingCategory.EXPLICIT_SOURCE_OBJECTIVE,
                label=value.exact_text,
                exact_text=value.exact_text,
                provenance=value.provenance,
                included_in_plan=True,
            )
            for value in objectives
        )
        materials = []
        for value in bundle.curriculum_lesson.materials:
            span = _normalized_span(text, value)
            if span is None:
                audit.append(SourceAuditFinding(
                    id=stable_id(
                        "source-audit", bundle.lesson_id, "material", value
                    ),
                    category=SourceFindingCategory.AMBIGUOUS,
                    label=value,
                    included_in_plan=False,
                    notes=[
                        "Prepared metadata wording is not an exact Teacher "
                        "Guide substring."
                    ],
                ))
                continue
            materials.append(SourceMaterial(
                id=stable_id("source-material", bundle.lesson_id, value),
                exact_text=value,
                provenance=[_provenance(
                    bundle,
                    assignment,
                    value,
                    start=span[0],
                    end=span[1],
                )],
            ))
        containers = {
            match.group("title").strip(): int(match.group("minutes"))
            for match in TIMED_HEADING_RE.finditer(text)
            if match.group("title").strip().isupper()
        }
        total_duration = (
            sum(containers.values()) if containers else None
        )
        warnings = []
        day_two_child = sum(
            value.duration_minutes or 0 for value in phases
            if value.day_label == "Day 2"
            and value.duration_minutes is not None
        )
        reading_container = containers.get("READING")
        if (
            reading_container is not None
            and day_two_child != reading_container
        ):
            message = (
                f"Day 2 is explicitly labeled {reading_container} minutes, "
                f"but its explicitly timed phases total {day_two_child} minutes."
            )
            warnings.append(_finding(
                "explicit_timing_conflict",
                FindingSeverity.WARNING,
                message,
                bundle.lesson_id,
            ))
            audit.append(SourceAuditFinding(
                id=stable_id("source-audit", bundle.lesson_id, message),
                category=SourceFindingCategory.AMBIGUOUS,
                label="Day 2 timing conflict",
                exact_text=message,
                provenance=[guide_provenance],
                included_in_plan=False,
            ))
        for label in (
            "exit ticket",
            "explicit assessment directions",
            "explicitly labeled transitions",
        ):
            audit.append(SourceAuditFinding(
                id=stable_id("source-audit", bundle.lesson_id, label),
                category=SourceFindingCategory.ABSENT,
                label=label,
                included_in_plan=False,
                notes=["No explicit labeled source section was identified."],
            ))

        def sequence_for(predicate) -> list[InstructionSequenceReference]:
            values = []
            for phase in phases:
                assignment_ids = [
                    value for value in phase.referenced_assignment_ids
                    if predicate(phase, value)
                ]
                if assignment_ids or predicate(phase, None):
                    values.append(InstructionSequenceReference(
                        sequence=len(values) + 1,
                        phase_id=phase.id,
                        assignment_ids=assignment_ids,
                    ))
            return values

        assignment_by_id = {
            value.assignment_id: value
            for value in (
                bundle.required_assignments + bundle.optional_assignments
            )
        }
        plan = SourceGroundedInstructionPlan(
            curriculum_id=bundle.curriculum_id,
            unit_id=bundle.unit_id,
            lesson_id=bundle.lesson_id,
            lesson_title=bundle.curriculum_lesson.title,
            teacher_guide_digest=content_digest(text),
            bundle_digest=bundle.bundle_digest,
            total_duration_minutes=total_duration,
            instructional_phases=phases,
            teacher_preparation=(
                phases[0].teacher_actions if phases else []
            ),
            materials=materials,
            objectives=objectives,
            vocabulary_sequence=sequence_for(
                lambda phase, _: "vocabulary" in phase.exact_source_text.casefold()
            ),
            reading_sequence=sequence_for(
                lambda phase, assignment_id: (
                    phase.phase_type in {"reading_preparation", "reading"}
                    and (
                        assignment_id is None
                        or (
                            assignment_by_id.get(assignment_id) is not None
                            and assignment_by_id[
                                assignment_id
                            ].assignment_type == "assigned_reading"
                        )
                    )
                )
            ),
            activity_sequence=sequence_for(
                lambda phase, assignment_id: (
                    assignment_id in phase.activity_assignment_ids
                    if assignment_id else bool(phase.activity_assignment_ids)
                )
            ),
            assessment_sequence=[],
            homework_sequence=sequence_for(
                lambda phase, assignment_id: (
                    phase.phase_type == "homework"
                    and (
                        assignment_id is None
                        or (
                            assignment_by_id.get(assignment_id) is not None
                            and assignment_by_id[
                                assignment_id
                            ].assignment_type == "homework"
                        )
                    )
                )
            ),
            audit_findings=audit,
            warnings=warnings,
            blockers=[],
            provenance=[guide_provenance],
            digest="pending",
            schema_version=PLAN_SCHEMA_VERSION,
            builder_version=PLAN_BUILDER_VERSION,
        )
        plan = plan.model_copy(update={"digest": _plan_digest(plan)})
        findings = validate_instruction_plan(plan, bundle)
        if findings:
            raise ValueError(
                "Instruction plan validation failed: "
                + "; ".join(value.message for value in findings)
            )
        return plan


def _generated_paths(value: Any, path: str = "") -> list[str]:
    output = []
    if isinstance(value, dict):
        if value.get("origin") == "generated_instructional_guidance":
            output.append(path or "$")
        for key, child in value.items():
            output.extend(_generated_paths(
                child, f"{path}.{key}" if path else key
            ))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(_generated_paths(child, f"{path}[{index}]"))
    return output


def _comparison_digest(comparison: InstructionPlanComparison) -> str:
    return content_digest(
        comparison.model_dump(
            mode="json", exclude={"comparison_digest"}
        )
    )


def compare_instruction_plan(
    plan: SourceGroundedInstructionPlan,
    current: dict[str, Any],
) -> InstructionPlanComparison:
    current_blocks = [
        value.get("title")
        for value in current.get("lesson_blocks", [])
        if isinstance(value, dict)
    ]
    current_questions = [
        question.get("question_text")
        for block in current.get("lesson_blocks", [])
        if isinstance(block, dict)
        for question in block.get("questions", [])
        if isinstance(question, dict)
    ] + [
        question.get("question_text")
        for block in current.get("lesson_blocks", [])
        if isinstance(block, dict)
        for chunk in block.get("reading_chunks", [])
        if isinstance(chunk, dict)
        for question in chunk.get("questions", [])
        if isinstance(question, dict)
    ]
    plan_questions = [
        value.question_text
        for phase in plan.instructional_phases
        for value in phase.questions
    ]
    current_activity = [
        value.get("page")
        for value in current.get("activity_book", [])
        if isinstance(value, dict)
    ]
    plan_activity = sorted({
        assignment_id
        for phase in plan.instructional_phases
        for assignment_id in phase.activity_assignment_ids
    })
    source_homework = [
        action.exact_text
        for phase in plan.instructional_phases
        if phase.phase_type == "homework"
        for action in phase.teacher_actions + phase.student_actions
    ]
    generated = sorted(set(_generated_paths(current)))
    items = [
        InstructionComparisonItem(
            field="instruction_order",
            status=InstructionComparisonStatus.NOT_REPRODUCIBLE,
            source_plan_value=[
                value.phase_title for value in plan.instructional_phases
            ],
            current_canonical_value=current_blocks,
            notes=[
                "The plan preserves explicit Teacher Guide headings; current "
                "slide-oriented block structure is not reproducible directly."
            ],
        ),
        InstructionComparisonItem(
            field="timing",
            status=InstructionComparisonStatus.SOURCE_SUPPORTED,
            source_plan_value={
                "total": plan.total_duration_minutes,
                "phases": {
                    value.phase_title: value.duration_minutes
                    for value in plan.instructional_phases
                },
            },
            current_canonical_value=current.get(
                "lesson_information", {}
            ).get("duration_minutes"),
        ),
        InstructionComparisonItem(
            field="questions",
            status=InstructionComparisonStatus.SOURCE_SUPPORTED,
            source_plan_value=plan_questions,
            current_canonical_value=current_questions,
        ),
        InstructionComparisonItem(
            field="activities",
            status=InstructionComparisonStatus.SOURCE_SUPPORTED,
            source_plan_value=plan_activity,
            current_canonical_value=current_activity,
        ),
        InstructionComparisonItem(
            field="homework",
            status=InstructionComparisonStatus.SOURCE_SUPPORTED,
            source_plan_value=source_homework,
            current_canonical_value=current.get("homework", []),
            notes=[
                "Source-plan homework is taken only from explicit Teacher Guide "
                "actions in the Take-Home phase."
            ],
        ),
        InstructionComparisonItem(
            field="assessments",
            status=InstructionComparisonStatus.NOT_REPRODUCIBLE,
            source_plan_value=[],
            current_canonical_value=current.get("assessment", []),
            notes=[
                "No explicitly labeled assessment directions were identified."
            ],
        ),
        InstructionComparisonItem(
            field="transitions",
            status=InstructionComparisonStatus.NOT_REPRODUCIBLE,
            source_plan_value=[],
            current_canonical_value=[
                value.get("transitions", [])
                for value in current.get("lesson_blocks", [])
                if isinstance(value, dict)
            ],
        ),
        InstructionComparisonItem(
            field="teacher_guidance",
            status=InstructionComparisonStatus.SOURCE_SUPPORTED,
            source_plan_value=sum(
                len(value.teacher_actions)
                for value in plan.instructional_phases
            ),
            current_canonical_value="Generated canonical guidance",
        ),
        InstructionComparisonItem(
            field="objectives",
            status=InstructionComparisonStatus.SOURCE_SUPPORTED,
            source_plan_value=[
                value.exact_text for value in plan.objectives
            ],
            current_canonical_value=current.get("learning_target"),
        ),
        InstructionComparisonItem(
            field="legacy_generated_content",
            status=InstructionComparisonStatus.CURRENT_GENERATED,
            source_plan_value=[],
            current_canonical_value=generated,
            notes=[
                "Not reproducible from verified curriculum sources.",
                "This does not assert that the generated content is incorrect.",
            ],
        ),
    ]
    comparison = InstructionPlanComparison(
        lesson_id=plan.lesson_id,
        plan_digest=plan.digest,
        current_source_digest=(
            current.get("source_digest") or content_digest(current)
        ),
        comparisons=items,
        not_reproducible_current_paths=generated,
        comparison_digest="pending",
    )
    return comparison.model_copy(update={
        "comparison_digest": _comparison_digest(comparison)
    })


def instruction_plan_markdown(
    plan: SourceGroundedInstructionPlan,
) -> str:
    lines = [
        f"# Source-Grounded Instruction Plan: {plan.lesson_title}",
        "",
        f"- Lesson ID: `{plan.lesson_id}`",
        f"- Bundle digest: `{plan.bundle_digest}`",
        f"- Plan digest: `{plan.digest}`",
        f"- Explicit total duration: {plan.total_duration_minutes} minutes",
        "",
        "## Source Objectives",
        "",
    ]
    lines.extend(f"- {value.exact_text}" for value in plan.objectives)
    if not plan.objectives:
        lines.append("- None explicitly available.")
    lines.extend(["", "## Source Materials", ""])
    lines.extend(f"- {value.exact_text}" for value in plan.materials)
    if not plan.materials:
        lines.append("- None exactly reproducible.")
    lines.extend([
        "",
        "## Ordered Instructional Phases",
        "",
    ])
    for phase in plan.instructional_phases:
        timing = (
            f"{phase.duration_minutes} minutes"
            if phase.duration_minutes is not None
            else "not explicitly stated"
        )
        lines.extend([
            f"### {phase.sequence}. {phase.phase_title}",
            f"- Type: {phase.phase_type}",
            f"- Day: {phase.day_label or 'preparation'}",
            f"- Duration: {timing}",
            f"- Teacher actions: {len(phase.teacher_actions)}",
            f"- Student actions: {len(phase.student_actions)}",
            f"- Questions: {len(phase.questions)}",
            "- Grouping: " + (", ".join(phase.grouping) or "none"),
            "- Assignment references: "
            + (", ".join(phase.referenced_assignment_ids) or "none"),
            "- Resource references: "
            + (", ".join(phase.referenced_resource_ids) or "none"),
            "",
        ])
        if phase.teacher_actions:
            lines.append("**Teacher actions**")
            lines.extend(
                f"- {value.exact_text}" for value in phase.teacher_actions
            )
            lines.append("")
        if phase.student_actions:
            lines.append("**Student actions**")
            lines.extend(
                f"- {value.exact_text}" for value in phase.student_actions
            )
            lines.append("")
        if phase.questions:
            lines.append("**Questions and source answers**")
        for question in phase.questions:
            lines.append(f"- Question: {question.question_text}")
            if question.answers:
                lines.extend(
                    f"  - Source answer: {answer.exact_text}"
                    for answer in question.answers
                )
            else:
                lines.append("  - Source answer: not provided")
        if phase.questions:
            lines.append("")
    lines.extend(["## Unsupported or Ambiguous Source Items", ""])
    excluded = [
        value for value in plan.audit_findings
        if not value.included_in_plan
    ]
    lines.extend(
        f"- **{value.category.value} — {value.label}**"
        + (": " + " ".join(value.notes) if value.notes else "")
        for value in excluded
    )
    if not excluded:
        lines.append("- None.")
    lines.append("")
    lines.extend(["## Warnings", ""])
    lines.extend(
        f"- **{value.code}**: {value.message}"
        for value in plan.warnings
    )
    if not plan.warnings:
        lines.append("- None.")
    return "\n".join(lines).strip() + "\n"


def instruction_comparison_markdown(
    comparison: InstructionPlanComparison,
) -> str:
    lines = [
        "# Instruction Plan Comparison",
        "",
        f"- Lesson ID: `{comparison.lesson_id}`",
        f"- Plan digest: `{comparison.plan_digest}`",
        f"- Comparison digest: `{comparison.comparison_digest}`",
        "",
    ]
    for value in comparison.comparisons:
        lines.extend([
            f"## {value.field}",
            "",
            f"- Status: **{value.status.value}**",
            f"- Source plan: `{value.source_plan_value}`",
            f"- Current canonical: `{value.current_canonical_value}`",
        ])
        lines.extend(f"- Note: {note}" for note in value.notes)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


class InstructionPlanService:
    def build(
        self,
        *,
        bundle_path: str | Path,
        current_canonical_path: str | Path,
        output_directory: str | Path,
    ) -> InstructionPlanResult:
        bundle = PreparedCurriculumSourceBundle.model_validate_json(
            Path(bundle_path).read_text(encoding="utf-8")
        )
        current = json.loads(
            Path(current_canonical_path).read_text(encoding="utf-8")
        )
        plan = SourceGroundedInstructionPlanBuilder().build(bundle)
        comparison = compare_instruction_plan(plan, current)
        output = Path(output_directory)
        plan_json = write_json(
            output / "source_grounded_instruction_plan.json", plan
        )
        plan_md = output / "source_grounded_instruction_plan.md"
        plan_md.parent.mkdir(parents=True, exist_ok=True)
        plan_md.write_text(
            instruction_plan_markdown(plan), encoding="utf-8"
        )
        comparison_json = write_json(
            output / "instruction_plan_comparison.json", comparison
        )
        comparison_md = output / "instruction_plan_comparison.md"
        comparison_md.write_text(
            instruction_comparison_markdown(comparison),
            encoding="utf-8",
        )
        return InstructionPlanResult(
            plan=plan,
            comparison=comparison,
            plan_json_path=plan_json,
            plan_markdown_path=plan_md,
            comparison_json_path=comparison_json,
            comparison_markdown_path=comparison_md,
        )


__all__ = [
    "InstructionPlanResult",
    "InstructionPlanService",
    "PLAN_BUILDER_VERSION",
    "PLAN_SCHEMA_VERSION",
    "SourceGroundedInstructionPlanBuilder",
    "compare_instruction_plan",
    "instruction_comparison_markdown",
    "instruction_plan_markdown",
    "validate_instruction_plan",
]
