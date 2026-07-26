"""CKLA translation into curriculum-agnostic source intelligence records."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from curriculum.adapters.intelligence import CurriculumIntelligenceAdapter
from curriculum.intelligence.ids import stable_id
from curriculum.intelligence.mappings import coordinate_mapping_id
from schemas.curriculum_intelligence_schema import (
    Curriculum,
    CurriculumLesson,
    CurriculumUnit,
    ExtractionStatus,
    InstructionalResource,
    MappingMethod,
    MappingReviewStatus,
    ReadinessState,
    ResolutionStatus,
    ResourceAssignment,
    ResourcePage,
    SourceProvenance,
    SourceCoordinateMapping,
    TextSegment,
)
from schemas.curriculum_mapping_proposal_schema import (
    LessonResourceMappingManifest,
    ProposalStatus,
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
    coordinate_mappings: list[SourceCoordinateMapping] = field(
        default_factory=list
    )


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

    def build_source_lesson_from_manifest(
        self,
        *,
        curriculum_id: str,
        curriculum_title: str,
        unit_title: str,
        lesson_entry: LessonIndexEntry,
        manifest: LessonResourceMappingManifest,
        resources: dict[str, InstructionalResource],
        pages: dict[str, list[ResourcePage]],
    ) -> SourceLessonTranslation:
        """Translate reviewed assignment configuration into source records."""
        if manifest.lesson_number != lesson_entry.lesson_number:
            raise ValueError("Mapping manifest lesson does not match the index.")
        if manifest.grade != "8" or manifest.unit_number != 1:
            raise ValueError("Mapping manifest does not match the registered unit.")

        curriculum = Curriculum(
            id=curriculum_id,
            title=curriculum_title,
            publisher="Core Knowledge Foundation",
            grade_or_course=manifest.grade,
            subject="Language Arts",
            adapter_id=self.adapter_id,
            resource_ids=[value.id for value in resources.values()],
        )
        unit_id = stable_id(
            "unit", curriculum_id, manifest.unit_number, unit_title
        )
        lesson_id = stable_id(
            "lesson",
            unit_id,
            lesson_entry.lesson_number,
            lesson_entry.lesson_title,
        )
        resource_by_id = {value.id: value for value in resources.values()}
        pages_by_id = {
            resources[key].id: value for key, value in pages.items()
        }
        guide = resources["teacher_guide"]
        online = resources["online_resources"]
        role_types = {
            "defines_lesson": "defines_lesson",
            "assigned_reading": "assigned_reading",
            "assessment_reading": "assigned_reading",
            "activity_resource": "activity",
            "assessment_resource": "assessment",
            "shared_review_activity": "activity",
            "shared_review_answer_key": "teacher_reference",
            "prior_lesson_homework_review": "background_reading",
            "prior_lesson_activity_review": "activity",
            "vocabulary_resource": "vocabulary_reference",
            "homework_writing": "homework",
            "grammar_practice_and_homework": "activity",
            "writing_plan": "activity",
            "homework_writing_plan": "homework",
            "prior_lesson_activity_answer_key": "teacher_reference",
            "publisher_answer_key": "teacher_reference",
            "translation_reference": "teacher_reference",
            "refrane_reference": "teacher_reference",
            "story_notes": "teacher_reference",
            "online_teacher_resources": "teacher_reference",
            "embedded_teacher_chart": "teacher_reference",
            "teacher_chart": "teacher_reference",
            "classroom_map": "visual_resource",
        }
        if manifest.lesson_number >= 3:
            role_types["story_notes"] = "background_reading"
        optional_roles = {
            "prior_lesson_activity_answer_key",
            "publisher_answer_key",
            "shared_review_answer_key",
            "online_teacher_resources",
            "classroom_map",
        }
        purposes = {
            "defines_lesson": "Define the indexed lesson source boundary and requirements.",
            "assigned_reading": "Provide the assigned instructional reading.",
            "assessment_reading": "Provide the assigned assessment reading.",
            "activity_resource": "Provide the assigned student activity resource.",
            "assessment_resource": "Provide the assigned assessment resource.",
            "shared_review_activity": "Provide the explicitly referenced prior activity for review.",
            "shared_review_answer_key": "Provide the explicitly referenced prior activity answer key.",
            "prior_lesson_homework_review": "Provide the prior homework text required for Lesson 2 review.",
            "prior_lesson_activity_review": "Provide the prior activity required for Lesson 2 review.",
            "vocabulary_resource": "Provide the assigned vocabulary activity.",
            "homework_writing": "Provide the assigned writing homework.",
            "grammar_practice_and_homework": "Provide the assigned grammar practice and homework.",
            "writing_plan": "Provide the assigned narrative planning activity.",
            "homework_writing_plan": "Provide the assigned narrative-planning homework.",
            "prior_lesson_activity_answer_key": "Provide the explicitly labeled publisher answer key.",
            "publisher_answer_key": "Provide the explicitly labeled publisher answer key.",
            "translation_reference": "Provide the assigned translation reference.",
            "refrane_reference": "Provide the assigned refrane translation reference.",
            "story_notes": "Provide the assigned story notes.",
            "online_teacher_resources": "Record the Lesson 2 online-resource index.",
            "embedded_teacher_chart": "Provide the assigned Teacher Guide chart.",
            "teacher_chart": "Provide the assigned Teacher Guide chart.",
            "classroom_map": "Record the required teacher-supplied classroom map.",
        }
        guided_roles = {
            "guided_reading_range",
            "guided_reading_continuation",
        }
        guided_by_story: dict[str, list] = {}
        for configured in manifest.assignments:
            if configured.resource_role not in guided_roles:
                continue
            parent = next(
                (
                    assignment.title_or_label
                    for assignment in manifest.assignments
                    if (
                        assignment.resource_role == "assigned_reading"
                        and configured.title_or_label.startswith(
                            f"{assignment.title_or_label} guided"
                        )
                    )
                ),
                None,
            )
            if parent is None:
                raise ValueError(
                    "Guided-reading reference is not tied to an approved "
                    f"parent story: {configured.title_or_label}."
                )
            guided_by_story.setdefault(parent, []).append(configured)

        segments: list[TextSegment] = []
        assignments: list[ResourceAssignment] = []
        mappings: list[SourceCoordinateMapping] = []
        sequence = 1
        for configured in manifest.assignments:
            if configured.resource_role in guided_roles:
                continue
            if configured.resource_role not in role_types:
                raise ValueError(
                    "Unsupported configured assignment role: "
                    f"{configured.resource_role}."
                )
            resource = (
                resource_by_id.get(configured.resolved_resource_id)
                if configured.resolved_resource_id
                else online
            )
            if resource is None:
                raise ValueError(
                    f"Configured resource is not registered: "
                    f"{configured.resolved_resource_id}"
                )
            selected: list[ResourcePage] = []
            segment = None
            if configured.proposed_pdf_start_page is not None:
                selected = [
                    page
                    for page in pages_by_id.get(resource.id, [])
                    if configured.proposed_pdf_start_page
                    <= page.pdf_page_number
                    <= configured.proposed_pdf_end_page
                ]
                expected = set(range(
                    configured.proposed_pdf_start_page,
                    configured.proposed_pdf_end_page + 1,
                ))
                if {page.pdf_page_number for page in selected} != expected:
                    raise ValueError(
                        f"Approved range for {configured.title_or_label} is "
                        "missing registered page text."
                    )
                segment = self._segment(
                    resource,
                    selected,
                    title=configured.title_or_label,
                    segment_type=configured.resource_role,
                    sequence=sequence,
                    confidence=configured.confidence,
                )
                segments.append(segment)
                sequence += 1

            reviewed = (
                configured.verification_status
                == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
            )
            resolved = (
                segment is not None
                and configured.verification_status
                in {
                    ProposalStatus.DETERMINISTICALLY_VERIFIED,
                    ProposalStatus.HUMAN_REVIEWED_OVERRIDE,
                }
            )
            warnings = list(dict.fromkeys(
                configured.ambiguity_notes
                + [
                    note
                    for evidence in configured.evidence
                    for note in evidence.evidence_notes
                ]
            ))
            guided = guided_by_story.get(configured.title_or_label, [])
            if guided:
                warnings.append(
                    "Publisher guided-reading references are attached to "
                    "this approved parent story without inferred PDF "
                    "subranges."
                )
            if configured.resource_role == "classroom_map":
                warnings.append(
                    (
                        "Required teacher-supplied material is unavailable "
                        "in registered sources; supply or display an "
                        "appropriate map of North and Central America."
                    )
                    if manifest.lesson_number == 2
                    else (
                        "Required teacher-supplied map is unavailable in "
                        "registered sources; supply the publisher-referenced "
                        "map before teaching."
                    )
                )
            assignment = ResourceAssignment(
                id=configured.assignment_id,
                lesson_id=lesson_id,
                resource_id=resource.id,
                assignment_type=role_types[configured.resource_role],
                title=configured.title_or_label,
                instructional_purpose=purposes[configured.resource_role],
                printed_page_references=list(dict.fromkeys(
                    configured.referenced_printed_pages
                    + [
                        reference
                        for item in guided
                        for reference in item.referenced_printed_pages
                    ]
                )),
                pdf_page_numbers=[
                    page.pdf_page_number for page in selected
                ],
                display_page_numbers=[
                    page.display_page_number for page in selected
                ],
                section_references=[
                    evidence.source_heading
                    for item in [configured] + guided
                    for evidence in item.evidence
                    if evidence.source_heading
                ],
                document_labels=(
                    [configured.title_or_label.rsplit(" ", 1)[-1]]
                    if configured.title_or_label.startswith("Activity Page ")
                    else []
                ),
                story_relative_page_references=(
                    list(dict.fromkeys(
                        configured.referenced_printed_pages
                        + [
                            item.curriculum_reference for item in guided
                        ]
                    ))
                    if configured.resource_type == "instructional_text"
                    else []
                ),
                segment_ids=[segment.id] if segment else [],
                required_status=(
                    "optional"
                    if configured.resource_role in optional_roles
                    else configured.required_status
                ),
                resolution_status=(
                    ResolutionStatus.PARTIAL
                    if reviewed
                    else (
                        ResolutionStatus.RESOLVED
                        if resolved
                        else ResolutionStatus.UNRESOLVED
                    )
                ),
                extraction_status=(
                    resource.extraction_status
                    if segment
                    else ExtractionStatus.UNAVAILABLE
                ),
                confidence=configured.confidence,
                source_provenance=(
                    segment.source_provenance if segment else []
                ),
                warnings=warnings,
            )
            assignments.append(assignment)
            if reviewed and segment:
                reference_value = (
                    configured.referenced_printed_pages[0]
                    if configured.referenced_printed_pages
                    else configured.curriculum_reference
                )
                mapping = SourceCoordinateMapping(
                    id=coordinate_mapping_id(
                        assignment.id,
                        "curriculum_reference",
                        reference_value,
                        "pdf_page_range",
                    ),
                    lesson_id=lesson_id,
                    assignment_id=assignment.id,
                    resource_id=resource.id,
                    source_version=resource.resource_version,
                    resource_checksum=resource.checksum,
                    extraction_version=resource.extraction_version,
                    reference_system="curriculum_reference",
                    reference_value=reference_value,
                    target_coordinate_system="pdf_page_range",
                    target_pdf_start_page=selected[0].pdf_page_number,
                    target_pdf_end_page=selected[-1].pdf_page_number,
                    target_display_start_page=selected[0].display_page_number,
                    target_display_end_page=selected[-1].display_page_number,
                    target_segment_ids=[segment.id],
                    mapping_method=MappingMethod.HUMAN_REVIEWED_OVERRIDE,
                    confidence=1,
                    review_status=MappingReviewStatus.VERIFIED,
                    reviewer_type="human",
                    reviewer_note=configured.reviewer_note or "",
                    created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
                    mapping_version="1.0",
                    warnings=warnings,
                )
                mappings.append(mapping)

        guide_assignment = next(
            value for value in assignments
            if value.assignment_type == "defines_lesson"
        )
        objectives = [
            value for value in lesson_entry.lesson_objective
            if not re.fullmatch(
                r"Core Knowledge Language Arts\s*\|\s*Grade 8\s+"
                r"Lesson \d+\s*\|\s*Unit 1\s+\d+",
                value,
                re.IGNORECASE,
            )
        ]
        lesson = CurriculumLesson(
            id=lesson_id,
            curriculum_id=curriculum_id,
            unit_id=unit_id,
            grade_or_course=manifest.grade,
            sequence=lesson_entry.lesson_number,
            title=lesson_entry.lesson_title or f"Lesson {lesson_entry.lesson_number}",
            assignment_ids=[value.id for value in assignments],
            standards=list(lesson_entry.standards),
            objectives=objectives,
            materials=list(lesson_entry.materials),
            homework=list(lesson_entry.homework),
            assessment_references=list(lesson_entry.assessment_references),
            source_provenance=guide_assignment.source_provenance,
            readiness_state=ReadinessState.MAPPED,
        )
        unit = CurriculumUnit(
            id=unit_id,
            curriculum_id=curriculum_id,
            title=unit_title,
            sequence=manifest.unit_number,
            lesson_ids=[lesson_id],
            linked_resource_ids=[value.id for value in resources.values()],
            source_provenance=guide_assignment.source_provenance,
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
            coordinate_mappings=mappings,
        )


__all__ = [
    "CKLACurriculumIntelligenceAdapter",
    "SourceLessonTranslation",
]
