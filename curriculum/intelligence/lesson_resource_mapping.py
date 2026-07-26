"""Deterministic, review-only resource mapping for indexed curriculum lessons."""

from __future__ import annotations

import re
from pathlib import Path

from curriculum.intelligence.ids import stable_id
from curriculum.intelligence.repository import CurriculumIntelligenceRepository
from curriculum.lesson_locator import CKLALessonLocator
from schemas.curriculum_intelligence_schema import InstructionalResource, ResourcePage
from schemas.curriculum_mapping_proposal_schema import (
    LessonResourceMappingManifest,
    MappingEvidence,
    ProposalStatus,
    ResourceAssignmentProposal,
)


LESSON_TWO_BUILDER_VERSION = "1.0"


def _flat(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _excerpt(value: str, *, beginning: bool) -> str:
    text = _flat(value)
    if len(text) <= 260:
        return text
    return text[:260].rstrip() + "…" if beginning else "…" + text[-260:].lstrip()


def _resource_by_type(
    resources: list[InstructionalResource], resource_type: str
) -> InstructionalResource:
    matches = [value for value in resources if value.resource_type == resource_type]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one registered {resource_type} resource, found {len(matches)}."
        )
    return matches[0]


def _page_containing(pages: list[ResourcePage], exact_text: str) -> ResourcePage:
    needle = _flat(exact_text)
    matches = [page for page in pages if needle in _flat(page.normalized_text)]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one Teacher Guide page for exact reference {exact_text!r}, "
            f"found {len(matches)}."
        )
    return matches[0]


def _label_range(pages: list[ResourcePage], label: str) -> tuple[int, int]:
    starts = [
        index for index, page in enumerate(pages)
        if page.document_page_label == label
        and "continued" not in page.normalized_text[:80].casefold()
    ]
    if len(starts) != 1:
        raise ValueError(
            f"Expected one start page for Activity Book label {label}, found "
            f"{len(starts)}."
        )
    start_index = starts[0]
    end_index = start_index
    for index in range(start_index + 1, len(pages)):
        page = pages[index]
        if page.document_page_label and page.document_page_label != label:
            break
        end_index = index
    while end_index > start_index and not _flat(pages[end_index].normalized_text):
        end_index -= 1
    return pages[start_index].pdf_page_number, pages[end_index].pdf_page_number


def _story_range(
    pages: list[ResourcePage], heading: str, next_heading: str
) -> tuple[int, int, ResourcePage, ResourcePage]:
    starts = [
        page for page in pages
        if any(value.casefold() == heading.casefold() for value in page.headings)
        and _flat(page.normalized_text).casefold().startswith(heading.casefold())
    ]
    stops = [
        page for page in pages
        if any(value.casefold() == next_heading.casefold() for value in page.headings)
        and _flat(page.normalized_text).casefold().startswith(next_heading.casefold())
    ]
    if len(starts) != 1 or len(stops) != 1:
        raise ValueError(
            f"Could not determine unique heading boundaries for {heading}."
        )
    selected = [
        page for page in pages
        if starts[0].pdf_page_number <= page.pdf_page_number < stops[0].pdf_page_number
        and _flat(page.normalized_text)
    ]
    if not selected:
        raise ValueError(f"No extracted text was found for {heading}.")
    return (
        selected[0].pdf_page_number,
        selected[-1].pdf_page_number,
        selected[0],
        selected[-1],
    )


def _evidence(
    page: ResourcePage,
    exact_text: str,
    *,
    heading: str | None = None,
    beginning: str | None = None,
    ending: str | None = None,
    notes: list[str] | None = None,
) -> MappingEvidence:
    return MappingEvidence(
        teacher_guide_pdf_page=page.pdf_page_number,
        teacher_guide_printed_page=page.printed_page_label,
        exact_reference_text=exact_text,
        source_heading=heading,
        beginning_excerpt=beginning,
        ending_excerpt=ending,
        evidence_notes=notes or [],
    )


