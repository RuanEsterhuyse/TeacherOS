from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from curriculum.intelligence.generate_lesson_intelligence import (
    generate_lesson_intelligence,
    prepare_configured_lesson_cache,
)
from curriculum.intelligence.lesson_intelligence import (
    LessonIntelligenceCompiler,
)
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
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
LESSON_ONE_MAPPING = (
    ROOT
    / "curriculum/mappings/"
    "ckla_grade_8_unit_1_lesson_1_coordinate_mappings.json"
)
LESSON_TWO_MANIFEST = (
    ROOT
    / "curriculum/mappings/"
    "ckla_grade_8_unit_1_lesson_2_resource_manifest.json"
)
REFERENCE_LESSON_ONE = ROOT / "output/lesson_001"
PRIVATE_LESSON_TWO_PREREQUISITES = (
    DATABASE,
    INDEX,
    LESSON_TWO_MANIFEST,
)


def _require_paths(paths: tuple[Path, ...]) -> None:
    if not all(path.is_file() for path in paths):
        pytest.skip(
            "Registered/private curriculum fixtures are unavailable in "
            "the public clone."
        )


def _prepared(tmp_path: Path):
    _require_paths(PRIVATE_LESSON_TWO_PREREQUISITES)
    database = tmp_path / "library.sqlite3"
    shutil.copy2(DATABASE, database)
    cache_root = tmp_path / "cache"
    cache = prepare_configured_lesson_cache(
        lesson=2,
        cache_root=cache_root,
        database_path=database,
    )
    bundle = PreparedCurriculumSourceBundle.model_validate_json(
        (cache / "prepared_source_bundle.json").read_text()
    )
    canonical = CanonicalLesson.model_validate_json(
        (cache / "bundle_derived_canonical_lesson.json").read_text()
    )
    plan = SourceGroundedInstructionPlan.model_validate_json(
        (cache / "source_grounded_instruction_plan.json").read_text()
    )
    graph = InstructionalRelationshipGraph.model_validate_json(
        (cache / "instructional_relationship_graph.json").read_text()
    )
    return database, cache_root, cache, bundle, canonical, plan, graph


def test_lesson_two_reaches_each_deterministic_production_stage(tmp_path):
    _, _, cache, bundle, canonical, plan, graph = _prepared(tmp_path)
    assert bundle.readiness_state.value == "source_ready"
    assert not bundle.blockers
    assert canonical.lesson_information.lesson_number == 2
    assert canonical.lesson_information.lesson_title == (
        "Whole Group: “Burrito Man” and “Band-Aid”"
    )
    assert plan.lesson_id == bundle.lesson_id
    assert plan.instructional_phases
    assert graph.lesson_id == bundle.lesson_id
    assert graph.nodes and graph.edges
    assert (cache / "instructional_relationship_graph_audit.json").is_file()


def test_lesson_two_assignments_do_not_leak_adjacent_lessons(tmp_path):
    _, _, _, bundle, _, _, _ = _prepared(tmp_path)
    lesson_boundary = next(
        assignment
        for assignment in bundle.required_assignments
        if assignment.assignment_type == "defines_lesson"
    )
    assert lesson_boundary.title == "Teacher Guide Lesson 2 range"
    assert {
        coordinate.start
        for coordinate in lesson_boundary.verified_coordinates
        if coordinate.coordinate_system == "pdf_page_zero_based"
    } == {"47"}
    assert {
        coordinate.end
        for coordinate in lesson_boundary.verified_coordinates
        if coordinate.coordinate_system == "pdf_page_zero_based"
    } == {"62"}
    assert not any(
        "Lesson 3" in assignment.title
        for assignment in (
            bundle.required_assignments + bundle.optional_assignments
        )
    )


def test_map_warning_is_nonblocking_and_does_not_fabricate_an_asset(tmp_path):
    _, _, _, bundle, _, _, _ = _prepared(tmp_path)
    map_assignment = next(
        assignment
        for assignment in bundle.optional_assignments
        if assignment.title == "Maps of North and Central America"
    )
    assert not map_assignment.available
    assert map_assignment.resolution_status.value == "unresolved"
    assert not map_assignment.source_segments
    assert any(
        "teacher-supplied" in warning
        for warning in map_assignment.warnings
    )
    assert bundle.readiness_state.value == "source_ready"


def test_activity_answer_recovery_uses_only_structured_assignments(tmp_path):
    database, _, _, bundle, canonical, plan, graph = _prepared(tmp_path)
    package = LessonIntelligenceCompiler().compile(
        bundle=bundle,
        canonical=canonical,
        plan=plan,
        graph=graph,
        repository=CurriculumIntelligenceRepository(database),
    )
    questions_by_label = {
        label: [
            question
            for question in package.questions
            if question.question_id.startswith(f"activity-{label}-")
        ]
        for label in ("1.3", "2.1", "2.2", "2.3", "2.4", "2.5")
    }
    assert all(
        question.publisher_answer is not None
        for question in questions_by_label["1.3"]
    )
    assert any(
        question.publisher_answer is not None
        for question in questions_by_label["2.3"]
    )
    for label in ("2.1", "2.4", "2.5"):
        assert all(
            question.publisher_answer is None
            for question in questions_by_label[label]
        )
    answer_key_titles = {
        assignment.title
        for assignment in bundle.optional_assignments
        if assignment.title.startswith("Answer Key ")
    }
    assert answer_key_titles == {
        "Answer Key 1.3", "Answer Key 2.2", "Answer Key 2.3"
    }


def test_lesson_two_generation_writes_both_markdown_artifacts(tmp_path):
    database, cache_root, _, _, _, _, _ = _prepared(tmp_path)
    output = tmp_path / "lesson_002"
    teacher, slides = generate_lesson_intelligence(
        lesson=2,
        output_directory=output,
        cache_root=cache_root,
        database_path=database,
    )
    assert teacher == output / "lesson_intelligence_package.md"
    assert slides == output / "google_slides_prompt.md"
    assert teacher.is_file() and teacher.stat().st_size > 0
    assert slides.is_file() and slides.stat().st_size > 0
    assert "Lesson 2" in slides.read_text()


def test_lesson_one_reference_outputs_remain_byte_identical(tmp_path):
    expected = [
        REFERENCE_LESSON_ONE / "lesson_intelligence_package.md",
        REFERENCE_LESSON_ONE / "google_slides_prompt.md",
    ]
    _require_paths((
        DATABASE,
        INDEX,
        LESSON_ONE_MAPPING,
        *expected,
    ))
    teacher, slides = generate_lesson_intelligence(
        lesson=1,
        output_directory=tmp_path / "lesson_001",
        cache_root=ROOT / "output/curriculum_intelligence",
        database_path=DATABASE,
    )
    assert teacher.read_bytes() == expected[0].read_bytes()
    assert slides.read_bytes() == expected[1].read_bytes()
