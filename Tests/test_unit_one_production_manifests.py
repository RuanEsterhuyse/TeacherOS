from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from curriculum.intelligence.generate_lesson_intelligence import (
    generate_lesson_intelligence,
    prepare_configured_lesson_cache,
)
from curriculum.intelligence.generate_unit import generate_unit
from curriculum.intelligence.lesson_intelligence import (
    LessonIntelligenceCompiler,
)
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
from curriculum.intelligence.service import CurriculumIntelligenceService
from schemas.canonical_lesson_schema import CanonicalLesson
from schemas.instructional_relationship_graph_schema import (
    InstructionalRelationshipGraph,
)
from schemas.prepared_curriculum_source_schema import (
    PreparedCurriculumSourceBundle,
)
from schemas.source_grounded_instruction_schema import (
    SourceGroundedInstructionPlan,
)


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/curriculum/library.sqlite3"
INDEX = ROOT / "data/indexes/ckla_grade_8_unit_1_index.json"
MAPPINGS = ROOT / "curriculum/mappings"
APPROVED_RANGES = {
    3: {
        "Firstborn": (57, 65),
        "Cubano Two": (66, 70),
        "Story notes: Firstborn and Cubano Two": (132, 132),
        "Spanish translations: Firstborn and Cubano Two": (124, 124),
        "Refrane translation: Firstborn and Cubano Two": (128, 128),
    },
    4: {
        "Peacemaker": (73, 82),
        "Story notes: Peacemaker": (132, 132),
    },
    5: {
        "The Secret": (85, 92),
        "Story notes: The Secret": (133, 133),
    },
    6: {
        "Pickup Soccer": (93, 98),
        "Story notes: Pickup Soccer": (133, 133),
        "Refrane translation: Pickup Soccer": (129, 129),
    },
    7: {
        "Saturday School": (101, 106),
        "Story notes: Saturday School": (134, 134),
    },
    8: {
        "90,000 Children": (109, 118),
        "Story notes: 90,000 Children": (134, 134),
        "Refrane translation: 90,000 Children": (129, 129),
    },
}
ANSWER_KEYS = {
    3: {"2.2", "3.2", "3.3"},
    4: {"3.3", "4.2", "4.3"},
    5: {"4.3", "5.2", "5.3"},
    6: {"5.3", "6.2", "6.3"},
    7: {"6.2", "7.2"},
    8: {"7.2", "8.2", "8.3"},
    9: {"9.1"},
}
PRIVATE_PRODUCTION_PREREQUISITES = (
    DATABASE,
    INDEX,
    *(
        MAPPINGS
        / f"ckla_grade_8_unit_1_lesson_{lesson}_resource_manifest.json"
        for lesson in range(3, 10)
    ),
)


def _require_private_production_sources() -> None:
    if not all(path.is_file() for path in PRIVATE_PRODUCTION_PREREQUISITES):
        pytest.skip(
            "Registered/private Unit 1 curriculum fixtures are unavailable "
            "in the public clone."
        )


@pytest.fixture(scope="module")
def production_workspace(tmp_path_factory):
    _require_private_production_sources()
    root = tmp_path_factory.mktemp("unit-one-production")
    database = root / "library.sqlite3"
    shutil.copy2(DATABASE, database)
    cache_root = root / "cache"
    bundles = {}
    for lesson in range(3, 9):
        cache = prepare_configured_lesson_cache(
            lesson=lesson,
            cache_root=cache_root,
            database_path=database,
        )
        bundles[lesson] = PreparedCurriculumSourceBundle.model_validate_json(
            (cache / "prepared_source_bundle.json").read_text()
        )
    return root, database, cache_root, bundles


@pytest.mark.parametrize("lesson", range(3, 10))
def test_approved_manifest_loads_without_pending_proposals(lesson):
    manifest = json.loads((
        MAPPINGS
        / f"ckla_grade_8_unit_1_lesson_{lesson}_resource_manifest.json"
    ).read_text())
    assert not any(
        value["verification_status"] == "proposed_for_review"
        for value in manifest["assignments"]
    )
    assert manifest["warnings"][0] == (
        f"This Lesson {lesson} manifest is an approved production "
        "configuration."
    )