class LessonTwoResourceMappingBuilder:
    """Build a proposal without changing production intelligence records."""

    def build(
        self,
        *,
        index_path: str | Path,
        repository: CurriculumIntelligenceRepository,
    ) -> LessonResourceMappingManifest:
        index = CKLALessonLocator().load_index(index_path)
        entry = CKLALessonLocator.get_lesson_entry(index, 2)
        resources = repository.load_all_resources()
        guide = _resource_by_type(resources, "teacher_guide")
        reader = _resource_by_type(resources, "instructional_text")
        activity = _resource_by_type(resources, "activity_resource")
        online = _resource_by_type(resources, "online_resource_guide")
        guide_pages_all = repository.load_resource_pages(guide.id)
        guide_pages = [
            page for page in guide_pages_all
            if entry.start_pdf_page <= page.pdf_page_number <= entry.end_pdf_page
        ]
        if [page.pdf_page_number for page in guide_pages] != list(
            range(entry.start_pdf_page, entry.end_pdf_page + 1)
        ):
            raise ValueError("Lesson 2 Teacher Guide boundary pages are incomplete.")
        reader_pages = repository.load_resource_pages(reader.id)
        activity_pages = repository.load_resource_pages(activity.id)
        online_pages = repository.load_resource_pages(online.id)
        assignments: list[ResourceAssignmentProposal] = []

        def add(
            *,
            role: str,
            resource_type: str,
            reference: str,
            title: str,
            evidence_text: str,
            resource: InstructionalResource | None,
            pdf_range: tuple[int, int] | None,
            method: str,
            status: ProposalStatus,
            confidence: float,
            heading: str | None = None,
            beginning: str | None = None,
            ending: str | None = None,
            notes: list[str] | None = None,
            printed: list[str] | None = None,
        ) -> None:
            evidence_page = _page_containing(guide_pages, evidence_text)
            assignments.append(ResourceAssignmentProposal(
                assignment_id=stable_id(
                    "mapping-proposal", index.curriculum.unit, 2, role, reference
                ),
                unit_number=1,
                lesson_number=2,
                resource_role=role,
                resource_type=resource_type,
                curriculum_reference=reference,
                title_or_label=title,
                referenced_printed_pages=printed or [],
                resolved_resource_id=resource.id if resource else None,
                proposed_pdf_start_page=pdf_range[0] if pdf_range else None,
                proposed_pdf_end_page=pdf_range[1] if pdf_range else None,
                resolution_method=method,
                confidence=confidence,
                verification_status=status,
                evidence=[_evidence(
                    evidence_page, evidence_text, heading=heading,
                    beginning=beginning, ending=ending, notes=notes,
                )],
                ambiguity_notes=notes or [],
                human_review_required=status in {
                    ProposalStatus.PROPOSED_FOR_REVIEW,
                    ProposalStatus.UNRESOLVED,
                },
            ))

        add(
            role="defines_lesson", resource_type="teacher_guide",
            reference="Lesson 2, printed pages 42–57",
            title="Teacher Guide Lesson 2 range",
            evidence_text="Lesson 2 AT A GLANCE CHART",
            resource=guide, pdf_range=(47, 62),
            method="saved_index_exact_boundary",
            status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
            confidence=1, heading="Lesson 2",
            beginning=_excerpt(guide_pages[0].normalized_text, beginning=True),
            ending=_excerpt(guide_pages[-1].normalized_text, beginning=False),
            printed=["42–57"],
        )

        burrito = _story_range(reader_pages, "BURRITO MAN", "BAND-AID")
        add(
            role="assigned_reading", resource_type="instructional_text",
            reference="“Burrito Man” [pages 59–69]",
            title="Burrito Man", evidence_text=(
                "Whole Group: “Burrito Man” and “Band-Aid” [pages 59–69 and 71–91]"
            ),
            resource=reader, pdf_range=burrito[:2],
            method="exact_story_heading_to_next_story_heading",
            status=ProposalStatus.PROPOSED_FOR_REVIEW, confidence=.94,
            heading="BURRITO MAN",
            beginning=_excerpt(burrito[2].normalized_text, beginning=True),
            ending=_excerpt(burrito[3].normalized_text, beginning=False),
            notes=[
                "The story heading and next-story boundary are exact, but the "
                "registered reflowed PDF does not expose printed pages 59–69."
            ], printed=["59–69"],
        )
        bandaid = _story_range(reader_pages, "BAND-AID", "FIRSTBORN")
        add(
            role="assigned_reading", resource_type="instructional_text",
            reference="“Band-Aid” [pages 71–91]",
            title="Band-Aid", evidence_text=(
                "Whole Group: “Burrito Man” and “Band-Aid” [pages 59–69 and 71–91]"
            ),
            resource=reader, pdf_range=bandaid[:2],
            method="exact_story_heading_to_next_story_heading",
            status=ProposalStatus.PROPOSED_FOR_REVIEW, confidence=.9,
            heading="BAND-AID",
            beginning=_excerpt(bandaid[2].normalized_text, beginning=True),
            ending=_excerpt(bandaid[3].normalized_text, beginning=False),
            notes=[
                "The at-a-glance reference ends at page 91, while guided reading "
                "continues through page 92. The reflowed PDF has no printed labels."
            ], printed=["71–91", "guided reading through 92"],
        )

        guera = _story_range(reader_pages, "GÜERA", "BURRITO MAN")
        add(
            role="prior_lesson_homework_review",
            resource_type="instructional_text",
            reference="homework reading “Güera” (pages 51–57)",
            title="Güera", evidence_text=(
                "Read and be prepared to discuss the homework reading “Güera” "
                "(pages 51–57) and accompanying Activity Page 1.3."
            ),
            resource=reader, pdf_range=guera[:2],
            method="exact_story_heading_to_next_story_heading",
            status=ProposalStatus.PROPOSED_FOR_REVIEW, confidence=.95,
            heading="GÜERA",
            beginning=_excerpt(guera[2].normalized_text, beginning=True),
            ending=_excerpt(guera[3].normalized_text, beginning=False),
            notes=[
                "This is an explicit Lesson 2 review dependency, not a copied "
                "Lesson 1 assignment. Printed-page equivalence is not "
                "deterministically exposed by the registered reflowed text."
            ], printed=["51–57"],
        )

        for label, role, evidence_text in [
            ("1.3", "prior_lesson_activity_review", "Activity Page 1.3 (for review)"),
            ("2.1", "vocabulary_resource", "Have students reference Activity Page 2.1"),
            ("2.2", "homework_writing", "Activity Page 2.2 for homework"),
            ("2.3", "grammar_practice_and_homework", "Have students turn to Activity Page 2.3."),
            ("2.4", "writing_plan", "Have students complete Activity Page 2.4"),
            ("2.5", "homework_writing_plan", "Activity Page 2.5 as homework"),
        ]:
            page_range = _label_range(activity_pages, label)
            start_page = next(
                page for page in activity_pages
                if page.pdf_page_number == page_range[0]
            )
            end_page = next(
                page for page in activity_pages
                if page.pdf_page_number == page_range[1]
            )
            add(
                role=role, resource_type="activity_resource",
                reference=f"Activity Page {label}", title=f"Activity Page {label}",
                evidence_text=evidence_text, resource=activity,
                pdf_range=page_range, method="exact_document_label_boundary",
                status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                confidence=1, heading=start_page.headings[0] if start_page.headings else label,
                beginning=_excerpt(start_page.normalized_text, beginning=True),
                ending=_excerpt(end_page.normalized_text, beginning=False),
                printed=[label],
            )

        def answer_key(label: str, role: str, evidence_text: str) -> None:
            matches = [
                page for page in guide_pages_all
                if "Answer Key" in page.headings
                and re.search(
                    rf"(?:ACTIVITY PAGE|TAKE-HOME)\s+{re.escape(label)}\b",
                    page.normalized_text,
                    re.I,
                )
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Expected one exact answer-key page for {label}, found {len(matches)}."
                )
            page = matches[0]
            add(
                role=role, resource_type="teacher_guide_answer_key",
                reference=f"Activity Page {label} answer key",
                title=f"Answer Key {label}", evidence_text=evidence_text,
                resource=guide, pdf_range=(page.pdf_page_number, page.pdf_page_number),
                method="exact_answer_key_heading_and_activity_label",
                status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                confidence=1, heading="Activity Book Answer Key",
                beginning=_excerpt(page.normalized_text, beginning=True),
                ending=_excerpt(page.normalized_text, beginning=False),
                notes=[
                    "The answer-key page may contain multiple activity facsimiles; "
                    "only the explicitly matching label is in scope."
                ],
            )

        answer_key("1.3", "prior_lesson_activity_answer_key", "Activity Page 1.3 (for review)")
        answer_key("2.2", "publisher_answer_key", "Activity Page 2.2 for homework")
        answer_key("2.3", "publisher_answer_key", "Have students turn to Activity Page 2.3.")

        for role, reference, heading, candidate_pages, evidence_text, note in [
            (
                "translation_reference", "Spanish translations beginning page 217",
                "Band-Aid", (123, 124),
                "translations of Spanish words and phrases used in the stories can be found beginning on page 217",
                "The extracted translation pages contain exact Burrito Man and Band-Aid subsection headings, but printed page 217 is absent.",
            ),
            (
                "refrane_reference", "refrane translations beginning page 228",
                "TRANSLATIONS OF THE REFRANES", (128, 128),
                "Translations of the refranes that accompany each story begin on page 228.",
                "The section heading and both story labels are exact; printed page 228 is absent from the reflowed PDF.",
            ),
            (
                "story_notes", "notes on the stories on pages 235–236",
                "NOTES ON THE STORIES", (131, 132),
                "Have students read the notes on the stories on pages 235–236.",
                "The notes contain Burrito Man and Band-Aid headings, but printed pages 235–236 are absent.",
            ),
        ]:
            first = next(page for page in reader_pages if page.pdf_page_number == candidate_pages[0])
            last = next(page for page in reader_pages if page.pdf_page_number == candidate_pages[1])
            add(
                role=role, resource_type="instructional_text",
                reference=reference, title=heading, evidence_text=evidence_text,
                resource=reader, pdf_range=candidate_pages,
                method="exact_section_and_story_labels",
                status=ProposalStatus.PROPOSED_FOR_REVIEW,
                confidence=.86, heading=heading,
                beginning=_excerpt(first.normalized_text, beginning=True),
                ending=_excerpt(last.normalized_text, beginning=False),
                notes=[note], printed=[reference],
            )

        online_matches = [
            page for page in online_pages
            if any(heading.casefold() == "lesson 2" for heading in page.headings)
            and _flat(page.normalized_text).casefold().startswith(
                "online resources lesson 2"
            )
        ]
        if len(online_matches) != 1:
            raise ValueError(
                f"Expected one Lesson 2 online-resource page, found {len(online_matches)}."
            )
        online_page = online_matches[0]
        add(
            role="online_teacher_resources", resource_type="online_resource_guide",
            reference="CKLA Online Resources for this unit: Lesson 2",
            title="Lesson 2 Online Resources",
            evidence_text="The CKLA Online Resources for this unit have information about these topics.",
            resource=online, pdf_range=(online_page.pdf_page_number, online_page.pdf_page_number),
            method="exact_lesson_number_heading",
            status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
            confidence=1, heading="Lesson 2",
            beginning=_excerpt(online_page.normalized_text, beginning=True),
            ending=_excerpt(online_page.normalized_text, beginning=False),
        )

        for role, reference, evidence_text, page_number in [
            (
                "embedded_teacher_chart",
                "Using Punctuation to Indicate Pauses and Breaks Chart, Teacher Guide page 55",
                "Using Punctuation to Indicate Pauses and Breaks Chart Commas Used to Indicate Pauses Between Items in a List",
                60,
            ),
            (
                "embedded_teacher_chart",
                "Writing Process Chart",
                "Display the Writing Process Chart.",
                61,
            ),
        ]:
            page = next(value for value in guide_pages if value.pdf_page_number == page_number)
            add(
                role=role, resource_type="teacher_guide",
                reference=reference, title=reference, evidence_text=evidence_text,
                resource=guide, pdf_range=(page_number, page_number),
                method="exact_text_within_indexed_lesson_boundary",
                status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                confidence=1, heading=reference,
                beginning=_excerpt(page.normalized_text, beginning=True),
                ending=_excerpt(page.normalized_text, beginning=False),
            )

        add(
            role="classroom_map", resource_type="visual_resource",
            reference="maps of North and Central America",
            title="Maps of North and Central America",
            evidence_text=(
                "Display maps of North and Central America to show the distance "
                "from Washington, D.C., to El Salvador"
            ),
            resource=None, pdf_range=None,
            method="no_registered_exact_asset_match",
            status=ProposalStatus.UNRESOLVED, confidence=0,
            notes=[
                "The registered Lesson 2 online-resource page contains immigration "
                "and deportation links but no exact map asset record."
            ],
        )

        reviewed_notes = {
            "“Burrito Man” [pages 59–69]": (
                "Human review approved registered instructional-text PDF pages "
                "36–40 as equivalent to the publisher reference pages 59–69. "
                "The registered reflowed text contains the complete titled story, "
                "but does not expose printed or story-relative page numbering."
            ),
            "“Band-Aid” [pages 71–91]": (
                "Human review approved registered instructional-text PDF pages "
                "45–54 as the complete required story range. The publisher's "
                "principal at-a-glance assignment remains pages 71–91; guided "
                "reading continues through printed page 92, whose closing text is "
                "present on registered PDF page 54. The reflowed text does not "
                "expose printed or story-relative page numbering."
            ),
            "homework reading “Güera” (pages 51–57)": (
                "Human review approved registered instructional-text PDF pages "
                "32–34 as equivalent to the Lesson 2 review reference pages 51–57. "
                "The registered reflowed text contains the complete titled story, "
                "but does not expose printed or story-relative page numbering."
            ),
            "Spanish translations beginning page 217": (
                "Human review approved registered instructional-text PDF pages "
                "123–124 as the translation material beginning on curriculum page "
                "217. Exact story subsection headings support the equivalence; "
                "printed numbering is absent from the reflowed registered text."
            ),
            "refrane translations beginning page 228": (
                "Human review approved registered instructional-text PDF page 128 "
                "as the refrane translations beginning on curriculum page 228. "
                "The exact section and story labels support the equivalence; "
                "printed numbering is absent from the reflowed registered text."
            ),
            "notes on the stories on pages 235–236": (
                "Human review approved registered instructional-text PDF pages "
                "131–132 as the story notes on curriculum pages 235–236. Exact "
                "story headings support the equivalence; printed numbering is "
                "absent from the reflowed registered text."
            ),
        }
        assignments = [
            assignment.model_copy(update={
                "verification_status": ProposalStatus.HUMAN_REVIEWED_OVERRIDE,
                "human_review_required": False,
                "reviewer_note": reviewed_notes[assignment.curriculum_reference],
            })
            if assignment.curriculum_reference in reviewed_notes
            else assignment
            for assignment in assignments
        ]

        manifest = LessonResourceMappingManifest(
            curriculum=index.curriculum.curriculum_name,
            grade=index.curriculum.grade,
            unit_number=1,
            lesson_number=2,
            lesson_title=entry.lesson_title or "Lesson 2",
            teacher_guide_resource_id=guide.id,
            teacher_guide_pdf_start_page=entry.start_pdf_page,
            teacher_guide_pdf_end_page=entry.end_pdf_page,
            teacher_guide_printed_start_page=entry.start_printed_page,
            teacher_guide_printed_end_page=entry.end_printed_page,
            assignments=assignments,
            unresolved_references=["Maps of North and Central America: exact registered asset unavailable."],
            warnings=[
                "The principal Band-Aid assignment remains pages 71–91; guided reading continues through page 92, whose endpoint is included on registered PDF page 54.",
                "No answer key is proposed for vocabulary Activity 2.1 or open-ended planning Activities 2.4 and 2.5.",
            ],
            builder_version=LESSON_TWO_BUILDER_VERSION,
        )
        validate_lesson_two_manifest(
            manifest,
            entry=entry,
            resources=resources,
            pages_by_resource={
                guide.id: guide_pages_all,
                reader.id: reader_pages,
                activity.id: activity_pages,
                online.id: online_pages,
            },
        )
        return manifest


