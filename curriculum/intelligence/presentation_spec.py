"""Deterministic construction of provider-neutral presentation specifications."""

from __future__ import annotations

from collections import defaultdict

from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.presentation_spec_validator import (
    validate_presentation_spec,
)
from schemas.pasted_lesson_schema import SourceReference
from schemas.playbook_enrichment_schema import (
    ApprovedPlaybookEnrichment,
    GENERATED_GUIDANCE_LABEL,
    TeacherApprovalStatus,
)
from schemas.presentation_spec_schema import (
    ActivityCoverage,
    ApprovalStatus,
    ContentElement,
    ContentElementType,
    GroundingLabel,
    ImagePlacement,
    LayoutType,
    PRESENTATION_SPEC_GENERATOR_VERSION,
    PresentationBuildOptions,
    PresentationBuildResult,
    PresentationGenerationMetadata,
    PresentationSpec,
    PresentationWarning,
    RequiredSection,
    RequiredSectionKey,
    SlideGenerationMetadata,
    SlideSpec,
    SlideType,
    SpeakerNotes,
    ThemeSpec,
    ValidationStatus,
    VisualSpec,
    VisualType,
)


DEFAULT_THEME = ThemeSpec(
    theme_id="teacheros_classroom",
    name="TeacherOS Classroom",
    background_color="#F7F4EE",
    heading_color="#3B97A8",
    body_text_color="#2E2E2E",
    accent_colors=["#67C7D8", "#E97F7C", "#D9D9D9"],
    heading_font="Aptos Display",
    body_font="Aptos",
    title_font="Aptos Display",
    border_radius=16,
    shadow_style="soft",
    spacing_scale=[8, 12, 16, 24, 32, 48],
    footer_style="minimal source attribution",
    image_style="modern educational, mature, uncluttered",
)


def _grounding_label(value: str | None) -> GroundingLabel:
    if value and value.startswith(GENERATED_GUIDANCE_LABEL):
        return GroundingLabel.generated_guidance_review
    return GroundingLabel.source_backed


def _slide_type(title: str, has_questions: bool) -> SlideType:
    value = title.casefold().replace("&", "and")
    rules = (
        (("core connection", "background"), SlideType.background_knowledge),
        (("geograph", " map", "diversity"), SlideType.map_or_geography),
        (("identity", "concept"), SlideType.identity_or_concept),
        (("author", "text preview"), SlideType.author_or_text_preview),
        (("windows and mirrors", "windows/mirrors"), SlideType.windows_and_mirrors),
        (("vocabulary",), SlideType.vocabulary),
        (("reading purpose",), SlideType.reading_purpose),
        (("checkpoint", "stop and"), SlideType.reading_checkpoint),
        (("reading chunk", "read ", "reread"), SlideType.reading_chunk),
        (("theme",), SlideType.theme_analysis),
        (("text evidence", "evidence"), SlideType.text_evidence),
        (("activity book", "activity page"), SlideType.activity_book),
        (("writing", "write"), SlideType.writing_task),
        (("grammar",), SlideType.grammar),
        (("morphology",), SlideType.morphology),
        (("reflection", "reflect"), SlideType.reflection),
        (("exit ticket",), SlideType.exit_ticket),
    )
    for terms, slide_type in rules:
        if any(term in value for term in terms):
            return slide_type
    return SlideType.discussion if has_questions else SlideType.identity_or_concept


def _layout(slide_type: SlideType) -> LayoutType:
    if slide_type == SlideType.title:
        return LayoutType.title
    if slide_type == SlideType.agenda:
        return LayoutType.day_opener
    if slide_type in {
        SlideType.essential_question,
        SlideType.discussion,
        SlideType.reading_checkpoint,
        SlideType.exit_ticket,
    }:
        return LayoutType.question_focus
    if slide_type == SlideType.vocabulary:
        return LayoutType.cards
    if slide_type in {
        SlideType.map_or_geography,
        SlideType.author_or_text_preview,
    }:
        return LayoutType.visual_focus
    if slide_type in {
        SlideType.windows_and_mirrors,
        SlideType.theme_analysis,
    }:
        return LayoutType.comparison
    if slide_type == SlideType.text_evidence:
        return LayoutType.text_evidence
    if slide_type in {
        SlideType.activity_book,
        SlideType.writing_task,
        SlideType.grammar,
        SlideType.morphology,
        SlideType.homework,
    }:
        return LayoutType.steps
    return LayoutType.single_focus


