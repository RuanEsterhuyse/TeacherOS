"""Offline one-to-one tests for the Phase 5B Google Slides path."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from curriculum.intelligence.ids import content_digest
from curriculum.intelligence.instruction_plan import (
    SourceGroundedInstructionPlanBuilder,
)
from curriculum.intelligence.lesson_phase_support import (
    resolve_phase_support,
)
from curriculum.intelligence.lesson_rendering_model import (
    build_lesson_rendering_model,
)
from curriculum.intelligence.lesson_rendering_model_validator import (
    validate_lesson_rendering_model,
)
from curriculum.intelligence.relationship_graph import (
    InstructionalRelationshipGraphBuilder,
)
from renderer.google_slides_renderer import GoogleSlidesRenderer
from renderer.lesson_rendering_model_adapter import (
    SLIDE_TYPE_LAYOUTS,
    LessonRenderingModelSlidesAdapter,
)
from renderer.lesson_rendering_model_slides import (
    ContentOverflowError,
    LessonRenderingModelGoogleSlidesRenderer,
)
from schemas.lesson_rendering_model_schema import (
    ContentOrigin,
    LessonRenderingValidationReport,
    OriginText,
    RenderingReadinessStatus,
    SlideCoverageEntry,
    SlideScope,
    SlideType,
    VisualAssetRequirement,
)
from Tests.test_grounded_instructional_intelligence import (
    intelligence_bundle,
)


class _Execute:
    def __init__(self, callback):
        self.callback = callback

    def execute(self):
        return self.callback()


class FakePresentations:
    def __init__(self, presentation_id="fake-presentation"):
        self.presentation_id = presentation_id
        self.slides = ["default-slide"]
        self.requests = []
        self.create_calls = 0
        self.get_calls = 0
        self.batch_update_calls = 0

    def create(self, body):
        def result():
            self.create_calls += 1
            return {
                "presentationId": self.presentation_id,
                "slides": [{"objectId": "default-slide"}],
            }
        return _Execute(result)

    def batchUpdate(self, presentationId, body):
        def result():
            self.batch_update_calls += 1
            for request in body["requests"]:
                self.requests.append(deepcopy(request))
                if "deleteObject" in request:
                    object_id = request["deleteObject"]["objectId"]
                    self.slides = [
                        value for value in self.slides
                        if value != object_id
                    ]
                if "createSlide" in request:
                    value = request["createSlide"]
                    self.slides.insert(
                        value["insertionIndex"], value["objectId"]
                    )
            return {"replies": []}
        return _Execute(result)

    def get(self, presentationId):
        def result():
            self.get_calls += 1
            return {"slides": [
                {
                    "objectId": object_id,
                    "slideProperties": {
                        "notesPage": {
                            "notesProperties": {
                                "speakerNotesObjectId":
                                    f"notes-{object_id}"
                            }
                        }
                    },
                }
                for object_id in self.slides
            ]}
        return _Execute(result)


class FakeSlidesService:
    def __init__(self, presentation_id="fake-presentation"):
        self.api = FakePresentations(presentation_id)

    def presentations(self):
        return self.api


class FakeDriveService:
    pass


def _with_digests(model):
    value = model.model_copy(update={
        "content_digest": content_digest(model.model_dump(
            mode="json",
            exclude={
                "content_digest", "artifact_digest",
                "warnings", "blockers",
            },
        )),
        "artifact_digest": "pending",
    })
    return value.model_copy(update={
        "artifact_digest": content_digest(
            value.model_dump(mode="json", exclude={"artifact_digest"})
        )
    })


def _report(model, source_report=None):
    report = LessonRenderingValidationReport(
        status=source_report.status if source_report else "pass_with_warnings",
        lesson_id=model.lesson_id,
        model_digest=model.artifact_digest,
        findings=source_report.findings if source_report else [],
        phase_count=len(model.phases),
        slide_count=len(model.slides),
        question_count=len(model.question_coverage),
        validation_digest="fixture-validation",
    )
    return report


@pytest.fixture
def slides_fixture(tmp_path: Path):
    bundle = intelligence_bundle(tmp_path)
    plan = SourceGroundedInstructionPlanBuilder().build(bundle)
    graph, audit = InstructionalRelationshipGraphBuilder().build(
        bundle, plan
    )
    manifest, drafts = resolve_phase_support(
        bundle, plan, graph, audit, cache_directory=None
    )
    model = build_lesson_rendering_model(
        bundle, plan, graph, audit,
        support_manifest=manifest, support_drafts=drafts,
    )
    source_report = validate_lesson_rendering_model(
        model, bundle, plan, graph, audit
    )
    # The real Lesson 1 has 36 specifications. Extend only the offline API
    # fixture with explicitly scoped structural records to exercise that count.
    value = model.model_copy(deep=True)
    needed = 36 - len(value.slides)
    for index in range(needed):
        source = value.slides[0].model_copy(deep=True)
        source.slide_id = f"fixture-lesson-structure-{index + 1}"
        source.slide_number = len(value.slides) + 1
        source.scope = SlideScope.LESSON_STRUCTURE
        source.phase_id = None
        source.student_visible_content.title = OriginText(
            text=f"Structural Fixture {index + 1}",
            origin=ContentOrigin.DETERMINISTIC_STRUCTURE,
        )
        value.slides.append(source)
        value.slide_coverage.append(SlideCoverageEntry(
            slide_id=source.slide_id,
            slide_number=source.slide_number,
            scope=SlideScope.LESSON_STRUCTURE,
            coverage_reference=f"fixture:{index + 1}",
        ))
    value = _with_digests(value)
    return {
        "model": value,
        "report": _report(value, source_report),
        "asset_registry": {
            resource.resource_id:
                f"https://assets.example.test/{resource.resource_id}.png"
            for resource in bundle.resource_summaries
        },
        "tmp_path": tmp_path,
    }


def _adapter(fixture, model=None, report=None, registry=None):
    value = model or fixture["model"]
    return LessonRenderingModelSlidesAdapter().adapt(
        value,
        report or _report(value),
        asset_registry=(
            fixture["asset_registry"] if registry is None else registry
        ),
    )


def _renderer(fixture, presentation_id="fake-presentation"):
    service = FakeSlidesService(presentation_id)
    renderer = LessonRenderingModelGoogleSlidesRenderer(
        slides_service=service,
        drive_service=FakeDriveService(),
    )
    return renderer, service


def test_valid_lesson_one_has_one_instruction_per_slide(slides_fixture) -> None:
    instructions = _adapter(slides_fixture)
    assert len(slides_fixture["model"].slides) == len(instructions) == 36
    assert [value.source_slide_id for value in instructions] == [
        value.slide_id for value in slides_fixture["model"].slides
    ]
    assert [value.slide_number for value in instructions] == list(
        range(1, 37)
    )


def test_all_slide_types_have_explicit_supported_layouts() -> None:
    assert set(SLIDE_TYPE_LAYOUTS) == set(SlideType)
    assert len(SLIDE_TYPE_LAYOUTS) == 19


@pytest.mark.parametrize("slide_type", [
    SlideType.TITLE, SlideType.DAY_DIVIDER,
    SlideType.TEXT_DEPENDENT_QUESTION, SlideType.DISCUSSION,
    SlideType.HOMEWORK,
])
def test_key_slide_type_mapping(slides_fixture, slide_type) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    model.slides[0].slide_type = slide_type
    instructions = _adapter(
        slides_fixture, _with_digests(model),
        _report(_with_digests(model)),
    )
    assert instructions[0].layout_name == SLIDE_TYPE_LAYOUTS[slide_type]


def test_unknown_slide_type_blocks(slides_fixture, monkeypatch) -> None:
    monkeypatch.delitem(
        SLIDE_TYPE_LAYOUTS,
        slides_fixture["model"].slides[0].slide_type,
    )
    with pytest.raises(ValueError, match="Unsupported slide type"):
        _adapter(slides_fixture)


def test_blocked_or_mismatched_validation_artifact_is_rejected(
    slides_fixture,
) -> None:
    model = slides_fixture["model"].model_copy(
        update={"readiness_status": RenderingReadinessStatus.BLOCKED}
    )
    with pytest.raises(ValueError, match="is blocked"):
        _adapter(slides_fixture, model, _report(model))
    report = slides_fixture["report"].model_copy(update={"status": "fail"})
    with pytest.raises(ValueError, match="validation failed"):
        _adapter(slides_fixture, report=report)
    report = slides_fixture["report"].model_copy(
        update={"model_digest": "different-model"}
    )
    with pytest.raises(ValueError, match="artifact digest"):
        _adapter(slides_fixture, report=report)


def test_teacher_note_origin_and_lossless_answer_rules(
    slides_fixture,
) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    answer_slide = next(value for value in model.slides if value.answer_ids)
    answer_slide.teacher_notes.source_answers[0].origin = (
        ContentOrigin.AI_GENERATED_TEACHER_SUPPORT
    )
    model = _with_digests(model)
    with pytest.raises(ValueError, match="answer field has wrong origin"):
        _adapter(slides_fixture, model, _report(model))

    model = slides_fixture["model"].model_copy(deep=True)
    answer_slide = next(value for value in model.slides if value.answer_ids)
    answer_slide.teacher_notes.source_answer_ids.pop()
    model = _with_digests(model)
    with pytest.raises(ValueError, match="mapped losslessly"):
        _adapter(slides_fixture, model, _report(model))


def test_visible_content_excludes_answers_and_ai_support(slides_fixture) -> None:
    instructions = _adapter(slides_fixture)
    question = next(value for value in instructions if value.answer_ids)
    visible = "\n".join([
        question.title, *question.content_lines, *question.cue_lines
    ])
    assert "PUBLISHER ANSWERS" not in visible
    assert "AI-GENERATED TEACHER SUPPORT" not in visible
    assert "PUBLISHER ANSWERS" in question.notes_text
    assert all(answer_id in question.notes_text for answer_id in question.answer_ids)


def test_ai_support_is_labeled_and_notes_only(slides_fixture) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    slide = next(value for value in model.slides if value.question_ids)
    slide.teacher_notes.facilitation_notes.append(OriginText(
        text="Optional generated coaching.",
        origin=ContentOrigin.AI_GENERATED_TEACHER_SUPPORT,
        support_item_ids=["support-1"],
    ))
    model = _with_digests(model)
    instruction = next(
        value for value in _adapter(
            slides_fixture, model, _report(model)
        )
        if value.source_slide_id == slide.slide_id
    )
    assert "Optional generated coaching." not in "\n".join(
        instruction.content_lines
    )
    assert (
        "AI-GENERATED TEACHER SUPPORT — DRAFT/UNREVIEWED"
        in instruction.notes_text
    )


def test_phase_seven_has_no_invented_answers(slides_fixture) -> None:
    phase_seven = slides_fixture["model"].phases[6].phase_id
    instructions = [
        value for value in _adapter(slides_fixture)
        if value.phase_id == phase_seven
    ]
    assert instructions
    assert all(not value.answer_ids for value in instructions)
    assert all("PUBLISHER ANSWERS" not in value.notes_text for value in instructions)


def test_all_phase_six_answers_and_questions_remain_associated(
    slides_fixture,
) -> None:
    phase_six = slides_fixture["model"].phases[5].phase_id
    instructions = [
        value for value in _adapter(slides_fixture)
        if value.phase_id == phase_six
    ]
    assert sum(len(value.question_ids) for value in instructions) == 32
    assert sum(len(value.answer_ids) for value in instructions) == 32
    assert all(
        answer_id in value.notes_text
        for value in instructions
        for answer_id in value.answer_ids
    )


@pytest.mark.parametrize("mutation,match", [
    ("duplicate_id", "Duplicate source slide ID"),
    ("number_gap", "not contiguous"),
    ("coverage", "coverage count"),
    ("unknown_phase", "Unknown phase reference"),
    ("lesson_phase", "Lesson-structure slide has phase ID"),
    ("unknown_question", "Unknown question ID"),
    ("unknown_answer", "Unknown answer ID"),
])
def test_input_integrity_blockers(
    slides_fixture, mutation, match
) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    if mutation == "duplicate_id":
        model.slides[1].slide_id = model.slides[0].slide_id
    elif mutation == "number_gap":
        model.slides[1].slide_number = 99
    elif mutation == "coverage":
        model.slide_coverage.pop()
    elif mutation == "unknown_phase":
        slide = next(
            value for value in model.slides
            if value.scope == SlideScope.PHASE
        )
        slide.phase_id = "unknown-phase"
    elif mutation == "lesson_phase":
        slide = next(
            value for value in model.slides
            if value.scope == SlideScope.LESSON_STRUCTURE
        )
        slide.phase_id = model.phases[0].phase_id
    elif mutation == "unknown_question":
        model.slides[0].question_ids = ["unknown-question"]
    else:
        model.slides[0].answer_ids = ["unknown-answer"]
    model = _with_digests(model)
    with pytest.raises(ValueError, match=match):
        _adapter(slides_fixture, model, _report(model))


def test_overflow_blocks_before_google_creation(slides_fixture) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    model.slides[0].student_visible_content.statements.append(
        OriginText(
            text=" ".join(["required"] * 5000),
            origin=ContentOrigin.DETERMINISTIC_STRUCTURE,
        )
    )
    model = _with_digests(model)
    renderer, service = _renderer(slides_fixture)
    with pytest.raises(ContentOverflowError, match="content_overflow"):
        renderer.create_from_rendering_model(
            model, _report(model),
            output_directory=slides_fixture["tmp_path"],
            asset_registry=slides_fixture["asset_registry"],
        )
    assert service.api.create_calls == 0


def test_minimum_body_font_is_enforced(slides_fixture) -> None:
    renderer, _ = _renderer(slides_fixture)
    instructions = _adapter(slides_fixture)
    renderer._preflight(instructions)
    for instruction in instructions:
        for role, text, box, preferred, minimum in renderer._text_blocks(
            instruction
        ):
            if text and role not in {"cue", "footer"}:
                expected_minimum = (
                    15 if role in {"left_column", "right_column"} else 18
                )
                assert minimum >= expected_minimum or role == "title"


def test_live_canvas_scaling_preserves_relative_geometry(
    slides_fixture,
) -> None:
    renderer, _ = _renderer(slides_fixture)
    renderer._canvas_scale = .75
    requests = renderer._strict_text_requests(
        "slide-id", "source-id", "body", "Visible text",
        {"x": 1.0, "y": 2.0, "w": 4.0, "h": 2.0},
        18,
    )
    create = requests[0]["createShape"]["elementProperties"]
    style = requests[2]["updateTextStyle"]["style"]
    assert create["transform"]["translateX"] == renderer._emu(.75)
    assert create["transform"]["translateY"] == renderer._emu(1.5)
    assert style["fontSize"]["magnitude"] == 13.5
    assert style["foregroundColor"]["opaqueColor"]["rgbColor"] == (
        renderer._rgb(renderer.theme["colors"]["text"])
    )


def test_optional_placeholder_and_required_visual_block(slides_fixture) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    slide = model.slides[0]
    slide.visual_asset_requirements = [VisualAssetRequirement(
        description="Optional approved visual",
        required=False,
    )]
    model = _with_digests(model)
    instruction = _adapter(
        slides_fixture, model, _report(model), registry={}
    )[0]
    assert instruction.visuals[0].placeholder_text == (
        "Optional visual — add approved image"
    )
    slide = model.slides[0]
    slide.visual_asset_requirements = [VisualAssetRequirement(
        resource_id="missing-required",
        description="Required approved visual",
        required=True,
    )]
    model = _with_digests(model)
    with pytest.raises(ValueError, match="required_visual_unavailable"):
        _adapter(slides_fixture, model, _report(model), registry={})


def test_online_resource_reference_is_not_an_image_blocker(
    slides_fixture,
) -> None:
    model = slides_fixture["model"].model_copy(deep=True)
    slide = model.slides[0]
    slide.visual_asset_requirements = [VisualAssetRequirement(
        resource_id="resource-unit-online-resources",
        assignment_id="assignment-lesson-online-resources",
        description="Lesson Online Resources",
        required=True,
    )]
    model = _with_digests(model)
    instruction = _adapter(
        slides_fixture, model, _report(model), registry={}
    )[0]
    assert instruction.visuals == []
    assert instruction.resource_references == [
        "Lesson Online Resources "
        "[resource=resource-unit-online-resources; "
        "assignment=assignment-lesson-online-resources]"
    ]
    assert "RESOURCE REFERENCES" in instruction.notes_text
    assert "resource-unit-online-resources" in instruction.notes_text
    assert not instruction.blockers


def test_fake_google_render_creates_exactly_36_in_order(slides_fixture) -> None:
    renderer, service = _renderer(slides_fixture)
    original = slides_fixture["model"].model_dump_json()
    manifest = renderer.create_from_rendering_model(
        slides_fixture["model"], slides_fixture["report"],
        output_directory=slides_fixture["tmp_path"],
        asset_registry=slides_fixture["asset_registry"],
    )
    creates = [
        value["createSlide"] for value in service.api.requests
        if "createSlide" in value
    ]
    notes = [
        value["insertText"] for value in service.api.requests
        if value.get("insertText", {}).get("objectId", "").startswith(
            "notes-"
        )
    ]
    assert len(creates) == len(notes) == 36
    assert service.api.batch_update_calls == 3
    assert [value["insertionIndex"] for value in creates] == list(
        range(36)
    )
    assert manifest.expected_slide_count == 36
    assert manifest.created_slide_count == 36
    assert len(manifest.ordered_slide_records) == 36
    assert [value.source_slide_id for value in manifest.ordered_slide_records] == [
        value.slide_id for value in slides_fixture["model"].slides
    ]
    assert slides_fixture["model"].model_dump_json() == original
    assert (
        slides_fixture["tmp_path"]
        / "google_slides_render_manifest.json"
    ).is_file()


def test_manifest_digests_ignore_presentation_identity(slides_fixture) -> None:
    instructions = _adapter(slides_fixture)
    records = []
    renderer_one, _ = _renderer(slides_fixture, "presentation-one")
    renderer_two, _ = _renderer(slides_fixture, "presentation-two")
    for renderer in (renderer_one, renderer_two):
        renderer.presentation_id = renderer.slides_service.api.presentation_id
    from renderer.lesson_rendering_model_slides import RenderedSlideRecord
    records = [
        RenderedSlideRecord(
            slide_number=value.slide_number,
            source_slide_id=value.source_slide_id,
            google_slide_object_id=GoogleSlidesRenderer._google_id(
                "slide", value.source_slide_id
            ),
            slide_type=value.slide_type.value,
            layout_name=value.layout_name.value,
            notes_written=True,
            visible_text_digest=value.visible_text_digest,
            notes_digest=value.notes_digest,
            question_ids=value.question_ids,
            answer_ids=value.answer_ids,
        )
        for value in instructions
    ]
    first = renderer_one._manifest(
        slides_fixture["model"], records, []
    )
    second = renderer_two._manifest(
        slides_fixture["model"], records, []
    )
    assert first.presentation_id != second.presentation_id
    assert first.content_digest == second.content_digest
    assert first.manifest_digest == second.manifest_digest


def test_no_live_google_or_provider_and_existing_paths_isolated(
    slides_fixture, monkeypatch
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Live integration must not be called")

    monkeypatch.setattr(
        "services.openai_client.OpenAIClient.__init__", forbidden
    )
    monkeypatch.setattr(
        "google_auth_oauthlib.flow.InstalledAppFlow."
        "from_client_secrets_file",
        forbidden,
    )
    _adapter(slides_fixture)
    root = Path(__file__).parents[1]
    for path in (
        root / "app" / "teacheros.py",
        root / "renderer" / "google_slides_renderer.py",
        root / "renderer" / "gamma_prompt.py",
        root / "schemas" / "canonical_lesson_schema.py",
    ):
        if path.exists():
            assert "lesson_rendering_model_slides" not in path.read_text(
                encoding="utf-8"
            )