def _line_containing(
    pages: list[ResourcePage],
    pattern: str,
    *,
    flags: int = re.IGNORECASE,
) -> tuple[ResourcePage, str] | None:
    matcher = re.compile(pattern, flags)
    for page in pages:
        lines = [
            line.strip()
            for line in page.normalized_text.splitlines()
            if line.strip()
        ]
        for width in (1, 2, 3):
            for index in range(0, len(lines) - width + 1):
                exact = " ".join(lines[index:index + width])
                if matcher.search(exact):
                    return page, exact
    return None


def _reader_story_boundaries(
    pages: list[ResourcePage],
) -> dict[str, tuple[int, int, ResourcePage, ResourcePage]]:
    contents = next(
        (
            page for page in pages
            if page.pdf_page_number == 4
            and "CONTENTS" in page.headings
        ),
        None,
    )
    valid_titles: set[str] = set()
    if contents:
        lines = [
            line.strip()
            for line in contents.normalized_text.splitlines()
            if line.strip()
        ]
        start = lines.index("The Attack")
        stop = lines.index("Acknowledgments")
        valid_titles = {
            line.casefold() for line in lines[start:stop]
        }
    story_pages = []
    for page in pages:
        first = next(
            (
                line.strip()
                for line in page.normalized_text.splitlines()
                if line.strip()
            ),
            "",
        )
        if (
            page.pdf_page_number < 121
            and first
            and first in page.headings
            and first.casefold() in valid_titles
        ):
            story_pages.append((first, page.pdf_page_number))
    output = {}
    for index, (heading, start) in enumerate(story_pages):
        stop = (
            story_pages[index + 1][1]
            if index + 1 < len(story_pages)
            else 121
        )
        selected = [
            page
            for page in pages
            if start <= page.pdf_page_number < stop
            and _flat(page.normalized_text)
        ]
        if selected:
            output[heading.casefold()] = (
                selected[0].pdf_page_number,
                selected[-1].pdf_page_number,
                selected[0],
                selected[-1],
            )
    return output


