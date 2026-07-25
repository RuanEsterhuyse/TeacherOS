"""CKLA translation into curriculum-agnostic source intelligence records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from curriculum.adapters.intelligence import CurriculumIntelligenceAdapter
from curriculum.intelligence.ids import stable_id
from schemas.curriculum_intelligence_schema import (
    Curriculum,
    CurriculumLesson,
    CurriculumUnit,
    ExtractionStatus,
    InstructionalResource,
    ReadinessState,
    ResolutionStatus,
    ResourceAssignment,
    ResourcePage,
    SourceProvenance,
    TextSegment,
)
from schemas.curriculum_schema import LessonIndexEntry


ACTIVITY_LABEL_RE = re.compile(
    r"\b((?:\d{1,3}\.\d{1,3})|(?:SR\.\d{1,3}))\b",
    re.IGNORECASE,
)


@dataclass
class SourceLessonTranslation:
    curriculum: Curriculum
    unit: CurriculumUnit
    lesson: CurriculumLesson
    resources: list[InstructionalResource]
    pages: dict[str, list[ResourcePage]]
    assignments: list[ResourceAssignment]
    segments: list[TextSegment]


class CKLACurriculumIntelligenceAdapter(CurriculumIntelligenceAdapter):
    adapter_id = "ckla-source-intelligence"
    adapter_version = "1.0"

    @staticmethod
    def label_activity_pages(
        pages: list[ResourcePage],
    ) -> list[ResourcePage]:
        output = []
        for page in pages:
            lines = [
                value.strip()
                for value in page.normalized_text.splitlines()[:10]
                if value.strip()
            ]
            label = None
            for line in lines[:3]:
                match = ACTIVITY_LABEL_RE.search(line)
                if match:
                    label = match.group(1).upper()
                    break
            output.append(
                page.model_copy(update={"document_page_label": label})
            )
        return output

    @staticmethod
    def _provenance(
        resource: InstructionalResource,
        pages: Iterable[ResourcePage],
        *,
        segment_id: str | None = None,
        section: str | None = None,
        confidence: float = 1.0,
    ) -> list[SourceProvenance]:
        return [
            SourceProvenance(
                resource_id=resource.id,
                resource_version=resource.resource_version,
                resource_checksum=resource.checksum,
                pdf_page_number=page.pdf_page_number,
                display_page_number=page.display_page_number,
                printed_page_label=page.printed_page_label,
                document_page_label=page.document_page_label,
                segment_id=segment_id,
                section_path=[section] if section else [],
                extraction_method=page.extraction_method,
                extraction_version=page.extraction_version,
                confidence=min(confidence, page.extraction_confidence),
            )
            for page in pages
        ]

    def _segment(
        self,
        resource: InstructionalResource,
        pages: list[ResourcePage],
        *,
        title: str,
        segment_type: str,
        sequence: int,
        confidence: float = 1.0,
    ) -> TextSegment:
        selected = [page for page in pages if page.normalized_text.strip()]
        if not selected:
            raise ValueError(f"Cannot create an empty source segment: {title}")
        segment_id = stable_id(
            "segment",
            resource.id,
            resource.resource_version,
            title,
            selected[0].pdf_page_number,
            selected[-1].pdf_page_number,
        )
        exact = "\n\n".join(page.normalized_text for page in selected)
        return TextSegment(
            id=segment_id,
            resource_id=resource.id,
            resource_page_ids=[page.id for page in selected],
            segment_type=segment_type,
            title=title,
            sequence=sequence,
            exact_text=exact,
            normalized_text=exact,
            section_path=[title],
            source_provenance=self._provenance(
                resource,
                selected,
                segment_id=segment_id,
                section=title,
                confidence=confidence,
            ),
            confidence=confidence,
        )

    @staticmethod
    def _page_with_heading(
        pages: list[ResourcePage], heading: str
    ) -> int | None:
        expected = heading.casefold()
        for page in pages:
            lines = [
                value.strip().casefold()
                for value in page.normalized_text.splitlines()[:2]
                if value.strip()
            ]
            if expected in lines:
                return page.pdf_page_number
        return None

    @staticmethod
    def _nonempty_range(
        pages: list[ResourcePage], start: int, stop: int
    ) -> list[ResourcePage]:
        selected = [
            page
            for page in pages
            if start <= page.pdf_page_number < stop
            and page.normalized_text.strip()
        ]
        return selected

    @staticmethod
    def _activity_range(
        pages: list[ResourcePage], label: str
    ) -> list[ResourcePage]:
        target = label.upper()
        starts = [
            page.pdf_page_number
            for page in pages
            if page.document_page_label == target
        ]
        if not starts:
            return []
        start = min(starts)
        later_labels = [
            page.pdf_page_number
            for page in pages
            if page.pdf_page_number > start
            and page.document_page_label
            and page.document_page_label != target
        ]
        stop = min(later_labels) if later_labels else len(pages)
        return [
            page
            for page in pages
            if start <= page.pdf_page_number < stop
            and page.normalized_text.strip()
        ]

    def _assignment(
        self,
        *,
        lesson_id: str,
        resource: InstructionalResource,
        title: str,
        assignment_type: str,
        purpose: str,
        required: bool,
        segment: TextSegment | None,
        resolution: ResolutionStatus,
        confidence: float,
        printed: list[str] | None = None,
        document_labels: list[str] | None = None,
        story_relative: list[str] | None = None,
        sections: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> ResourceAssignment:
        segment_pages = []
        if segment:
            segment_pages = segment.source_provenance
        return ResourceAssignment(
            id=stable_id(
                "assignment",
                lesson_id,
                resource.id,
                assignment_type,
                title,
            ),
            lesson_id=lesson_id,
            resource_id=resource.id,
            assignment_type=assignment_type,
            title=title,
            instructional_purpose=purpose,
            printed_page_references=printed or [],
            pdf_page_numbers=[
                value.pdf_page_number
                for value in segment_pages
                if value.pdf_page_number is not None
            ],
            display_page_numbers=[
                value.display_page_number
                for value in segment_pages
                if value.display_page_number is not None
            ],
            section_references=sections or [],
            document_labels=document_labels or [],
            story_relative_page_references=story_relative or [],
            segment_ids=[segment.id] if segment else [],
            required_status="required" if required else "optional",
            resolution_status=resolution,
            extraction_status=(
                resource.extraction_status
                if segment
                else ExtractionStatus.FAILED
            ),
            confidence=confidence,
            source_provenance=segment.source_provenance if segment else [],
            warnings=warnings or [],
        )

    def build_source_lesson(
        self,
        *,
        curriculum_id: str,
        curriculum_title: str,
        unit_title: str,
        lesson_entry: LessonIndexEntry,
        resources: dict[str, InstructionalResource],
        pages: dict[str, list[ResourcePage]],
    ) -> SourceLessonTranslation:
        guide = resources["teacher_guide"]
        book = resources["instructional_text"]
        activities = resources["activity_resource"]
        online = resources["online_resources"]
        terms = resources["terms_of_use"]
        pages["activity_resource"] = self.label_activity_pages(
            pages["activity_resource"]
        )

        curriculum = Curriculum(
            id=curriculum_id,
            title=curriculum_title,
            publisher="Core Knowledge Foundation",
            grade_or_course="8",
            subject="Language Arts",
            adapter_id=self.adapter_id,
            resource_ids=[value.id for value in resources.values()],
        )
        unit_id = stable_id("unit", curriculum_id, 1, unit_title)
        lesson_id = stable_id(
            "lesson", unit_id, lesson_entry.lesson_number, lesson_entry.lesson_title
        )

        segments: list[TextSegment] = []
        sequence = 1

        guide_pages = [
            page
            for page in pages["teacher_guide"]
            if lesson_entry.start_pdf_page
            <= page.pdf_page_number
            <= lesson_entry.end_pdf_page
        ]
        guide_segment = self._segment(
            guide,
            guide_pages,
            title="Teacher Guide Lesson 1",
            segment_type="lesson_source",
            sequence=sequence,
        )
        segments.append(guide_segment)
        sequence += 1

        intro_start = self._page_with_heading(
            pages["instructional_text"], "INTRODUCTION"
        )
        attack_start = self._page_with_heading(
            pages["instructional_text"], "THE ATTACK"
        )
        selfie_start = self._page_with_heading(
            pages["instructional_text"], "SELFIE"
        )
        guera_start = self._page_with_heading(
            pages["instructional_text"], "GÜERA"
        )
        burrito_start = self._page_with_heading(
            pages["instructional_text"], "BURRITO MAN"
        )
        refrane_start = self._page_with_heading(
            pages["instructional_text"], "TRANSLATIONS OF THE REFRANES"
        )
        notes_start = self._page_with_heading(
            pages["instructional_text"], "NOTES ON THE STORIES"
        )
        author_start = self._page_with_heading(
            pages["instructional_text"], "ABOUT THE AUTHOR"
        )

        def book_segment(
            title: str,
            start: int | None,
            stop: int | None,
            segment_type: str,
        ) -> TextSegment | None:
            nonlocal sequence
            if start is None or stop is None:
                return None
            selected = self._nonempty_range(
                pages["instructional_text"], start, stop
            )
            if not selected:
                return None
            value = self._segment(
                book,
                selected,
                title=title,
                segment_type=segment_type,
                sequence=sequence,
            )
            sequence += 1
            segments.append(value)
            return value

        intro_segment = book_segment(
            "Trade-book introduction",
            intro_start,
            attack_start,
            "introduction",
        )
        attack_segment = book_segment(
            "The Attack", attack_start, selfie_start, "assigned_text"
        )
        guera_segment = book_segment(
            "Güera", guera_start, burrito_start, "homework_text"
        )
        refrane_segment = book_segment(
            "Relevant refranes",
            refrane_start,
            notes_start,
            "reference_text",
        )
        notes_segment = book_segment(
            "Relevant story notes",
            notes_start,
            author_start,
            "reference_text",
        )

        activity_segments: dict[str, TextSegment | None] = {}
        for label, title in (
            ("1.1", "Activity Resource 1.1"),
            ("1.2", "Activity Resource 1.2"),
            ("1.3", "Activity Resource 1.3"),
            ("SR.1", "Student Resource SR.1"),
        ):
            selected = self._activity_range(
                pages["activity_resource"], label
            )
            segment = (
                self._segment(
                    activities,
                    selected,
                    title=title,
                    segment_type="activity_resource",
                    sequence=sequence,
                )
                if selected
                else None
            )
            if segment:
                segments.append(segment)
                sequence += 1
            activity_segments[label] = segment

        online_page = next(
            (
                page
                for page in pages["online_resources"]
                if any(
                    heading.casefold() == "lesson 1"
                    for heading in page.headings
                )
                and "Maps of North and South America"
                in page.normalized_text
            ),
            None,
        )
        online_segment = (
            self._segment(
                online,
                [online_page],
                title="Lesson 1 Online Resources",
                segment_type="online_resource_index",
                sequence=sequence,
            )
            if online_page
            else None
        )
        if online_segment:
            segments.append(online_segment)
            sequence += 1

        terms_segment = (
            self._segment(
                terms,
                pages["terms_of_use"],
                title="Curriculum terms of use",
                segment_type="license",
                sequence=sequence,
            )
            if pages["terms_of_use"]
            else None
        )
        if terms_segment:
            segments.append(terms_segment)

        assignments = [
            self._assignment(
                lesson_id=lesson_id,
                resource=guide,
                title="Teacher Guide Lesson 1 range",
                assignment_type="defines_lesson",
                purpose="Define Lesson 1 source boundaries and requirements.",
                required=True,
                segment=guide_segment,
                resolution=ResolutionStatus.RESOLVED,
                confidence=lesson_entry.confidence,
                printed=[
                    f"{lesson_entry.start_printed_page}–"
                    f"{lesson_entry.end_printed_page}"
                ],
                sections=[lesson_entry.detected_heading],
            ),
            self._assignment(
                lesson_id=lesson_id,
                resource=book,
                title="Trade-book introduction",
                assignment_type="background_reading",
                purpose="Provide the author introduction assigned in Lesson 1.",
                required=True,
                segment=intro_segment,
                resolution=(
                    ResolutionStatus.PARTIAL
                    if intro_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=0.9 if intro_segment else 0,
                story_relative=["viii–xi"],
                sections=["Introduction"],
                warnings=[
                    "The titled introduction is resolved, but printed Roman-numeral pages are absent from the registered PDF."
                ],
            ),
            self._assignment(
                lesson_id=lesson_id,
                resource=book,
                title="The Attack",
                assignment_type="assigned_reading",
                purpose="Provide the primary Lesson 1 read-aloud text.",
                required=True,
                segment=attack_segment,
                resolution=(
                    ResolutionStatus.PARTIAL
                    if attack_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=0.95 if attack_segment else 0,
                story_relative=["1–15"],
                sections=["The Attack"],
                warnings=[
                    "The complete titled story section is resolved; story-relative pages 1–15 cannot be mapped to printed or PDF pages in this reflowed edition."
                ],
            ),
        ]
        for label, assignment_type, purpose in (
            ("1.1", "activity", "Provide the assigned family letter."),
            ("1.2", "vocabulary_reference", "Provide Lesson 1 vocabulary support."),
            ("1.3", "homework", "Provide the assigned homework response page."),
            ("SR.1", "vocabulary_reference", "Provide the assigned student glossary."),
        ):
            segment = activity_segments[label]
            assignments.append(self._assignment(
                lesson_id=lesson_id,
                resource=activities,
                title=(
                    f"Activity Resource {label}"
                    if label != "SR.1"
                    else "Student Resource SR.1"
                ),
                assignment_type=assignment_type,
                purpose=purpose,
                required=True,
                segment=segment,
                resolution=(
                    ResolutionStatus.RESOLVED
                    if segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=1.0 if segment else 0,
                document_labels=[label],
            ))
        assignments.extend([
            self._assignment(
                lesson_id=lesson_id,
                resource=book,
                title="Güera homework reading",
                assignment_type="homework",
                purpose="Provide the assigned Lesson 1 homework reading.",
                required=True,
                segment=guera_segment,
                resolution=(
                    ResolutionStatus.PARTIAL
                    if guera_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=0.95 if guera_segment else 0,
                story_relative=["51–57"],
                sections=["Güera"],
                warnings=[
                    "The complete titled story section is resolved; story-relative pages 51–57 cannot be mapped in this reflowed edition."
                ],
            ),
            self._assignment(
                lesson_id=lesson_id,
                resource=book,
                title="Relevant refrane reference",
                assignment_type="teacher_reference",
                purpose="Provide the refrane translation referenced by Lesson 1.",
                required=True,
                segment=refrane_segment,
                resolution=(
                    ResolutionStatus.PARTIAL
                    if refrane_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=0.9 if refrane_segment else 0,
                story_relative=["228–230"],
                sections=["Translations of the Refranes", "The Attack"],
                warnings=[
                    "The titled refrane section is resolved; printed pages 228–230 cannot be mapped in this reflowed edition."
                ],
            ),
            self._assignment(
                lesson_id=lesson_id,
                resource=book,
                title="Relevant story notes",
                assignment_type="teacher_reference",
                purpose="Provide story background notes referenced by Lesson 1.",
                required=True,
                segment=notes_segment,
                resolution=(
                    ResolutionStatus.PARTIAL
                    if notes_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=0.9 if notes_segment else 0,
                story_relative=["231"],
                sections=["Notes on the Stories", "The Attack"],
                warnings=[
                    "The titled notes section is resolved; printed page 231 cannot be mapped in this reflowed edition."
                ],
            ),
            self._assignment(
                lesson_id=lesson_id,
                resource=online,
                title="Lesson 1 Online Resources",
                assignment_type="visual_resource",
                purpose="Provide maps and teacher identity resources assigned to Lesson 1.",
                required=True,
                segment=online_segment,
                resolution=(
                    ResolutionStatus.RESOLVED
                    if online_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=1.0 if online_segment else 0,
                sections=[
                    "Maps of North and South America",
                    "Resources for Teachers: Teaching Identity",
                ],
            ),
            self._assignment(
                lesson_id=lesson_id,
                resource=terms,
                title="Curriculum terms of use",
                assignment_type="license_reference",
                purpose="Preserve the registered curriculum-use terms.",
                required=False,
                segment=terms_segment,
                resolution=(
                    ResolutionStatus.RESOLVED
                    if terms_segment
                    else ResolutionStatus.UNRESOLVED
                ),
                confidence=1.0 if terms_segment else 0,
                sections=["Terms of Use"],
            ),
        ])
        lesson = CurriculumLesson(
            id=lesson_id,
            curriculum_id=curriculum_id,
            unit_id=unit_id,
            grade_or_course="8",
            sequence=1,
            title=lesson_entry.lesson_title or "Read-Aloud: “The Attack”",
            assignment_ids=[value.id for value in assignments],
            standards=list(lesson_entry.standards),
            objectives=list(lesson_entry.lesson_objective),
            materials=list(lesson_entry.materials),
            homework=list(lesson_entry.homework),
            assessment_references=list(lesson_entry.assessment_references),
            source_provenance=guide_segment.source_provenance,
            readiness_state=ReadinessState.MAPPED,
        )
        unit = CurriculumUnit(
            id=unit_id,
            curriculum_id=curriculum_id,
            title=unit_title,
            sequence=1,
            lesson_ids=[lesson_id],
            linked_resource_ids=[value.id for value in resources.values()],
            source_provenance=guide_segment.source_provenance,
        )
        curriculum = curriculum.model_copy(update={"unit_ids": [unit_id]})
        return SourceLessonTranslation(
            curriculum=curriculum,
            unit=unit,
            lesson=lesson,
            resources=list(resources.values()),
            pages=pages,
            assignments=assignments,
            segments=segments,
        )


__all__ = [
    "CKLACurriculumIntelligenceAdapter",
    "SourceLessonTranslation",
]