@pytest.mark.parametrize("lesson", range(3, 9))
def test_exact_human_approved_reader_and_support_ranges(lesson):
    manifest = json.loads((
        MAPPINGS
        / f"ckla_grade_8_unit_1_lesson_{lesson}_resource_manifest.json"
    ).read_text())
    approved = {
        value["title_or_label"]: (
            value["proposed_pdf_start_page"],
            value["proposed_pdf_end_page"],
        )
        for value in manifest["assignments"]
        if value["verification_status"] == "human_reviewed_override"
    }
    assert approved == APPROVED_RANGES[lesson]
    assert all(
        value["reviewer_note"] and not value["human_review_required"]
        for value in manifest["assignments"]
        if value["verification_status"] == "human_reviewed_override"
    )


@pytest.mark.parametrize("lesson", range(3, 9))
def test_generic_preparation_is_source_ready_without_cross_lesson_leakage(
    production_workspace,
    lesson,
):
    _, _, _, bundles = production_workspace
    bundle = bundles[lesson]
    assert bundle.readiness_state.value == "source_ready"
    assert not bundle.blockers
    assert bundle.curriculum_lesson.sequence == lesson
    assert all(
        f"Lesson {other} range" not in assignment.title
        for other in range(1, 10)
        if other != lesson
        for assignment in (
            bundle.required_assignments + bundle.optional_assignments
        )
    )


@pytest.mark.parametrize("lesson", range(3, 9))
def test_guided_references_are_tied_to_parent_story_without_pdf_subranges(
    production_workspace,
    lesson,
):
    _, _, _, bundles = production_workspace
    bundle = bundles[lesson]
    assignments = bundle.required_assignments + bundle.optional_assignments
    assert not any(
        assignment.title.endswith("guided range")
        or "guided continuation" in assignment.title
        for assignment in assignments
    )
    manifest = json.loads((
        MAPPINGS
        / f"ckla_grade_8_unit_1_lesson_{lesson}_resource_manifest.json"
    ).read_text())
    for guided in (
        value for value in manifest["assignments"]
        if value["resource_role"].startswith("guided_reading_")
    ):
        parent = next(
            assignment for assignment in bundle.required_assignments
            if (
                assignment.assignment_type == "assigned_reading"
                and guided["title_or_label"].startswith(
                    f"{assignment.title} guided"
                )
            )
        )
        assert any(
            reference.value == guided["curriculum_reference"]
            for reference in parent.original_curriculum_references
        )


@pytest.mark.parametrize("lesson", (3, 4, 5, 7, 8))
def test_teacher_supplied_maps_are_nonblocking_warnings(
    production_workspace,
    lesson,
):
    _, _, _, bundles = production_workspace
    bundle = bundles[lesson]
    mapping = next(
        assignment for assignment in bundle.optional_assignments
        if assignment.assignment_type == "visual_resource"
    )
    assert not mapping.available
    assert mapping.required_status == "optional"
    assert any(
        "teacher-supplied map is unavailable" in warning
        for warning in mapping.warnings
    )
    assert bundle.readiness_state.value == "source_ready"


@pytest.mark.parametrize("lesson", range(3, 9))
def test_answer_keys_remain_owned_by_exact_activity_labels(
    production_workspace,
    lesson,
):
    _, _, _, bundles = production_workspace
    bundle = bundles[lesson]
    labels = {
        assignment.title.rsplit(" ", 1)[-1]
        for assignment in bundle.optional_assignments
        if assignment.title.startswith("Answer Key ")
    }
    assert labels == ANSWER_KEYS[lesson]