class IndexedLessonResourceMappingBuilder:
    """Build review proposals for indexed lessons from registered resources."""

    def build(
        self,
        *,
        index_path: str | Path,
        repository: CurriculumIntelligenceRepository,
        lesson_number: int = 2,
    ) -> LessonResourceMappingManifest:
        if lesson_number == 2:
            return LessonTwoResourceMappingBuilder().build(
                index_path=index_path, repository=repository
            )
        if lesson_number not in range(3, 10):
            raise ValueError(
                "Review proposals currently support indexed Lessons 2–9."
            )
        index = CKLALessonLocator().load_index(index_path)
        entry = CKLALessonLocator.get_lesson_entry(
            index, lesson_number
        )
        resources = repository.load_all_resources()
        guide = _resource_by_type(resources, "teacher_guide")
        reader = _resource_by_type(resources, "instructional_text")
        activity = _resource_by_type(resources, "activity_resource")
        online = _resource_by_type(resources, "online_resource_guide")
        guide_pages_all = repository.load_resource_pages(guide.id)
        guide_pages = [
            page
            for page in guide_pages_all
            if entry.start_pdf_page
            <= page.pdf_page_number
            <= entry.end_pdf_page
        ]
        expected_guide_pages = list(
            range(entry.start_pdf_page, entry.end_pdf_page + 1)
        )
        if [page.pdf_page_number for page in guide_pages] != expected_guide_pages:
            raise ValueError(
                f"Lesson {lesson_number} Teacher Guide boundary pages "
                "are incomplete."
            )
        reader_pages = repository.load_resource_pages(reader.id)
        activity_pages = repository.load_resource_pages(activity.id)
        online_pages = repository.load_resource_pages(online.id)
        story_boundaries = _reader_story_boundaries(reader_pages)
        assignments: list[ResourceAssignmentProposal] = []
        unresolved: list[str] = []

        def add(
            *,
            role: str,
            resource_type: str,
            curriculum_reference: str,
            title: str,
            evidence_page: ResourcePage,
            exact_evidence: str,
            resource: InstructionalResource | None,
            pdf_range: tuple[int, int] | None,
            method: str,
            status: ProposalStatus,
            confidence: float,
            printed: list[str] | None = None,
            heading: str | None = None,
            beginning: str | None = None,
            ending: str | None = None,
            notes: list[str] | None = None,
            required_status: str = "required",
        ) -> None:
            assignments.append(ResourceAssignmentProposal(
                assignment_id=stable_id(
                    "mapping-proposal", index.curriculum.unit,
                    lesson_number, role, title, curriculum_reference,
                ),
                unit_number=int(index.curriculum.unit),
                lesson_number=lesson_number,
                resource_role=role,
                resource_type=resource_type,
                curriculum_reference=curriculum_reference,
                title_or_label=title,
                referenced_printed_pages=printed or [],
                resolved_resource_id=resource.id if resource else None,
                proposed_pdf_start_page=(
                    pdf_range[0] if pdf_range else None
                ),
                proposed_pdf_end_page=(
                    pdf_range[1] if pdf_range else None
                ),
                resolution_method=method,
                confidence=confidence,
                verification_status=status,
                evidence=[_evidence(
                    evidence_page,
                    exact_evidence,
                    heading=heading,
                    beginning=beginning,
                    ending=ending,
                    notes=notes,
                )],
                ambiguity_notes=notes or [],
                human_review_required=status in {
                    ProposalStatus.PROPOSED_FOR_REVIEW,
                    ProposalStatus.UNRESOLVED,
                    ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES,
                },
                required_status=required_status,
            ))

        boundary_page = guide_pages[0]
        boundary_evidence = next(
            line.strip()
            for line in boundary_page.normalized_text.splitlines()
            if line.strip().casefold() == f"lesson {lesson_number}".casefold()
        )
        add(
            role="defines_lesson",
            resource_type="teacher_guide",
            curriculum_reference=(
                f"Lesson {lesson_number}, printed pages "
                f"{entry.start_printed_page}–{entry.end_printed_page}"
            ),
            title=f"Teacher Guide Lesson {lesson_number} range",
            evidence_page=boundary_page,
            exact_evidence=boundary_evidence,
            resource=guide,
            pdf_range=(entry.start_pdf_page, entry.end_pdf_page),
            method="saved_index_exact_boundary",
            status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
            confidence=1,
            printed=[
                f"{entry.start_printed_page}–{entry.end_printed_page}"
            ],
            heading=f"Lesson {lesson_number}",
            beginning=_excerpt(
                guide_pages[0].normalized_text, beginning=True
            ),
            ending=_excerpt(
                guide_pages[-1].normalized_text, beginning=False
            ),
        )

        titles = re.findall(r"“([^”]+)”", entry.lesson_title or "")
        if lesson_number == 9:
            titles = ["Selfie"]
        principal_ranges: list[str] = []
        reading_line = None
        for title in titles:
            match = _line_containing(
                guide_pages,
                rf"{re.escape(title)}.*\[pages?\s+[^\]]+\]",
            )
            if match:
                reading_line = reading_line or match
                for value in re.findall(r"\d+[–-]\d+", match[1]):
                    if value not in principal_ranges:
                        principal_ranges.append(value)
        if lesson_number == 9:
            reading_line = _line_containing(
                guide_pages,
                r"selections students will read are on pages",
            )
            if reading_line:
                next_line = _line_containing(
                    guide_pages,
                    r"17[–-]19 and 34[–-]35",
                )
                if next_line:
                    reading_line = (
                        reading_line[0],
                        f"{reading_line[1]} {next_line[1]}",
                    )
                principal_ranges = ["17–19", "34–35"]

        for position, title in enumerate(titles):
            boundary = story_boundaries.get(title.casefold())
            evidence = reading_line
            if not evidence:
                unresolved.append(
                    f"{title}: exact assigned-reading reference was not "
                    f"located inside Lesson {lesson_number}."
                )
                continue
            printed = (
                [principal_ranges[position]]
                if position < len(principal_ranges)
                else principal_ranges
            )
            if lesson_number == 9:
                add(
                    role="assessment_reading",
                    resource_type="instructional_text",
                    curriculum_reference=evidence[1],
                    title="Selfie assessment selections",
                    evidence_page=evidence[0],
                    exact_evidence=evidence[1],
                    resource=reader,
                    pdf_range=None,
                    method="printed_subranges_not_mappable_from_guide_only",
                    status=ProposalStatus.UNRESOLVED,
                    confidence=0,
                    printed=principal_ranges,
                    heading="SELFIE",
                    notes=[
                        "The Teacher Guide identifies printed selections "
                        "17–19 and 34–35, but provides no quoted boundary "
                        "text that mechanically maps those excerpts into "
                        "the registered reflowed story."
                    ],
                )
                unresolved.append(
                    "Selfie assessment selections pages 17–19 and 34–35 "
                    "require human coordinate identification."
                )
                break
            if not boundary:
                unresolved.append(
                    f"{title}: exact registered story heading unavailable."
                )
                continue
            add(
                role="assigned_reading",
                resource_type="instructional_text",
                curriculum_reference=evidence[1],
                title=title,
                evidence_page=evidence[0],
                exact_evidence=evidence[1],
                resource=reader,
                pdf_range=boundary[:2],
                method="exact_story_heading_to_next_story_heading",
                status=ProposalStatus.PROPOSED_FOR_REVIEW,
                confidence=.94,
                printed=printed,
                heading=title.upper(),
                beginning=_excerpt(
                    boundary[2].normalized_text, beginning=True
                ),
                ending=_excerpt(
                    boundary[3].normalized_text, beginning=False
                ),
                notes=[
                    "The exact story heading and next-story boundary are "
                    "registered, but printed-page equivalence is absent "
                    "from the reflowed instructional text."
                ],
            )

        guided_references: list[tuple[ResourcePage, str, list[str]]] = []
        seen_guided = set()
        for page in guide_pages:
            for line in page.normalized_text.splitlines():
                exact_line = line.strip()
                for match in re.finditer(
                    r"\[[^\]]*(?:pages?|page)\s+\d+[^\]]*\]",
                    exact_line,
                    re.IGNORECASE,
                ):
                    exact = match.group(0)
                    printed = re.findall(
                        r"\d+(?:[–-]\d+)?", exact
                    )
                    key = (exact, tuple(printed))
                    if (
                        printed
                        and key not in seen_guided
                        and printed != principal_ranges
                        and not (
                            len(printed) == 1
                            and printed[0] in principal_ranges
                        )
                    ):
                        seen_guided.add(key)
                        guided_references.append(
                            (page, exact, printed)
                        )
        for sequence, (
            evidence_page,
            exact_reference,
            printed,
        ) in enumerate(guided_references, start=1):
            numeric_start = int(
                re.match(r"\d+", printed[0]).group(0)
            )
            linked_title = next(
                (
                    title
                    for title, principal in zip(
                        titles, principal_ranges
                    )
                    if int(re.match(r"\d+", principal).group(0))
                    <= numeric_start
                    <= int(re.findall(r"\d+", principal)[-1])
                ),
                titles[0] if titles else "Assigned text",
            )
            boundary = story_boundaries.get(linked_title.casefold())
            add(
                role="guided_reading_range",
                resource_type="instructional_text",
                curriculum_reference=exact_reference,
                title=(
                    f"{linked_title} guided range "
                    f"{', '.join(printed)}"
                ),
                evidence_page=evidence_page,
                exact_evidence=exact_reference,
                resource=reader,
                pdf_range=None,
                method="printed_subrange_requires_reviewed_text_boundary",
                status=ProposalStatus.UNRESOLVED,
                confidence=0,
                printed=printed,
                heading=linked_title.upper(),
                beginning=(
                    _excerpt(
                        boundary[2].normalized_text, beginning=True
                    )
                    if boundary else None
                ),
                ending=(
                    _excerpt(
                        boundary[3].normalized_text, beginning=False
                    )
                    if boundary else None
                ),
                notes=[
                    "This guided-reading stop is distinct from the "
                    "principal story assignment. The registered reflowed "
                    "text has no printed labels, so its exact subrange "
                    "must be located during human review."
                ],
            )
            unresolved.append(
                f"{linked_title} guided-reading reference "
                f"{', '.join(printed)} requires reviewed subrange "
                "coordinates."
            )

        continuation_references: list[tuple[ResourcePage, str]] = []
        for page in guide_pages:
            for match in re.finditer(
                r"\[Have students read the rest of the story\.\]",
                page.normalized_text,
                re.IGNORECASE,
            ):
                continuation_references.append((page, match.group(0)))
        for sequence, (
            evidence_page,
            exact_reference,
        ) in enumerate(continuation_references, start=1):
            prior_ranges = [
                item
                for item in guided_references
                if item[0].pdf_page_number <= evidence_page.pdf_page_number
            ]
            linked_title = titles[0] if titles else "Assigned text"
            if prior_ranges:
                numeric_start = int(
                    re.match(r"\d+", prior_ranges[-1][2][0]).group(0)
                )
                linked_title = next(
                    (
                        title
                        for title, principal in zip(
                            titles, principal_ranges
                        )
                        if int(re.match(r"\d+", principal).group(0))
                        <= numeric_start
                        <= int(re.findall(r"\d+", principal)[-1])
                    ),
                    linked_title,
                )
            boundary = story_boundaries.get(linked_title.casefold())
            add(
                role="guided_reading_continuation",
                resource_type="instructional_text",
                curriculum_reference=exact_reference,
                title=f"{linked_title} guided continuation {sequence}",
                evidence_page=evidence_page,
                exact_evidence=exact_reference,
                resource=reader,
                pdf_range=None,
                method="unbounded_continuation_requires_human_review",
                status=ProposalStatus.UNRESOLVED,
                confidence=0,
                heading=linked_title.upper(),
                beginning=(
                    _excerpt(
                        boundary[2].normalized_text, beginning=True
                    )
                    if boundary else None
                ),
                ending=(
                    _excerpt(
                        boundary[3].normalized_text, beginning=False
                    )
                    if boundary else None
                ),
                notes=[
                    "The publisher explicitly assigns the remainder of "
                    "the story but gives no printed start or end "
                    "coordinate in this instruction. Human review must "
                    "connect it to the preceding guided-reading stop "
                    "without inferring a page range."
                ],
            )
            unresolved.append(
                f"{linked_title} unbounded guided-reading continuation "
                "requires reviewed subrange coordinates."
            )

        joined_guide = "\n".join(
            page.normalized_text for page in guide_pages
        )
        for label in entry.activity_book_pages:
            evidence = _line_containing(
                guide_pages,
                rf"\b(?:Activity Page|Activity Pages)[^\n]*\b"
                rf"{re.escape(label)}\b",
            )
            if not evidence:
                unresolved.append(
                    f"Activity Page {label}: exact Lesson "
                    f"{lesson_number} reference unavailable."
                )
                continue
            try:
                pdf_range = _label_range(activity_pages, label)
            except ValueError as error:
                add(
                    role="activity_resource",
                    resource_type="activity_resource",
                    curriculum_reference=evidence[1],
                    title=f"Activity Page {label}",
                    evidence_page=evidence[0],
                    exact_evidence=evidence[1],
                    resource=activity,
                    pdf_range=None,
                    method="exact_document_label_not_uniquely_resolved",
                    status=ProposalStatus.UNRESOLVED,
                    confidence=0,
                    printed=[label],
                    notes=[str(error)],
                )
                unresolved.append(str(error))
                continue
            first_page = next(
                page for page in activity_pages
                if page.pdf_page_number == pdf_range[0]
            )
            last_page = next(
                page for page in activity_pages
                if page.pdf_page_number == pdf_range[1]
            )
            prior = int(label.split(".", 1)[0]) < lesson_number
            add(
                role=(
                    "shared_review_activity"
                    if prior else "activity_resource"
                ),
                resource_type="activity_resource",
                curriculum_reference=evidence[1],
                title=f"Activity Page {label}",
                evidence_page=evidence[0],
                exact_evidence=evidence[1],
                resource=activity,
                pdf_range=pdf_range,
                method="exact_document_label_boundary",
                status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                confidence=1,
                printed=[label],
                heading=(
                    first_page.headings[0]
                    if first_page.headings else label
                ),
                beginning=_excerpt(
                    first_page.normalized_text, beginning=True
                ),
                ending=_excerpt(
                    last_page.normalized_text, beginning=False
                ),
                notes=(
                    [
                        "This earlier Activity Page is explicitly cited "
                        f"inside Lesson {lesson_number} as a review "
                        "dependency."
                    ]
                    if prior else []
                ),
            )

            answer_pattern = re.compile(
                rf"(?:ACTIVITY PAGE|TAKE-HOME|ASSESSMENT)\s+"
                rf"{re.escape(label)}\b",
                re.IGNORECASE,
            )
            answer_pages = [
                page
                for page in guide_pages_all
                if "Answer Key" in page.headings
                and answer_pattern.search(page.normalized_text)
            ]
            if answer_pages:
                answer_text = " ".join(
                    line.strip()
                    for line in answer_pages[0].normalized_text.splitlines()
                    if answer_pattern.search(line)
                ) or f"Answer Key: {label}"
                answer_notes = [
                    "Only content carrying the exact activity or "
                    "assessment label is in scope; neighboring facsimiles "
                    "on the same Teacher Guide page are excluded."
                ]
                combined = " ".join(
                    page.normalized_text for page in answer_pages
                ).casefold()
                if any(
                    marker in combined
                    for marker in (
                        "answers may vary",
                        "student responses may vary",
                        "sample answer",
                        "rubric",
                    )
                ):
                    answer_notes.append(
                        "The labeled source contains open-ended or sample "
                        "guidance and must not be treated as one exact "
                        "publisher answer."
                    )
                if re.search(
                    rf"writing prompt activity on Activity Page "
                    rf"{re.escape(label)}\b",
                    joined_guide,
                    re.IGNORECASE,
                ):
                    answer_notes.append(
                        "The lesson identifies this as an open-ended "
                        "writing prompt. Any labeled answer-key content "
                        "is guidance or a sample, not one exact answer."
                    )
                add(
                    role=(
                        "shared_review_answer_key"
                        if prior else "publisher_answer_key"
                    ),
                    resource_type="teacher_guide_answer_key",
                    curriculum_reference=(
                        f"Activity Page {label} answer-key resource"
                    ),
                    title=f"Answer Key {label}",
                    evidence_page=evidence[0],
                    exact_evidence=evidence[1],
                    resource=guide,
                    pdf_range=(
                        min(page.pdf_page_number for page in answer_pages),
                        max(page.pdf_page_number for page in answer_pages),
                    ),
                    method="exact_answer_key_heading_and_activity_label",
                    status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                    confidence=1,
                    printed=[label],
                    heading="Activity Book Answer Key",
                    beginning=_excerpt(
                        answer_pages[0].normalized_text, beginning=True
                    ),
                    ending=_excerpt(
                        answer_pages[-1].normalized_text, beginning=False
                    ),
                    notes=answer_notes,
                    required_status="optional",
                )

        notes_reference = _line_containing(
            guide_pages, r"notes on (?:the )?stor(?:y|ies) on pages?"
        )
        if notes_reference and titles:
            candidates = [
                page
                for page in reader_pages
                if 130 <= page.pdf_page_number <= 134
                and any(
                    title.casefold()
                    in {heading.casefold() for heading in page.headings}
                    for title in titles
                )
            ]
            if candidates:
                add(
                    role="story_notes",
                    resource_type="instructional_text",
                    curriculum_reference=notes_reference[1],
                    title="Story notes: " + " and ".join(titles),
                    evidence_page=notes_reference[0],
                    exact_evidence=notes_reference[1],
                    resource=reader,
                    pdf_range=(
                        min(page.pdf_page_number for page in candidates),
                        max(page.pdf_page_number for page in candidates),
                    ),
                    method="exact_section_and_story_labels",
                    status=ProposalStatus.PROPOSED_FOR_REVIEW,
                    confidence=.9,
                    printed=re.findall(
                        r"\d+(?:[–-]\d+)?", notes_reference[1]
                    ),
                    heading="NOTES ON THE STORIES",
                    beginning=_excerpt(
                        candidates[0].normalized_text, beginning=True
                    ),
                    ending=_excerpt(
                        candidates[-1].normalized_text, beginning=False
                    ),
                    notes=[
                        "Exact story labels occur in the registered notes "
                        "section, but printed-page equivalence is absent."
                    ],
                )

        translation_reference = _line_containing(
            guide_pages,
            r"translations of Spanish words and phrases.*page 217",
        )
        if translation_reference and titles:
            candidates = [
                page
                for page in reader_pages
                if 122 <= page.pdf_page_number <= 126
                and any(
                    title.casefold()
                    in {heading.casefold() for heading in page.headings}
                    for title in titles
                )
            ]
            if candidates:
                add(
                    role="translation_reference",
                    resource_type="instructional_text",
                    curriculum_reference=translation_reference[1],
                    title="Spanish translations: " + " and ".join(titles),
                    evidence_page=translation_reference[0],
                    exact_evidence=translation_reference[1],
                    resource=reader,
                    pdf_range=(
                        min(page.pdf_page_number for page in candidates),
                        max(page.pdf_page_number for page in candidates),
                    ),
                    method="exact_section_and_story_labels",
                    status=ProposalStatus.PROPOSED_FOR_REVIEW,
                    confidence=.9,
                    printed=["217"],
                    heading="TRANSLATIONS OF SPANISH WORDS AND PHRASES",
                    beginning=_excerpt(
                        candidates[0].normalized_text, beginning=True
                    ),
                    ending=_excerpt(
                        candidates[-1].normalized_text, beginning=False
                    ),
                    notes=[
                        "Exact story labels occur in the registered "
                        "translation section; printed page 217 is absent."
                    ],
                )

        refrane_reference = _line_containing(
            guide_pages,
            r"(?:Translations of the refranes.*page 228|"
            r"translation on page 230|refrane.*found on page 230)",
        )
        if refrane_reference and titles:
            candidates = [
                page
                for page in reader_pages
                if 128 <= page.pdf_page_number <= 129
                and any(
                    title.casefold()
                    in {heading.casefold() for heading in page.headings}
                    for title in titles
                )
            ]
            if candidates:
                add(
                    role="refrane_reference",
                    resource_type="instructional_text",
                    curriculum_reference=refrane_reference[1],
                    title="Refrane translation: " + " and ".join(titles),
                    evidence_page=refrane_reference[0],
                    exact_evidence=refrane_reference[1],
                    resource=reader,
                    pdf_range=(
                        min(page.pdf_page_number for page in candidates),
                        max(page.pdf_page_number for page in candidates),
                    ),
                    method="exact_section_and_story_labels",
                    status=ProposalStatus.PROPOSED_FOR_REVIEW,
                    confidence=.9,
                    printed=re.findall(
                        r"\d+(?:[–-]\d+)?", refrane_reference[1]
                    ),
                    heading="TRANSLATIONS OF THE REFRANES",
                    beginning=_excerpt(
                        candidates[0].normalized_text, beginning=True
                    ),
                    ending=_excerpt(
                        candidates[-1].normalized_text, beginning=False
                    ),
                    notes=[
                        "Exact story labels occur in the registered "
                        "refrane section; printed numbering is absent."
                    ],
                )

        online_reference = _line_containing(
            guide_pages, r"(?:CKLA )?Online Resources"
        )
        online_matches = [
            page
            for page in online_pages
            if any(
                heading.casefold() == f"lesson {lesson_number}".casefold()
                for heading in page.headings
            )
            and _flat(page.normalized_text).casefold().startswith(
                f"online resources lesson {lesson_number}".casefold()
            )
        ]
        if online_reference and len(online_matches) == 1:
            page = online_matches[0]
            add(
                role="online_teacher_resources",
                resource_type="online_resource_guide",
                curriculum_reference=online_reference[1],
                title=f"Lesson {lesson_number} Online Resources",
                evidence_page=online_reference[0],
                exact_evidence=online_reference[1],
                resource=online,
                pdf_range=(page.pdf_page_number, page.pdf_page_number),
                method="exact_lesson_number_heading",
                status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                confidence=1,
                heading=f"Lesson {lesson_number}",
                beginning=_excerpt(
                    page.normalized_text, beginning=True
                ),
                ending=_excerpt(
                    page.normalized_text, beginning=False
                ),
                required_status="optional",
            )

        map_reference = _line_containing(
            guide_pages, r"Display (?:the )?maps? of "
        )
        if map_reference:
            add(
                role="classroom_map",
                resource_type="visual_resource",
                curriculum_reference=map_reference[1],
                title="Teacher-supplied map",
                evidence_page=map_reference[0],
                exact_evidence=map_reference[1],
                resource=None,
                pdf_range=None,
                method="no_registered_exact_asset_match",
                status=ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES,
                confidence=0,
                notes=[
                    "The map is explicitly required by this lesson, but "
                    "no exact map asset is registered. Do not substitute "
                    "the online-resource index page for the map itself."
                ],
            )
            unresolved.append(
                f"Lesson {lesson_number} teacher-supplied map: exact "
                "registered asset unavailable."
            )

        chart_titles = [
            "Word Roots Anchor Chart",
            "Omission Punctuation Anchor Chart",
            "Grammar Review Chart",
            "Writing Process Chart",
        ]
        for chart_title in chart_titles:
            chart_reference = _line_containing(
                guide_pages, re.escape(chart_title)
            )
            if not chart_reference:
                continue
            target_pages = [
                page
                for page in guide_pages_all
                if (
                    chart_title in page.headings
                    or chart_title in page.normalized_text
                )
            ]
            exact_heading_pages = [
                page for page in target_pages
                if chart_title in page.headings
            ]
            selected = exact_heading_pages or [
                chart_reference[0]
            ]
            page = selected[0]
            add(
                role="teacher_chart",
                resource_type="teacher_guide",
                curriculum_reference=chart_reference[1],
                title=chart_title,
                evidence_page=chart_reference[0],
                exact_evidence=chart_reference[1],
                resource=guide,
                pdf_range=(page.pdf_page_number, page.pdf_page_number),
                method=(
                    "exact_chart_title_heading"
                    if exact_heading_pages
                    else "exact_chart_title_within_lesson"
                ),
                status=ProposalStatus.DETERMINISTICALLY_VERIFIED,
                confidence=1,
                heading=chart_title,
                beginning=_excerpt(
                    page.normalized_text, beginning=True
                ),
                ending=_excerpt(
                    page.normalized_text, beginning=False
                ),
            )

        if lesson_number == 9:
            for title, pattern, pdf_range in (
                (
                    "Unit Assessment administration",
                    r"UNIT ASSESSMENT 35 minutes",
                    (135, 135),
                ),
                (
                    "Unit Assessment analysis and scoring",
                    r"UNIT ASSESSMENT ANALYSIS",
                    (136, 139),
                ),
            ):
                evidence = _line_containing(guide_pages, pattern)
                if evidence:
                    first = next(
                        page for page in guide_pages_all
                        if page.pdf_page_number == pdf_range[0]
                    )
                    last = next(
                        page for page in guide_pages_all
                        if page.pdf_page_number == pdf_range[1]
                    )
                    add(
                        role="assessment_resource",
                        resource_type="teacher_guide",
                        curriculum_reference=evidence[1],
                        title=title,
                        evidence_page=evidence[0],
                        exact_evidence=evidence[1],
                        resource=guide,
                        pdf_range=pdf_range,
                        method="exact_assessment_heading_within_lesson",
                        status=(
                            ProposalStatus.DETERMINISTICALLY_VERIFIED
                        ),
                        confidence=1,
                        heading=evidence[1],
                        beginning=_excerpt(
                            first.normalized_text, beginning=True
                        ),
                        ending=_excerpt(
                            last.normalized_text, beginning=False
                        ),
                    )

        manifest = LessonResourceMappingManifest(
            curriculum=index.curriculum.curriculum_name,
            grade=index.curriculum.grade,
            unit_number=int(index.curriculum.unit),
            lesson_number=lesson_number,
            lesson_title=entry.lesson_title or f"Lesson {lesson_number}",
            teacher_guide_resource_id=guide.id,
            teacher_guide_pdf_start_page=entry.start_pdf_page,
            teacher_guide_pdf_end_page=entry.end_pdf_page,
            teacher_guide_printed_start_page=entry.start_printed_page,
            teacher_guide_printed_end_page=entry.end_printed_page,
            assignments=assignments,
            unresolved_references=list(dict.fromkeys(unresolved)),
            warnings=[
                "This manifest is a review proposal only. No Lesson "
                "3–9 instructional-text coordinate is human approved.",
                "Open-ended answer guidance remains distinguished from "
                "an exact publisher answer.",
            ],
            schema_version="1.1",
            builder_version="2.0",
        )
        validate_indexed_lesson_manifest(
            manifest,
            entry=entry,
            resources=resources,
            pages_by_resource={
                guide.id: guide_pages_all,
                reader.id: reader_pages,
                activity.id: activity_pages,
                online.id: online_pages,
            },
        )
        return manifest