def _visual(
    slide_type: SlideType,
    title: str,
    references: list[SourceReference],
    include_prompt: bool,
) -> VisualSpec:
    visual_type = VisualType.text_only
    description = None
    placement = ImagePlacement.none
    if slide_type == SlideType.map_or_geography:
        visual_type = VisualType.map
        description = (
            "Use an approved source map if supplied; otherwise use a neutral, "
            "editable placeholder labeled for teacher replacement."
        )
        placement = ImagePlacement.right
    elif slide_type == SlideType.author_or_text_preview:
        visual_type = VisualType.book_cover_reference
        description = (
            "Reference only an approved author or text asset; never recreate a "
            "cover or factual source document."
        )
        placement = ImagePlacement.right
    elif slide_type == SlideType.activity_book:
        visual_type = VisualType.activity_page_reference
        description = (
            "Use the approved activity-page asset when available; otherwise "
            "show a labeled editable placeholder."
        )
        placement = ImagePlacement.right
    elif slide_type in {
        SlideType.background_knowledge,
        SlideType.identity_or_concept,
        SlideType.windows_and_mirrors,
    }:
        visual_type = VisualType.diagram
        description = "Use a simple editable concept diagram that adds no factual claims."
        placement = ImagePlacement.right
    image_prompt = None
    if include_prompt and visual_type != VisualType.text_only:
        image_prompt = (
            f"Create renderer-neutral visual support for “{title}” following "
            "the approved-source and neutral-placeholder rules."
        )
    return VisualSpec(
        visual_type=visual_type,
        description=description,
        image_prompt=image_prompt,
        placement=placement,
        alt_text=(
            f"Visual support for {title}"
            if visual_type != VisualType.text_only else None
        ),
        required=False,
        source_reference=references[0] if references else None,
        licensing_note=(
            "Confirm usage rights before classroom distribution."
            if visual_type != VisualType.text_only else None
        ),
    )


class _SlideBuilder:
    def __init__(self, presentation_id: str) -> None:
        self.presentation_id = presentation_id
        self.slides: list[SlideSpec] = []

    def add(
        self,
        *,
        slide_type: SlideType,
        title: str,
        content: list[ContentElement],
        notes: SpeakerNotes,
        instructional_day: int | None = None,
        activity_id: str | None = None,
        estimated_minutes: int | None = None,
        references: list[SourceReference] | None = None,
        eld_supports: list[str] | None = None,
        visual: VisualSpec | None = None,
        sequence_group: str | None = None,
        required: bool = True,
    ) -> SlideSpec:
        number = len(self.slides) + 1
        slide_id = stable_id(
            "presentation-slide",
            self.presentation_id,
            number,
            slide_type.value,
            activity_id or "lesson",
        )
        labels = {
            element.grounding_label for element in content
        } | set(notes.grounding_labels)
        slide = SlideSpec(
            slide_id=slide_id,
            slide_number=number,
            instructional_day=instructional_day,
            activity_id=activity_id,
            slide_type=slide_type,
            layout_type=_layout(slide_type),
            title=title,
            student_facing_content=content,
            speaker_notes=notes,
            estimated_minutes=estimated_minutes,
            visual_spec=visual,
            source_references=list(references or []),
            grounding_labels=sorted(labels, key=lambda value: value.value),
            eld_supports=list(eld_supports or []),
            required=required,
            sequence_group=sequence_group,
            generation_metadata=SlideGenerationMetadata(
                source_activity_id=activity_id
            ),
        )
        self.slides.append(slide)
        return slide


def _element(
    presentation_id: str,
    slide_number: int,
    order: int,
    element_type: ContentElementType,
    *,
    text: str | None = None,
    items: list[str] | None = None,
    label: str | None = None,
    reference: SourceReference | None = None,
    grounding: GroundingLabel = GroundingLabel.source_backed,
) -> ContentElement:
    return ContentElement(
        element_id=stable_id(
            "content-element",
            presentation_id,
            slide_number,
            order,
            element_type.value,
        ),
        element_type=element_type,
        text=text,
        items=list(items or []),
        label=label,
        order=order,
        source_reference=reference,
        grounding_label=grounding,
    )


