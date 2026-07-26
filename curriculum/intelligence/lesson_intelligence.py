"""Deterministic compilation of verified lesson data for teacher use."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Iterable

from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.repository import CurriculumIntelligenceRepository
from schemas.canonical_lesson_schema import CanonicalLesson
from schemas.curriculum_intelligence_schema import ResourcePage
from schemas.instructional_relationship_graph_schema import InstructionalRelationshipGraph
from schemas.lesson_intelligence_package_schema import (
    ActivityGuide, AnswerProvenanceStatus, ClassifiedContent,
    ContentClassification, LanguageDemand, LessonIdentity,
    LessonIntelligencePackage, ObjectiveGuide, PackageCitation, PhaseGuide,
    QuestionGuideItem, ReadingGuide, SlidePromptSpecification,
    VocabularyGuideEntry,
)
from schemas.phase_teacher_support_schema import PhaseTeacherSupportDraft
from schemas.prepared_curriculum_source_schema import PreparedCurriculumSourceBundle
from schemas.source_grounded_instruction_schema import SourceGroundedInstructionPlan


COMPILER_VERSION = "1.0"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _citation(page: ResourcePage, document: str, stable_id: str, *evidence: str) -> PackageCitation:
    printed = page.printed_page_label
    footer = re.search(
        r"Teacher Resources\s*\|\s*Unit\s+\d+\s+(\d+)\s*$",
        _clean(page.normalized_text),
    )
    if footer:
        printed = footer.group(1)
    return PackageCitation(
        resource_id=page.resource_id,
        source_document=document,
        pdf_page_number=page.pdf_page_number,
        display_page_number=page.display_page_number,
        printed_page=printed,
        stable_source_id=stable_id,
        match_evidence=list(evidence),
    )


def _publisher(text: str, citations: list[PackageCitation]) -> ClassifiedContent:
    return ClassifiedContent(text=_clean(text), classification=ContentClassification.PUBLISHER_SOURCE, citations=citations)


def _interpretation(text: str) -> ClassifiedContent:
    return ClassifiedContent(text=_clean(text), classification=ContentClassification.TEACHEROS_INTERPRETATION)


def _limitation(text: str) -> ClassifiedContent:
    return ClassifiedContent(text=_clean(text), classification=ContentClassification.SOURCE_LIMITATION)


def _page_for_text(text: str, pages: Iterable[ResourcePage]) -> ResourcePage | None:
    needle = _clean(text)
    for page in pages:
        if needle and needle in _clean(page.normalized_text):
            return page
    return None


def _column_region_text(page: ResourcePage, *, left: bool, lower: bool) -> str:
    blocks = [
        block for block in page.text_blocks
        if (block.x0 < 320) == left and (block.y0 >= 420) == lower
        and block.y0 < 700
    ]
    return _clean(" ".join(block.text for block in sorted(blocks, key=lambda item: (item.y0, item.x0))))


def locate_activity_answer_key(
    pages: list[ResourcePage],
    *,
    activity_label: str,
    questions: list[str],
) -> dict[str, tuple[str, PackageCitation]]:
    """Link only explicit, numbered answer-key entries with exact question text."""
    matches: dict[str, tuple[str, PackageCitation]] = {}
    for page in pages:
        if "Answer Key" not in page.headings or activity_label not in page.normalized_text:
            continue
        regions = [
            _column_region_text(page, left=True, lower=False),
            _column_region_text(page, left=False, lower=False),
            _column_region_text(page, left=True, lower=True),
            _column_region_text(page, left=False, lower=True),
        ]
        for number, question in enumerate(questions, 1):
            exact = _clean(question)
            for region in regions:
                marker = f"{number}. {exact}"
                start = region.find(marker)
                if start < 0:
                    continue
                remainder = region[start + len(marker):].strip()
                next_number = re.search(r"\s\d+\.\s", remainder)
                answer = remainder[:next_number.start()].strip() if next_number else remainder
                answer = re.sub(
                    r"\s*Core Knowledge Language Arts.*$", "", answer
                ).strip()
                if not answer:
                    continue
                citation = _citation(
                    page, "Teacher Guide", f"answer-key-{activity_label}-{number}",
                    "explicit Answer Key heading",
                    f"exact activity label {activity_label}",
                    "exact numbered question text",
                )
                matches[exact] = (answer, citation)
    return matches


def _activity_questions(pages: list[ResourcePage], label: str) -> list[tuple[str, PackageCitation]]:
    results: list[tuple[str, PackageCitation]] = []
    for page in pages:
        text = _clean(page.normalized_text)
        for match in re.finditer(r"(?:^|\s)(\d+)\.\s(.+?)(?=\s\d+\.\s|Core Knowledge|$)", text):
            question = re.sub(
                r"\s+\d+\s+Unit 1 \| Activity Book Grade 8 \|\s*$",
                "",
                match.group(2).strip(),
            )
            results.append((question, _citation(page, f"Activity Resource {label}", f"activity-{label}-{match.group(1)}", "exact numbered activity prompt")))
    return results


class LessonIntelligenceCompiler:
    """Compile one immutable package; renderers only format this result."""

    def compile(
        self,
        *,
        bundle: PreparedCurriculumSourceBundle,
        canonical: CanonicalLesson,
        plan: SourceGroundedInstructionPlan,
        graph: InstructionalRelationshipGraph,
        repository: CurriculumIntelligenceRepository,
        cached_support: list[PhaseTeacherSupportDraft] = (),
    ) -> LessonIntelligencePackage:
        resources = {item.resource_id: item for item in bundle.resource_summaries}
        pages = {rid: repository.load_resource_pages(rid) for rid in resources}
        teacher = next(item for item in bundle.resource_summaries if item.resource_type == "teacher_guide")
        teacher_pages = pages[teacher.resource_id]
        lesson_assignment = next(item for item in bundle.required_assignments if item.assignment_type == "defines_lesson")

        def action_content(action):
            page = _page_for_text(action.exact_text, teacher_pages)
            citations = [_citation(page, teacher.title, action.id, "exact action text")] if page else [
                PackageCitation(resource_id=p.resource_id, source_document=teacher.title, pdf_page_number=p.pdf_page_numbers[0], display_page_number=p.display_page_numbers[0], stable_source_id=action.id, match_evidence=["instruction-plan provenance"])
                for p in action.provenance if p.pdf_page_numbers and p.display_page_numbers
            ]
            return _publisher(action.exact_text, citations)

        objectives = []
        for objective in plan.objectives:
            page = _page_for_text(objective.exact_text, teacher_pages)
            cites = [_citation(page, teacher.title, objective.id, "exact objective text")] if page else []
            if not cites:
                prov = objective.provenance[0]
                cites = [PackageCitation(resource_id=prov.resource_id, source_document=teacher.title, pdf_page_number=prov.pdf_page_numbers[0], display_page_number=prov.display_page_numbers[0], stable_source_id=objective.id, match_evidence=["instruction-plan provenance"])]
            phases = [phase.id for phase in plan.instructional_phases if objective.id in phase.exact_source_text]
            objectives.append(ObjectiveGuide(
                objective_id=objective.id,
                publisher_objective=_publisher(objective.exact_text, cites),
                student_friendly_interpretation=_interpretation(f"I can {objective.exact_text[0].lower() + objective.exact_text[1:]}"),
                evidence_of_mastery=_interpretation("Students demonstrate this objective through the linked discussion, reading, or written task using accurate lesson evidence."),
                phase_ids=phases or [plan.instructional_phases[0].id],
            ))

        phase_guides = []
        for phase in plan.instructional_phases:
            phase_citations = []
            for n in sorted(set(phase.pdf_page_numbers)):
                page = next((p for p in teacher_pages if p.pdf_page_number == n), None)
                if page:
                    phase_citations.append(_citation(page, teacher.title, phase.id, "phase page range"))
            phase_guides.append(PhaseGuide(
                phase_id=phase.id, sequence=phase.sequence, title=phase.phase_title,
                duration_minutes=phase.duration_minutes,
                purpose=_interpretation(f"Carry out the publisher sequence for {phase.phase_title} without changing its order or requirements."),
                teacher_actions=[action_content(a) for a in phase.teacher_actions],
                student_actions=[action_content(a) for a in phase.student_actions],
                materials=[m.exact_text for m in plan.materials],
                source_pages=phase_citations,
                transition_in=_interpretation(f"Signal the move into {phase.phase_title} and name the immediate task."),
                watch_for=_interpretation("Check that students understand the task and use the assigned source rather than guessing."),
                check_for_understanding=_interpretation("Ask a student to restate the task and identify the evidence or product expected."),
                differentiation=[_interpretation("Chunk directions and allow brief rehearsal."), _interpretation("Invite extension through a supported evidence-based explanation.")],
                language_support=_interpretation("Display a concise sentence frame tied to the phase response."),
                transition_out=_interpretation("Confirm completion, then name the purpose of the next phase."),
            ))

        questions = []
        q_index = 0
        for phase in plan.instructional_phases:
            for question in phase.questions:
                q_index += 1
                page = _page_for_text(question.question_text, teacher_pages)
                qcite = [_citation(page, teacher.title, question.id, "exact question text")] if page else phase_guides[phase.sequence - 1].source_pages[:1]
                publisher_answer = None
                status = AnswerProvenanceStatus.NOT_LOCATED
                if question.answers:
                    answer = question.answers[0]
                    apage = _page_for_text(answer.exact_text, teacher_pages)
                    acites = [_citation(apage, teacher.title, answer.id, "exact answer text")] if apage else qcite
                    publisher_answer = _publisher(answer.exact_text, acites)
                    status = AnswerProvenanceStatus.SAME_SECTION
                questions.append(QuestionGuideItem(
                    question_id=question.id, sequence=q_index, phase_id=phase.id,
                    question=_publisher(question.question_text, qcite),
                    interaction_format=", ".join(phase.grouping) or "teacher-led",
                    publisher_answer=publisher_answer,
                    answer_provenance_status=status,
                    teacher_explanation=_interpretation("Use the publisher answer when present; otherwise press students to ground responses in the verified assigned text."),
                    support_rationale=_interpretation("The response should address every part of the question and cite relevant lesson evidence."),
                    likely_incomplete_responses=["A response that answers only one part.", "A claim without source evidence."],
                    misconception="Students may substitute a general opinion for text-based reasoning.",
                    follow_up="What in the assigned text supports your response?",
                    check_for_understanding="Listen for a complete claim and a relevant detail.",
                    sentence_frame="I think ___ because the text shows ___.",
                    differentiation_or_extension="Rephrase one clause at a time, or ask students to compare two pieces of evidence.",
                ))

        activities = []
        activity_questions: list[QuestionGuideItem] = []
        answer_pages = teacher_pages
        for assignment in bundle.required_assignments:
            if assignment.assignment_type not in {"activity", "vocabulary_reference", "homework"} or "Activity Resource" not in assignment.title:
                continue
            label = assignment.title.rsplit(" ", 1)[-1]
            resource_pages = pages[assignment.resource_id]
            selected = [p for p in resource_pages if any(str(p.pdf_page_number) in {c.start, c.end} or (c.start.isdigit() and c.end.isdigit() and int(c.start) <= p.pdf_page_number <= int(c.end)) for c in assignment.verified_coordinates if c.coordinate_system == "pdf_page_zero_based")]
            citations = [_citation(p, assignment.title, assignment.assignment_id, "verified assignment coordinate") for p in selected]
            purpose = _publisher(assignment.instructional_purpose, citations[:1])
            activities.append(ActivityGuide(
                assignment_id=assignment.assignment_id, name=assignment.title,
                purpose=purpose,
                teacher_directions=_interpretation("Use the verified activity pages and retain the printed directions exactly."),
                student_task=_interpretation("Complete the prompts on the assigned activity pages."),
                expected_product=_interpretation("A completed response for every required prompt."),
                common_difficulty="Students may overlook multi-part directions.",
                language_support="Allow oral rehearsal before complete-sentence writing.",
                completion_check="Confirm every numbered item has a response.",
                citations=citations,
            ))
            if label == "1.3":
                prompts = _activity_questions(selected, label)
                answer_matches = locate_activity_answer_key(answer_pages, activity_label=label, questions=[q for q, _ in prompts])
                for prompt, pcite in prompts:
                    q_index += 1
                    match = answer_matches.get(_clean(prompt))
                    answer = _publisher(match[0], [match[1]]) if match else None
                    activity_questions.append(QuestionGuideItem(
                        question_id=f"activity-{label}-{q_index}", sequence=q_index,
                        phase_id=plan.instructional_phases[-1].id,
                        question=_publisher(prompt, [pcite]),
                        interaction_format="independent homework",
                        publisher_answer=answer,
                        answer_provenance_status=AnswerProvenanceStatus.ELSEWHERE if answer else AnswerProvenanceStatus.NOT_LOCATED,
                        teacher_explanation=_interpretation("Review the linked answer-key guidance after students complete the assigned reading."),
                        support_rationale=_interpretation("The answer-key match requires the same activity label, question number, and exact question text."),
                        likely_incomplete_responses=["A response without a complete sentence."],
                        misconception="Students may answer without returning to the assigned story.",
                        follow_up="Which event or detail supports that answer?",
                        check_for_understanding="Verify the response addresses every clause.",
                        sentence_frame="In the story, ___; this shows ___.",
                        differentiation_or_extension="Provide the question in clauses or request a second supporting detail.",
                    ))
        questions.extend(activity_questions)

        assigned_readings = [a for a in bundle.required_assignments if a.assignment_type in {"assigned_reading", "background_reading"}]
        reading_guides = []
        for assignment in assigned_readings:
            citations = []
            for segment in assignment.source_segments:
                for prov in segment.provenance:
                    if prov.pdf_page_number is not None and prov.display_page_number is not None:
                        citations.append(PackageCitation(resource_id=prov.resource_id, source_document=assignment.title, pdf_page_number=prov.pdf_page_number, display_page_number=prov.display_page_number, printed_page=prov.printed_page_label, stable_source_id=segment.segment_id, match_evidence=["verified assigned source segment"]))
            ref = ", ".join(r.value for r in assignment.original_curriculum_references)
            reading_guides.append(ReadingGuide(
                assignment_id=assignment.assignment_id, title=assignment.title,
                page_reference=ref,
                purpose=_publisher(assignment.instructional_purpose, citations[:1]),
                important_ideas=[],
                comprehension_difficulties=["Track references to identity, family, and how others perceive characters."],
                pause_points=["Use only the publisher-specified stopping points in the lesson question sequence."],
                think_alouds=[_interpretation("Model how to connect a claim to an exact event without inventing a quotation.")],
                text_evidence_to_notice=[],
                vocabulary_in_context=[], eld_scaffolds=["Preview key names and response frames."],
                source_available=assignment.available,
                limitations=[] if assignment.available else [_limitation("The assigned text is unavailable; summary, quotation, and evidence cannot be verified.")],
                citations=citations,
            ))

        support_items = [item for draft in cached_support for item in draft.support_sections]
        support_by_phase = {p.id: [] for p in plan.instructional_phases}
        for item in support_items:
            content = ClassifiedContent(text=item.content, classification=ContentClassification.TEACHEROS_AI_SUPPORT)
            for phase_id in item.linked_phase_ids:
                if phase_id in support_by_phase:
                    support_by_phase[phase_id].append(content)

        standards = []
        for standard in canonical.standards:
            text = getattr(standard, "code", None) or str(standard)
            # Canonical data is derived from verified curriculum, but citations
            # are recovered from objective source pages for teacher traceability.
            standards.append(_publisher(text, objectives[0].publisher_objective.citations))

        slides = self._slides(plan, questions, phase_guides)
        all_citations = {}
        for item in objectives:
            for cite in item.publisher_objective.citations:
                all_citations[(cite.resource_id, cite.pdf_page_number, cite.stable_source_id)] = cite
        for phase in phase_guides:
            for cite in phase.source_pages:
                all_citations[(cite.resource_id, cite.pdf_page_number, cite.stable_source_id)] = cite
        for question in questions:
            for cite in question.question.citations + (question.publisher_answer.citations if question.publisher_answer else []):
                all_citations[(cite.resource_id, cite.pdf_page_number, cite.stable_source_id)] = cite

        identity = LessonIdentity(
            curriculum_program=bundle.curriculum_id, grade="8", unit=bundle.unit_id,
            lesson_number=bundle.curriculum_lesson.sequence,
            lesson_title=plan.lesson_title,
            estimated_duration_minutes=plan.total_duration_minutes or 0,
            source_document_identity=teacher.source_identity,
            source_page_range=", ".join(r.value for r in lesson_assignment.original_curriculum_references),
        )
        payload = dict(
            identity=identity, generated_at="deterministic-cache-build",
            bundle_digest=bundle.bundle_digest,
            canonical_source_digest=canonical.source_digest,
            instruction_plan_digest=plan.digest,
            relationship_graph_digest=graph.graph_digest,
            package_digest="pending",
            lesson_at_a_glance=[
                _publisher(f"This lesson follows {len(plan.instructional_phases)} publisher phases in order.", phase_guides[0].source_pages[:1]),
                _interpretation("Students examine identity through listening, reading, discussion, and complete-sentence written responses."),
            ],
            objectives=objectives, standards=standards,
            language_demands=[LanguageDemand(phase_id=p.id, language_function="explain and support", language_domain="listening, speaking, reading, and writing", language_forms=["complete sentences", "because clauses", "evidence-based explanations"], likely_eld_difficulty="Sustaining an evidence-based explanation while processing unfamiliar names and concepts.", supports=["oral rehearsal", "displayed sentence frame", "partner processing"]) for p in plan.instructional_phases],
            before_you_teach=[
                *[action_content(a) for a in plan.teacher_preparation],
                _interpretation("Preview the verified Student Reader and Activity Resource pages listed below before class."),
            ],
            vocabulary=[],
            phases=phase_guides, reading_guides=reading_guides, questions=questions,
            activities=activities,
            discussion_facilitation=[
                _interpretation("Open by restating the discussion purpose and requiring evidence."),
                _interpretation("Use think-pair-share so all students rehearse before whole-group discussion."),
            ],
            differentiation_and_eld={
                p.id: support_by_phase[p.id] or [
                    _interpretation("Entering: offer a choice of sentence frames and allow pointing to evidence."),
                    _interpretation("Developing: require a complete claim-and-because response."),
                    _interpretation("Expanding: ask for comparison or a second piece of evidence."),
                ] for p in plan.instructional_phases
            },
            checks_for_understanding=[p.check_for_understanding for p in phase_guides],
            assessment_and_evidence=[_interpretation("Use discussion responses, reading answers, and completed Activity Resource work as evidence tied to the publisher objectives.")],
            homework_and_closing=[action_content(a) for p in plan.instructional_phases[-2:] for a in p.teacher_actions],
            teacher_preparation_checklist={
                "before class": ["Read the complete Teacher Guide lesson range.", "Preview assigned text pages."],
                "materials": [m.exact_text for m in plan.materials],
                "text or pages to preview": [f"{r.title}: {', '.join(x.value for x in r.original_curriculum_references)}" for r in bundle.required_assignments],
                "answers to review": ["Review linked answer-key entries and distinguish them from TeacherOS support."],
                "ELD supports to prepare": ["Post sentence frames for claim, evidence, and explanation."],
                "during-class reminders": ["Preserve phase order and required questions."],
                "after-class follow-up": ["Check Activity Resource completion and plan follow-up for incomplete evidence."],
            },
            provenance_index=list(all_citations.values()),
            slide_specifications=slides,
            source_limitations=[_limitation("No publisher answer was located for questions explicitly marked publisher_answer_not_located.")],
            cached_support_used=bool(support_items),
        )
        package = LessonIntelligencePackage.model_validate(payload)
        digest_basis = package.model_dump(mode="json", exclude={"package_digest"})
        return package.model_copy(
            update={"package_digest": content_digest(digest_basis)}
        )

    @staticmethod
    def _slides(plan, questions, phases):
        slides = [
            SlidePromptSpecification(slide_number=1, title=plan.lesson_title, student_facing_content=["Lesson 1"], teacher_notes=["Introduce the lesson without adding curriculum facts."], purpose="Opening", question_ids=[], answer_guidance=[], visual_recommendation="Neutral editable title treatment; do not fabricate a book cover.", interaction_format="whole group", provenance_references=[plan.lesson_id]),
            SlidePromptSpecification(slide_number=2, title="Learning Objectives", student_facing_content=[o.exact_text for o in plan.objectives], teacher_notes=["Review the objectives."], purpose="Orient students", question_ids=[], answer_guidance=[], visual_recommendation="Simple objective icons.", interaction_format="whole group", provenance_references=[o.id for o in plan.objectives]),
        ]
        grouped = {p.id: [] for p in plan.instructional_phases}
        for q in questions:
            grouped.setdefault(q.phase_id, []).append(q)
        for phase in phases:
            phase_questions = grouped.get(phase.phase_id, [])
            chunks = [phase_questions[i:i + 6] for i in range(0, len(phase_questions), 6)] or [[]]
            for index, chunk in enumerate(chunks, 1):
                answers = []
                for q in chunk:
                    if q.publisher_answer:
                        answers.append(f"{q.question_id}: {q.publisher_answer.text}")
                    else:
                        answers.append(f"{q.question_id}: Publisher answer not located.")
                slides.append(SlidePromptSpecification(
                    slide_number=len(slides) + 1,
                    title=phase.title if len(chunks) == 1 else f"{phase.title} ({index}/{len(chunks)})",
                    student_facing_content=[q.question.text for q in chunk] or [a.text for a in phase.student_actions] or ["Follow your teacher’s directions."],
                    teacher_notes=[a.text for a in phase.teacher_actions],
                    purpose=phase.purpose.text,
                    question_ids=[q.question_id for q in chunk],
                    answer_guidance=answers,
                    visual_recommendation="Use a neutral, editable instructional visual; never fabricate a source document, map, quotation, or cover.",
                    interaction_format=chunk[0].interaction_format if chunk else "whole group",
                    provenance_references=[c.stable_source_id for c in phase.source_pages],
                ))
        return slides


def load_cached_support(cache_root: Path, *, bundle_digest: str, plan_digest: str, graph_digest: str) -> list[PhaseTeacherSupportDraft]:
    """Reuse valid cached content identities; never make a provider call."""
    drafts = []
    for path in cache_root.glob("*/phase_teacher_support_draft.json"):
        validation = path.with_name("phase_teacher_support_validation.json")
        try:
            draft = PhaseTeacherSupportDraft.model_validate_json(path.read_text())
            report = json.loads(validation.read_text())
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            report.get("status") in {"pass", "pass_with_warnings"}
            and draft.prepared_bundle_digest == bundle_digest
            and draft.instruction_plan_digest == plan_digest
            and draft.relationship_graph_digest == graph_digest
        ):
            drafts.append(draft)
    # Identical support content may have historical cache identities. Consume it once.
    unique = {draft.content_digest: draft for draft in drafts}
    return [unique[key] for key in sorted(unique)]


__all__ = ["LessonIntelligenceCompiler", "locate_activity_answer_key", "load_cached_support"]