def validate_indexed_lesson_manifest(
    manifest: LessonResourceMappingManifest,
    *,
    entry,
    resources: list[InstructionalResource],
    pages_by_resource: dict[str, list[ResourcePage]],
) -> None:
    """Validate generic proposal boundaries without approving ambiguity."""
    if manifest.lesson_number != entry.lesson_number:
        raise ValueError("Manifest lesson does not match the saved index.")
    if (
        manifest.teacher_guide_pdf_start_page != entry.start_pdf_page
        or manifest.teacher_guide_pdf_end_page != entry.end_pdf_page
    ):
        raise ValueError("Teacher Guide boundaries do not match the index.")
    resource_by_id = {resource.id: resource for resource in resources}
    assignment_ids = set()
    for assignment in manifest.assignments:
        if assignment.assignment_id in assignment_ids:
            raise ValueError("Duplicate proposal assignment identifier.")
        assignment_ids.add(assignment.assignment_id)
        if assignment.lesson_number != manifest.lesson_number:
            raise ValueError("Assignment belongs to a different lesson.")
        if any(
            not entry.start_pdf_page
            <= evidence.teacher_guide_pdf_page
            <= entry.end_pdf_page
            for evidence in assignment.evidence
        ):
            raise ValueError(
                "Assignment evidence leaks outside indexed boundaries."
            )
        if (
            manifest.lesson_number >= 3
            and assignment.verification_status
            == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
        ):
            raise ValueError(
                "Lessons 3–9 cannot contain approved mappings yet."
            )
        if (
            assignment.resource_type == "instructional_text"
            and assignment.proposed_pdf_start_page is not None
            and assignment.verification_status
            == ProposalStatus.DETERMINISTICALLY_VERIFIED
        ):
            raise ValueError(
                "Reflowed instructional-text coordinates require review."
            )
        if assignment.resolved_resource_id:
            resource = resource_by_id.get(
                assignment.resolved_resource_id
            )
            if resource is None:
                raise ValueError(
                    "Proposal references an unregistered resource."
                )
            if assignment.proposed_pdf_start_page is not None:
                available = {
                    page.pdf_page_number
                    for page in pages_by_resource[resource.id]
                }
                proposed = set(range(
                    assignment.proposed_pdf_start_page,
                    assignment.proposed_pdf_end_page + 1,
                ))
                if not proposed <= available:
                    raise ValueError(
                        "Proposed PDF range exceeds registered bounds."
                    )
        if "answer_key" in assignment.resource_role:
            label = assignment.title_or_label.rsplit(" ", 1)[-1]
            if label not in assignment.curriculum_reference:
                raise ValueError("Answer-key activity label mismatch.")