def build_presentation_spec(
    playbook: ApprovedPlaybookEnrichment,
    options: PresentationBuildOptions | None = None,
) -> PresentationBuildResult:
    """Build a complete deterministic specification from one approved playbook."""
    options = options or PresentationBuildOptions()
    if playbook.teacher_approval_status != TeacherApprovalStatus.approved:
        raise ValueError("Presentation planning requires an approved enrichment.")
    if options.preferred_theme_id != DEFAULT_THEME.theme_id:
        raise ValueError(
            f"Unknown presentation theme: {options.preferred_theme_id}"
        )
    approved_playbook = playbook.enriched_playbook
    options_digest = content_digest(options.model_dump(mode="json"))
    presentation_id = stable_id(
        "presentation-spec",
        playbook.enrichment_id,
        approved_playbook.playbook_id,
        content_digest(approved_playbook.model_dump(mode="json")),
        options_digest,
        PRESENTATION_SPEC_GENERATOR_VERSION,
    )
    builder = _SlideBuilder(presentation_id)
    sections: list[RequiredSection] = []

    title_slide = builder.add(
        slide_type=SlideType.title,
        title=approved_playbook.lesson_metadata.lesson_title,
        content=[_element(
            presentation_id, 1, 1, ContentElementType.heading,
            text=approved_playbook.lesson_metadata.lesson_title,
        )],
        notes=SpeakerNotes(
            purpose=f"{GENERATED_GUIDANCE_LABEL} Open the lesson and orient students.",
            source_references=approved_playbook.source_references,
            grounding_labels=[GroundingLabel.generated_guidance_review],
        ),
        references=approved_playbook.source_references,
        visual=_visual(
            SlideType.title,
            approved_playbook.lesson_metadata.lesson_title,
            approved_playbook.source_references,
            False,
        ),
        sequence_group="lesson_opening",
    )
    sections.append(RequiredSection(
        section_key=RequiredSectionKey.title,
        represented_by_slide_ids=[title_slide.slide_id],
    ))

    activities_by_day: dict[int, list] = defaultdict(list)
    days = approved_playbook.instructional_days or [1]
    for activity in approved_playbook.activities:
        activities_by_day[activity.instructional_day or days[0]].append(activity)

    first_day = days[0]
    for day in days:
        day_activities = activities_by_day.get(day, [])
        agenda_items = [activity.title for activity in day_activities]
        content = [_element(
            presentation_id,
            len(builder.slides) + 1,
            1,
            ContentElementType.heading,
            text=f"Day {day}",
        )]
        if options.include_agenda and agenda_items:
            content.append(_element(
                presentation_id,
                len(builder.slides) + 1,
                2,
                ContentElementType.numbered_list,
                items=agenda_items,
                label="Today’s learning",
            ))
        day_slide = builder.add(
            slide_type=SlideType.agenda,
            title=f"Day {day}",
            content=content,
            notes=SpeakerNotes(
                purpose=f"{GENERATED_GUIDANCE_LABEL} Preview the day’s sequence.",
                grounding_labels=[GroundingLabel.generated_guidance_review],
            ),
            instructional_day=day,
            sequence_group=f"day_{day}",
        )
        sections.append(RequiredSection(
            section_key=RequiredSectionKey.day_start,
            instructional_day=day,
            represented_by_slide_ids=[day_slide.slide_id],
        ))

        if day == first_day:
            if approved_playbook.essential_question:
                slide_number = len(builder.slides) + 1
                eq_slide = builder.add(
                    slide_type=SlideType.essential_question,
                    title="Essential Question",
                    content=[_element(
                        presentation_id, slide_number, 1,
                        ContentElementType.question,
                        text=approved_playbook.essential_question,
                    )],
                    notes=SpeakerNotes(
                        purpose=f"{GENERATED_GUIDANCE_LABEL} Frame the lesson’s central inquiry.",
                        grounding_labels=[
                            GroundingLabel.generated_guidance_review
                        ],
                    ),
                    instructional_day=day,
                    references=approved_playbook.source_references,
                    sequence_group=f"day_{day}",
                )
                sections.append(RequiredSection(
                    section_key=RequiredSectionKey.essential_question,
                    represented_by_slide_ids=[eq_slide.slide_id],
                ))
            if options.include_objectives and approved_playbook.objectives:
                slide_number = len(builder.slides) + 1
                objective_slide = builder.add(
                    slide_type=SlideType.learning_objectives,
                    title="Learning Objectives",
                    content=[_element(
                        presentation_id, slide_number, 1,
                        ContentElementType.bullet_list,
                        items=approved_playbook.objectives,
                    )],
                    notes=SpeakerNotes(
                        purpose=f"{GENERATED_GUIDANCE_LABEL} Make the approved objectives visible.",
                        grounding_labels=[
                            GroundingLabel.generated_guidance_review
                        ],
                    ),
                    instructional_day=day,
                    references=approved_playbook.source_references,
                    sequence_group=f"day_{day}",
                )
                sections.append(RequiredSection(
                    section_key=RequiredSectionKey.objectives,
                    represented_by_slide_ids=[objective_slide.slide_id],
                ))
            elif approved_playbook.objectives:
                represented: list[str] = []
                if options.include_teacher_only_slides:
                    teacher_slide = builder.add(
                        slide_type=SlideType.teacher_only,
                        title="Teacher Only: Learning Objectives",
                        content=[],
                        notes=SpeakerNotes(
                            purpose=f"{GENERATED_GUIDANCE_LABEL} Keep approved objectives in teacher notes.",
                            teacher_actions=approved_playbook.objectives,
                            source_references=approved_playbook.source_references,
                            grounding_labels=[
                                GroundingLabel.generated_guidance_review,
                                GroundingLabel.source_backed,
                            ],
                        ),
                        instructional_day=day,
                        references=approved_playbook.source_references,
                        sequence_group=f"day_{day}",
                    )
                    represented = [teacher_slide.slide_id]
                sections.append(RequiredSection(
                    section_key=RequiredSectionKey.objectives,
                    required=options.strict_required_section_coverage,
                    represented_by_slide_ids=represented,
                ))
            if options.include_vocabulary and approved_playbook.vocabulary:
                slide_number = len(builder.slides) + 1
                vocabulary_items = [
                    (
                        f"{entry.term}: {entry.student_friendly_definition}"
                        if entry.student_friendly_definition
                        else entry.term
                    )
                    for entry in approved_playbook.vocabulary
                ]
                vocabulary_slide = builder.add(
                    slide_type=SlideType.vocabulary,
                    title="Vocabulary",
                    content=[_element(
                        presentation_id, slide_number, 1,
                        ContentElementType.bullet_list,
                        items=vocabulary_items,
                    )],
                    notes=SpeakerNotes(
                        purpose=f"{GENERATED_GUIDANCE_LABEL} Prepare students to use the approved terms.",
                        grounding_labels=[
                            GroundingLabel.generated_guidance_review
                        ],
                    ),
                    instructional_day=day,
                    references=approved_playbook.source_references,
                    visual=_visual(
                        SlideType.vocabulary, "Vocabulary",
                        approved_playbook.source_references,
                        options.include_visual_prompts,
                    ),
                    sequence_group=f"day_{day}",
                )
                sections.append(RequiredSection(
                    section_key=RequiredSectionKey.vocabulary,
                    represented_by_slide_ids=[vocabulary_slide.slide_id],
                ))
            elif approved_playbook.vocabulary:
                represented = []
                if options.include_teacher_only_slides:
                    teacher_slide = builder.add(
                        slide_type=SlideType.teacher_only,
                        title="Teacher Only: Vocabulary",
                        content=[],
                        notes=SpeakerNotes(
                            purpose=f"{GENERATED_GUIDANCE_LABEL} Keep approved vocabulary available in notes.",
                            teacher_actions=[
                                entry.term
                                for entry in approved_playbook.vocabulary
                            ],
                            source_references=approved_playbook.source_references,
                            grounding_labels=[
                                GroundingLabel.generated_guidance_review,
                                GroundingLabel.source_backed,
                            ],
                        ),
                        instructional_day=day,
                        references=approved_playbook.source_references,
                        sequence_group=f"day_{day}",
                    )
                    represented = [teacher_slide.slide_id]
                sections.append(RequiredSection(
                    section_key=RequiredSectionKey.vocabulary,
                    required=options.strict_required_section_coverage,
                    represented_by_slide_ids=represented,
                ))

        for activity in day_activities:
            slide_type = _slide_type(
                activity.title, bool(activity.questions)
            )
            slide_number = len(builder.slides) + 1
            elements = [_element(
                presentation_id, slide_number, 1,
                ContentElementType.heading,
                text=activity.title,
                reference=(
                    activity.source_references[0]
                    if activity.source_references else None
                ),
            )]
            order = 2
            for question in activity.questions:
                elements.append(_element(
                    presentation_id, slide_number, order,
                    ContentElementType.question,
                    text=question.prompt,
                    reference=(
                        activity.source_references[0]
                        if activity.source_references else None
                    ),
                ))
                order += 1
            notes_labels = {
                _grounding_label(value)
                for value in (
                    [activity.purpose, activity.teacher_goal]
                    + activity.teacher_script
                    + activity.possible_student_responses
                    + activity.teacher_responses
                    + activity.misconceptions
                    + activity.checks_for_understanding
                    + activity.eld_supports
                    + ([activity.transition] if activity.transition else [])
                )
                if value
            }
            slide = builder.add(
                slide_type=slide_type,
                title=activity.title,
                content=elements,
                notes=SpeakerNotes(
                    purpose=activity.purpose,
                    teacher_script=activity.teacher_script,
                    teacher_actions=(
                        [activity.teacher_goal]
                        if activity.teacher_goal else []
                    ) + activity.teacher_responses,
                    anticipated_responses=activity.possible_student_responses,
                    misconception_support=activity.misconceptions,
                    checks_for_understanding=activity.checks_for_understanding,
                    transition_language=activity.transition,
                    pacing_notes=(
                        f"{activity.duration_minutes} minutes"
                        if activity.duration_minutes is not None else None
                    ),
                    source_references=activity.source_references,
                    grounding_labels=sorted(
                        notes_labels, key=lambda value: value.value
                    ),
                ),
                instructional_day=day,
                activity_id=activity.activity_id,
                estimated_minutes=activity.duration_minutes,
                references=activity.source_references,
                eld_supports=(
                    activity.eld_supports
                    if options.include_eld_supports else []
                ),
                visual=_visual(
                    slide_type,
                    activity.title,
                    activity.source_references,
                    options.include_visual_prompts,
                ),
                sequence_group=f"day_{day}",
            )
            sections.append(RequiredSection(
                section_key=RequiredSectionKey.activity,
                activity_id=activity.activity_id,
                instructional_day=day,
                represented_by_slide_ids=[slide.slide_id],
            ))

    last_day = days[-1]
    if approved_playbook.assessment:
        slide_number = len(builder.slides) + 1
        contains_exit = any(
            "exit ticket" in value.casefold()
            for value in approved_playbook.assessment
        )
        assessment_slide = None
        if not contains_exit or options.include_exit_ticket:
            assessment_type = (
                SlideType.exit_ticket
                if contains_exit else SlideType.writing_task
            )
            assessment_slide = builder.add(
                slide_type=assessment_type,
                title="Exit Ticket" if contains_exit else "Assessment",
                content=[_element(
                    presentation_id, slide_number, 1,
                    (
                        ContentElementType.exit_ticket_prompt
                        if contains_exit else ContentElementType.bullet_list
                    ),
                    text=(
                        approved_playbook.assessment[0]
                        if contains_exit
                        and len(approved_playbook.assessment) == 1
                        else None
                    ),
                    items=(
                        approved_playbook.assessment
                        if not contains_exit
                        or len(approved_playbook.assessment) > 1
                        else []
                    ),
                )],
                notes=SpeakerNotes(
                    purpose=f"{GENERATED_GUIDANCE_LABEL} Use the approved assessment requirement.",
                    grounding_labels=[
                        GroundingLabel.generated_guidance_review
                    ],
                    source_references=approved_playbook.source_references,
                ),
                instructional_day=last_day,
                references=approved_playbook.source_references,
                sequence_group=f"day_{last_day}",
            )
        elif options.include_teacher_only_slides:
            assessment_slide = builder.add(
                slide_type=SlideType.teacher_only,
                title="Teacher Only: Exit Ticket",
                content=[],
                notes=SpeakerNotes(
                    purpose=f"{GENERATED_GUIDANCE_LABEL} Keep the approved exit ticket in teacher notes.",
                    teacher_actions=approved_playbook.assessment,
                    source_references=approved_playbook.source_references,
                    grounding_labels=[
                        GroundingLabel.generated_guidance_review,
                        GroundingLabel.source_backed,
                    ],
                ),
                instructional_day=last_day,
                references=approved_playbook.source_references,
                sequence_group=f"day_{last_day}",
            )
        sections.append(RequiredSection(
            section_key=(
                RequiredSectionKey.exit_ticket
                if contains_exit else RequiredSectionKey.assessment
            ),
            required=options.strict_required_section_coverage,
            represented_by_slide_ids=(
                [assessment_slide.slide_id] if assessment_slide else []
            ),
        ))

    if options.include_homework and approved_playbook.homework:
        slide_number = len(builder.slides) + 1
        homework_slide = builder.add(
            slide_type=SlideType.homework,
            title="Homework",
            content=[_element(
                presentation_id, slide_number, 1,
                ContentElementType.bullet_list,
                items=approved_playbook.homework,
            )],
            notes=SpeakerNotes(
                purpose=f"{GENERATED_GUIDANCE_LABEL} Assign the approved homework exactly.",
                grounding_labels=[GroundingLabel.generated_guidance_review],
                source_references=approved_playbook.source_references,
            ),
            instructional_day=last_day,
            references=approved_playbook.source_references,
            sequence_group=f"day_{last_day}",
        )
        sections.append(RequiredSection(
            section_key=RequiredSectionKey.homework,
            represented_by_slide_ids=[homework_slide.slide_id],
        ))
    elif approved_playbook.homework:
        represented = []
        if options.include_teacher_only_slides:
            teacher_slide = builder.add(
                slide_type=SlideType.teacher_only,
                title="Teacher Only: Homework",
                content=[],
                notes=SpeakerNotes(
                    purpose=f"{GENERATED_GUIDANCE_LABEL} Keep approved homework in teacher notes.",
                    teacher_actions=approved_playbook.homework,
                    source_references=approved_playbook.source_references,
                    grounding_labels=[
                        GroundingLabel.generated_guidance_review,
                        GroundingLabel.source_backed,
                    ],
                ),
                instructional_day=last_day,
                references=approved_playbook.source_references,
                sequence_group=f"day_{last_day}",
            )
            represented = [teacher_slide.slide_id]
        sections.append(RequiredSection(
            section_key=RequiredSectionKey.homework,
            required=options.strict_required_section_coverage,
            represented_by_slide_ids=represented,
        ))

    expected_minutes = sum(
        activity.duration_minutes or 0
        for activity in approved_playbook.activities
    )
    spec = PresentationSpec(
        presentation_id=presentation_id,
        playbook_id=approved_playbook.playbook_id,
        approved_enrichment_id=playbook.enrichment_id,
        source_id=playbook.source_id,
        grade=approved_playbook.lesson_metadata.grade,
        unit=approved_playbook.lesson_metadata.unit,
        lesson_number=approved_playbook.lesson_metadata.lesson_number,
        lesson_title=approved_playbook.lesson_metadata.lesson_title,
        presentation_title=approved_playbook.lesson_metadata.lesson_title,
        instructional_days=days,
        estimated_total_minutes=expected_minutes,
        theme=DEFAULT_THEME,
        slides=builder.slides,
        required_sections=sections,
        source_references=approved_playbook.source_references,
        generation_metadata=PresentationGenerationMetadata(
            generated_at=playbook.generated_at,
            approved_enrichment_id=playbook.enrichment_id,
            options_digest=options_digest,
        ),
        validation_status=ValidationStatus.pending,
        approval_status=ApprovalStatus.pending,
    )
    report = validate_presentation_spec(spec, playbook)
    spec = spec.model_copy(update={"validation_status": report.status})
    warnings: list[PresentationWarning] = []
    if (
        options.target_slide_count is not None
        and len(spec.slides) != options.target_slide_count
    ):
        warnings.append(PresentationWarning(
            code="target_slide_count_not_met",
            message=(
                f"Generated {len(spec.slides)} slides instead of target "
                f"{options.target_slide_count}; required coverage was preserved."
            ),
        ))
    if (
        options.maximum_slide_count is not None
        and len(spec.slides) > options.maximum_slide_count
    ):
        warnings.append(PresentationWarning(
            code="maximum_slide_count_exceeded",
            message=(
                f"Generated {len(spec.slides)} slides, exceeding maximum "
                f"{options.maximum_slide_count}; required slides were not dropped."
            ),
        ))
    missing_sections = [
        coverage.section_key
        for coverage in report.section_coverage
        if coverage.required and not coverage.covered
    ]
    return PresentationBuildResult(
        presentation_spec=spec,
        warnings=warnings,
        missing_sections=missing_sections,
        source_coverage=report.source_coverage,
        activity_coverage=report.activity_coverage,
        validation_report=report,
    )


__all__ = ["DEFAULT_THEME", "build_presentation_spec"]
