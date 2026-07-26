from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from curriculum.intelligence.generate_lesson_intelligence import generate_lesson_intelligence
from curriculum.intelligence.lesson_intelligence import (
    LessonIntelligenceCompiler,
    locate_activity_answer_key,
    load_cached_support,
)
from curriculum.intelligence.repository import CurriculumIntelligenceRepository
from renderer.lesson_intelligence_markdown import LessonIntelligenceMarkdownRenderer
from renderer.lesson_slide_prompt import LessonSlidePromptRenderer
from schemas.canonical_lesson_schema import CanonicalLesson
from schemas.curriculum_intelligence_schema import ResourcePage, SourceCoordinate
from schemas.instructional_relationship_graph_schema import InstructionalRelationshipGraph
from schemas.lesson_intelligence_package_schema import (
    AnswerProvenanceStatus,
    ClassifiedContent,
    ContentClassification,
)
from schemas.prepared_curriculum_source_schema import PreparedCurriculumSourceBundle
from schemas.source_grounded_instruction_schema import SourceGroundedInstructionPlan


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "output/curriculum_intelligence/ckla-grade-8-unit-1-lesson-1"
DB = ROOT / "data/curriculum/library.sqlite3"


def _cached_package():
    if not CACHE.is_dir() or not DB.is_file():
        pytest.skip("The reviewed Lesson 1 curriculum-intelligence cache is unavailable.")
    bundle = PreparedCurriculumSourceBundle.model_validate_json((CACHE / "prepared_source_bundle.json").read_text())
    canonical = CanonicalLesson.model_validate_json((CACHE / "bundle_derived_canonical_lesson.json").read_text())
    plan = SourceGroundedInstructionPlan.model_validate_json((CACHE / "source_grounded_instruction_plan.json").read_text())
    graph = InstructionalRelationshipGraph.model_validate_json((CACHE / "instructional_relationship_graph.json").read_text())
    support = load_cached_support(
        CACHE / "phase_teacher_support",
        bundle_digest=bundle.bundle_digest,
        plan_digest=plan.digest,
        graph_digest=graph.graph_digest,
    )
    package = LessonIntelligenceCompiler().compile(
        bundle=bundle, canonical=canonical, plan=plan, graph=graph,
        repository=CurriculumIntelligenceRepository(DB), cached_support=support,
    )
    return package, plan


def _page(text: str, headings: list[str]) -> ResourcePage:
    return ResourcePage(
        id="page-1", resource_id="teacher-guide", source_version="v1",
        pdf_page_number=9, display_page_number=10, printed_page_label="149",
        raw_text=text, normalized_text=text, headings=headings,
        text_blocks=[
            SourceCoordinate(x0=100, y0=100, x1=300, y1=110, text="1. What happened?"),
            SourceCoordinate(x0=100, y0=120, x1=300, y1=130, text="The verified event happened."),
        ],
        extraction_method="fixture", extraction_version="1",
        extraction_confidence=1,
    )


def test_answer_key_requires_strong_identity_and_rejects_ambiguity():
    page = _page(
        "Answer Key ACTIVITY PAGE 1.3 1. What happened? The verified event happened.",
        ["Answer Key", "ACTIVITY PAGE 1.3"],
    )
    match = locate_activity_answer_key([page], activity_label="1.3", questions=["What happened?"])
    assert match["What happened?"][0] == "The verified event happened."
    assert "exact numbered question text" in match["What happened?"][1].match_evidence
    assert locate_activity_answer_key([page], activity_label="9.9", questions=["What happened?"]) == {}
    assert locate_activity_answer_key([page], activity_label="1.3", questions=["What almost happened?"]) == {}


def test_publisher_classification_requires_page_provenance():
    with pytest.raises(ValueError, match="page provenance"):
        ClassifiedContent(text="Claim", classification=ContentClassification.PUBLISHER_SOURCE)
    support = ClassifiedContent(text="Suggestion", classification=ContentClassification.TEACHEROS_AI_SUPPORT)
    assert support.classification is ContentClassification.TEACHEROS_AI_SUPPORT


def test_real_package_is_deterministic_complete_and_source_grounded():
    first, plan = _cached_package()
    second, _ = _cached_package()
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert [p.phase_id for p in first.phases] == [p.id for p in plan.instructional_phases]
    source_questions = [q.id for p in plan.instructional_phases for q in p.questions]
    compiled_source = [q.question_id for q in first.questions if q.question_id in source_questions]
    assert compiled_source == source_questions
    assert len(compiled_source) == len(set(compiled_source))
    publisher = [
        item for item in first.lesson_at_a_glance + first.standards
        if item.classification is ContentClassification.PUBLISHER_SOURCE
    ]
    assert publisher and all(item.citations for item in publisher)
    elsewhere = [q for q in first.questions if q.answer_provenance_status is AnswerProvenanceStatus.ELSEWHERE]
    assert len(elsewhere) == 6
    assert all(q.publisher_answer and q.publisher_answer.citations[0].printed_page == "149" for q in elsewhere)
    assert all("exact numbered question text" in q.publisher_answer.citations[0].match_evidence for q in elsewhere)
    assert sum(q.answer_provenance_status is AnswerProvenanceStatus.NOT_LOCATED for q in first.questions) == 3
    assert all(q.teacheros_suggested_response is None for q in first.questions)


def test_available_student_sources_are_disclosed_without_invention():
    package, _ = _cached_package()
    assert package.reading_guides
    assert all(reading.source_available for reading in package.reading_guides)
    assert all(reading.verified_summary is None for reading in package.reading_guides)
    assert package.activities
    assert all(activity.citations for activity in package.activities)


def test_both_documents_use_the_same_package_and_include_every_question():
    package, _ = _cached_package()
    teacher = LessonIntelligenceMarkdownRenderer().render(package)
    slides = LessonSlidePromptRenderer().render(package)
    assert package.package_digest in teacher and package.package_digest in slides
    for question in package.questions:
        assert teacher.count(question.question.text) >= 1
        assert question.question_id in slides
    assert "Do not shorten, omit, merge, reorder, rewrite, or fabricate" in slides


def test_generation_writes_ignored_files_without_mutating_sources_or_invoking_slides(tmp_path, monkeypatch):
    if not CACHE.is_dir() or not DB.is_file():
        pytest.skip("The reviewed Lesson 1 curriculum-intelligence cache is unavailable.")
    tracked_inputs = [
        CACHE / "prepared_source_bundle.json",
        CACHE / "source_grounded_instruction_plan.json",
        CACHE / "instructional_relationship_graph.json",
    ]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked_inputs}
    monkeypatch.setattr(
        "renderer.google_slides_renderer.GoogleSlidesRenderer",
        lambda *args, **kwargs: pytest.fail("Google Slides renderer must not be invoked"),
    )
    teacher, slides = generate_lesson_intelligence(
        lesson=1, output_directory=tmp_path, cache_root=CACHE.parent,
        database_path=DB,
    )
    assert teacher.is_file() and slides.is_file()
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked_inputs}
    assert before == after
    assert "output/" in (ROOT / ".gitignore").read_text()