def validate_lesson_two_manifest(
    manifest: LessonResourceMappingManifest,
    *,
    entry,
    resources: list[InstructionalResource],
    pages_by_resource: dict[str, list[ResourcePage]],
) -> None:
    """Reject boundary leakage, false verification, and invalid resources."""
    if manifest.lesson_number != 2:
        raise ValueError("This review manifest must remain scoped to Lesson 2.")
    if (
        manifest.teacher_guide_pdf_start_page != entry.start_pdf_page
        or manifest.teacher_guide_pdf_end_page != entry.end_pdf_page
    ):
        raise ValueError("Teacher Guide boundaries do not match the saved index.")
    resource_by_id = {resource.id: resource for resource in resources}
    assignment_ids = set()
    for assignment in manifest.assignments:
        if assignment.assignment_id in assignment_ids:
            raise ValueError("Duplicate proposal assignment identifier.")
        assignment_ids.add(assignment.assignment_id)
        for evidence in assignment.evidence:
            if not entry.start_pdf_page <= evidence.teacher_guide_pdf_page <= entry.end_pdf_page:
                raise ValueError("Assignment evidence leaks outside Lesson 2 boundaries.")
        if assignment.resolved_resource_id:
            resource = resource_by_id.get(assignment.resolved_resource_id)
            if resource is None:
                raise ValueError("Proposal references an unregistered resource.")
            if assignment.proposed_pdf_start_page is not None:
                pages = pages_by_resource[resource.id]
                available = {page.pdf_page_number for page in pages}
                proposed = set(range(
                    assignment.proposed_pdf_start_page,
                    assignment.proposed_pdf_end_page + 1,
                ))
                if not proposed.issubset(available):
                    raise ValueError("Proposed PDF range exceeds the resource.")
        if (
            assignment.verification_status == ProposalStatus.DETERMINISTICALLY_VERIFIED
            and assignment.resolution_method
            in {"exact_story_heading_to_next_story_heading", "exact_section_and_story_labels"}
        ):
            raise ValueError("Reflowed instructional-text mappings cannot be auto-verified.")
        if (
            assignment.verification_status == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
            and assignment.resolution_method
            not in {
                "exact_story_heading_to_next_story_heading",
                "exact_section_and_story_labels",
            }
        ):
            raise ValueError("Human review is limited to approved source-coordinate mappings.")
        if "answer_key" in assignment.resource_role:
            label = assignment.title_or_label.rsplit(" ", 1)[-1]
            if label not in assignment.curriculum_reference:
                raise ValueError("Answer-key activity label mismatch.")
        if "Lesson 1 range" in assignment.title_or_label:
            raise ValueError("A Lesson 1 assignment leaked into Lesson 2.")


