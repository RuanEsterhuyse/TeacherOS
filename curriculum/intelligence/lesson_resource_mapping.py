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


__all__ = [
    "LessonTwoResourceMappingBuilder", "validate_lesson_two_manifest",
]