def test_lesson_nine_stops_on_unmapped_selfie_assessment(tmp_path):
    _require_private_production_sources()
    database = tmp_path / "library.sqlite3"
    shutil.copy2(DATABASE, database)
    service = CurriculumIntelligenceService(
        database_path=database,
        output_directory=tmp_path / "lesson-9",
    )
    built = service.build_configured_lesson(
        lesson_number=9,
        index_path=INDEX,
        mapping_manifest_path=(
            MAPPINGS
            / "ckla_grade_8_unit_1_lesson_9_resource_manifest.json"
        ),
    )
    bundle = service.prepare_lesson_source_bundle(
        built.lesson.id,
        output_path=tmp_path / "lesson-9/prepared_source_bundle.json",
    ).bundle
    assert bundle.readiness_state.value == "partially_ready"
    assert [finding.code for finding in bundle.blockers] == [
        "required_assignment_unavailable"
    ]
    assert "Selfie assessment selections" in bundle.blockers[0].message
    with pytest.raises(ValueError, match="Selfie assessment selections"):
        prepare_configured_lesson_cache(
            lesson=9,
            cache_root=tmp_path / "cache",
            database_path=database,
        )


def test_compiler_does_not_create_answers_without_exact_owned_key(
    production_workspace,
):
    root, database, cache_root, _ = production_workspace
    cache = cache_root / "ckla-grade-8-unit-1-lesson-7"
    bundle = PreparedCurriculumSourceBundle.model_validate_json(
        (cache / "prepared_source_bundle.json").read_text()
    )
    package = LessonIntelligenceCompiler().compile(
        bundle=bundle,
        canonical=CanonicalLesson.model_validate_json(
            (cache / "bundle_derived_canonical_lesson.json").read_text()
        ),
        plan=SourceGroundedInstructionPlan.model_validate_json(
            (cache / "source_grounded_instruction_plan.json").read_text()
        ),
        graph=InstructionalRelationshipGraph.model_validate_json(
            (cache / "instructional_relationship_graph.json").read_text()
        ),
        repository=CurriculumIntelligenceRepository(database),
    )
    answered_activity_labels = {
        question.question_id.split("-", 2)[1]
        for question in package.questions
        if (
            question.question_id.startswith("activity-")
            and question.publisher_answer is not None
        )
    }
    assert answered_activity_labels <= ANSWER_KEYS[7]
    output = root / "lesson_007"
    generate_lesson_intelligence(
        lesson=7,
        output_directory=output,
        cache_root=cache_root,
        database_path=database,
    )
    assert (output / "lesson_intelligence_package.md").is_file()
    assert (output / "google_slides_prompt.md").is_file()


@pytest.mark.parametrize("lesson", (6, 7))
def test_compound_ckla_question_labels_are_preserved(
    production_workspace,
    lesson,
):
    _, _, cache_root, _ = production_workspace
    plan = SourceGroundedInstructionPlan.model_validate_json((
        cache_root
        / f"ckla-grade-8-unit-1-lesson-{lesson}/"
        "source_grounded_instruction_plan.json"
    ).read_text())
    questions = [
        question
        for phase in plan.instructional_phases
        for question in phase.questions
    ]
    assert questions
    assert any(question.answers for question in questions)


def test_real_unit_orchestration_isolates_lesson_nine_failure(
    production_workspace,
    monkeypatch,
):
    root, database, cache_root, _ = production_workspace
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    lesson_one_cache = (
        ROOT / "output/curriculum_intelligence/"
        "ckla-grade-8-unit-1-lesson-1"
    )
    if not lesson_one_cache.is_dir():
        pytest.skip("Cached Lesson 1 regression fixture is unavailable.")
    target = cache_root / "ckla-grade-8-unit-1-lesson-1"
    target.mkdir(parents=True, exist_ok=True)
    for name in (
        "prepared_source_bundle.json",
        "bundle_derived_canonical_lesson.json",
        "source_grounded_instruction_plan.json",
        "instructional_relationship_graph.json",
    ):
        shutil.copy2(lesson_one_cache / name, target / name)
    summary = generate_unit(
        unit=1,
        output_directory=root / "unit_01",
        index_directory=ROOT / "data/indexes",
        cache_root=cache_root,
        database_path=database,
    )
    assert summary["lessons_attempted"] == 9
    assert summary["lessons_successfully_generated"] == 8
    assert summary["lessons_failed"] == 1
    failure = summary["results"][8]["failure"]
    assert failure["exception_type"] == "ValueError"
    assert "Selfie assessment selections" in failure["message"]
    assert all(
        (root / f"unit_01/lesson_{lesson:03d}/"
         "lesson_intelligence_package.md").is_file()
        for lesson in range(1, 9)
    )