def validate_production_lesson_manifest(
    manifest: LessonResourceMappingManifest,
    *,
    entry,
    resources: list[InstructionalResource],
    pages_by_resource: dict[str, list[ResourcePage]],
) -> None:
    """Validate an approved Unit 1 manifest without resolving ambiguity."""
    if manifest.lesson_number == 2:
        validate_lesson_two_manifest(
            manifest,
            entry=entry,
            resources=resources,
            pages_by_resource=pages_by_resource,
        )
        return
    if manifest.lesson_number not in range(3, 10):
        raise ValueError(
            "Configured production manifests currently support Lessons 2–9."
        )
    if manifest.lesson_number != entry.lesson_number:
        raise ValueError("Manifest lesson does not match the saved index.")
    if (
        manifest.teacher_guide_pdf_start_page != entry.start_pdf_page
        or manifest.teacher_guide_pdf_end_page != entry.end_pdf_page
    ):
        raise ValueError("Teacher Guide boundaries do not match the index.")
    resource_by_id = {resource.id: resource for resource in resources}
    assignment_ids: set[str] = set()
    approved_story_titles = {
        assignment.title_or_label
        for assignment in manifest.assignments
        if (
            assignment.resource_role == "assigned_reading"
            and assignment.verification_status
            == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
        )
    }
    for assignment in manifest.assignments:
        if assignment.assignment_id in assignment_ids:
            raise ValueError("Duplicate configured assignment identifier.")
        assignment_ids.add(assignment.assignment_id)
        if assignment.lesson_number != manifest.lesson_number:
            raise ValueError("Assignment belongs to a different lesson.")
        if any(
            not entry.start_pdf_page
            <= evidence.teacher_guide_pdf_page
            <= entry.end_pdf_page
            for evidence in assignment.evidence
        ):
            raise ValueError(
                "Assignment evidence leaks outside indexed boundaries."
            )
        if (
            assignment.verification_status
            == ProposalStatus.PROPOSED_FOR_REVIEW
        ):
            raise ValueError(
                "Production configuration contains an unapproved proposal: "
                f"{assignment.title_or_label}."
            )
        if (
            assignment.verification_status
            == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
        ):
            if assignment.resolution_method not in {
                "exact_story_heading_to_next_story_heading",
                "exact_section_and_story_labels",
            }:
                raise ValueError(
                    "Human review is limited to approved Reader or "
                    "supporting-text mappings."
                )
            if assignment.proposed_pdf_start_page is None:
                raise ValueError(
                    "Approved mapping has no registered PDF range."
                )
        if assignment.resource_role in {
            "guided_reading_range",
            "guided_reading_continuation",
        }:
            parent = next(
                (
                    title for title in approved_story_titles
                    if assignment.title_or_label.startswith(
                        f"{title} guided"
                    )
                ),
                None,
            )
            if parent is None:
                raise ValueError(
                    "Guided-reading reference has no approved parent story."
                )
            if assignment.proposed_pdf_start_page is not None:
                raise ValueError(
                    "Guided-reading subranges must not invent PDF coordinates."
                )
        elif (
            assignment.verification_status == ProposalStatus.UNRESOLVED
            and not (
                manifest.lesson_number == 9
                and assignment.resource_role == "assessment_reading"
            )
        ):
            raise ValueError(
                "Required production assignment remains unresolved: "
                f"{assignment.title_or_label}."
            )
        if (
            assignment.verification_status
            == ProposalStatus.UNAVAILABLE_IN_REGISTERED_SOURCES
            and assignment.resource_role != "classroom_map"
        ):
            raise ValueError(
                "Only explicitly teacher-supplied maps may remain "
                "unavailable in this production configuration."
            )
        if assignment.resolved_resource_id:
            resource = resource_by_id.get(assignment.resolved_resource_id)
            if resource is None:
                raise ValueError(
                    "Configured assignment references an unregistered "
                    "resource."
                )
            if assignment.proposed_pdf_start_page is not None:
                available_pages = {
                    page.pdf_page_number
                    for page in pages_by_resource[resource.id]
                }
                approved_pages = set(range(
                    assignment.proposed_pdf_start_page,
                    assignment.proposed_pdf_end_page + 1,
                ))
                if not approved_pages <= available_pages:
                    raise ValueError(
                        "Approved PDF range exceeds registered bounds."
                    )
                selected_text = "\n".join(
                    page.normalized_text
                    for page in pages_by_resource[resource.id]
                    if page.pdf_page_number in approved_pages
                ).casefold()
                if (
                    assignment.verification_status
                    == ProposalStatus.HUMAN_REVIEWED_OVERRIDE
                    and assignment.resource_role == "assigned_reading"
                ):
                    headings = {
                        evidence.source_heading.casefold()
                        for evidence in assignment.evidence
                        if evidence.source_heading
                    }
                    if headings and not any(
                        heading in selected_text for heading in headings
                    ):
                        raise ValueError(
                            "Approved range does not contain the expected "
                            f"heading for {assignment.title_or_label}."
                        )
        if "answer_key" in assignment.resource_role:
            label = assignment.title_or_label.rsplit(" ", 1)[-1]
            if label not in assignment.curriculum_reference:
                raise ValueError("Answer-key activity label mismatch.")


__all__ = [
    "IndexedLessonResourceMappingBuilder",
    "LessonTwoResourceMappingBuilder",
    "validate_indexed_lesson_manifest",
    "validate_lesson_two_manifest",
    "validate_production_lesson_manifest",
]
