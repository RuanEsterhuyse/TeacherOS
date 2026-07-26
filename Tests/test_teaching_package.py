from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from curriculum.intelligence.generate_lesson_intelligence import (
    build_lesson_intelligence,
    generate_lesson_intelligence,
)
from curriculum.intelligence.generate_teaching_package import (
    generate_teaching_package,
    write_teaching_package_artifacts,
)
from curriculum.intelligence.teaching_package import (
    TeachingPackageBuilder,
    TeachingPackageValidator,
    load_cached_teaching_package,
)
from curriculum.intelligence.publishing import write_publishing_metadata
from renderer.google_docs_publisher import GoogleDocsPublisher
from renderer.teaching_package_markdown import (
    StudentSlidesMarkdownRenderer,
    TeacherCompanionMarkdownRenderer,
    deterministic_json,
)
from renderer.teaching_package_slides import (
    TeachingPackageGoogleSlidesPublisher,
    package_to_google_lesson,
)
from schemas.teaching_package_schema import (
    ContentOrigin,
    GroundedText,
    StructuredTeachingPackage,
    TEACHING_PACKAGE_SCHEMA_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "output/curriculum_intelligence"
LESSON_CACHE = CACHE_ROOT / "ckla-grade-8-unit-1-lesson-1"
DB = ROOT / "data/curriculum/library.sqlite3"


def _source_package():
    if not LESSON_CACHE.is_dir() or not DB.is_file():
        pytest.skip("Reviewed Lesson 1 source cache is unavailable.")
    bundle, intelligence, _ = build_lesson_intelligence(
        lesson=1,
        cache_root=CACHE_ROOT,
        database_path=DB,
    )
    return bundle, intelligence, TeachingPackageBuilder().build(
        bundle=bundle, intelligence=intelligence
    )


def test_grounded_source_content_requires_provenance():
    with pytest.raises(ValidationError, match="requires provenance"):
        GroundedText(
            id="official",
            text="Official content",
            origin=ContentOrigin.EXACT_PUBLISHER,
            transformation_type="exact",
            confidence=1,
            review_status="verified",
        )


def test_schema_rejects_invalid_version_and_duplicate_stable_ids():
    _, _, package = _source_package()
    with pytest.raises(ValidationError, match="schema version"):
        StructuredTeachingPackage.model_validate(
            package.model_dump(mode="json")
            | {"schema_version": "999"}
        )
    duplicate = package.model_dump(mode="json")
    duplicate["student_slides"][1]["slide_id"] = (
        duplicate["student_slides"][0]["slide_id"]
    )
    with pytest.raises(ValidationError, match="Stable IDs"):
        StructuredTeachingPackage.model_validate(duplicate)


def test_builder_preserves_agenda_objectives_questions_and_timing():
    _, intelligence, package = _source_package()
    assert [value.official_title.text for value in package.agenda] == [
        value.title for value in intelligence.phases
    ]
    assert [value.duration_minutes for value in package.agenda] == [
        value.duration_minutes for value in intelligence.phases
    ]
    assert [value.official.text for value in package.objectives] == [
        value.publisher_objective.text
        for value in intelligence.objectives
    ]
    assert [value.question_id for value in package.questions] == [
        value.question_id for value in intelligence.questions
    ]
    assert all(value.teaching_step_ids for value in package.agenda)
    assert all(value.slide_ids for value in package.agenda)
    assert all(value.slide_ids for value in package.questions)


def test_agenda_omission_timing_change_and_unsupported_page_are_blocked():
    _, intelligence, package = _source_package()
    agenda = [
        package.agenda[0].model_copy(update={"duration_minutes": 999}),
        *package.agenda[2:],
    ]
    slide = package.student_slides[0].model_copy(
        update={"page_reference": "unsupported pages 999–1000"}
    )
    changed = package.model_copy(update={
        "agenda": agenda,
        "student_slides": [slide, *package.student_slides[1:]],
    })
    report = TeachingPackageValidator().validate(changed, intelligence)
    codes = {value.code for value in report.findings}
    assert "agenda_order_or_coverage_changed" in codes
    assert "agenda_timing_changed" in codes
    assert "unsupported_reader_page_reference" in codes
    assert report.status == "fail"


def test_objective_unsafe_simplification_is_blocked():
    _, intelligence, package = _source_package()
    objective = package.objectives[1]
    unsafe = objective.student_friendly.model_copy(update={
        "text": "I can identify something.",
        "cognitive_demands": ["identify"],
        "required_conditions": [],
    })
    changed = package.model_copy(update={
        "objectives": [
            objective.model_copy(update={"student_friendly": unsafe}),
            *package.objectives[2:],
        ]
    })
    report = TeachingPackageValidator().validate(changed, intelligence)
    assert report.status == "fail"
    assert "objective_meaning_changed" in {
        value.code for value in report.findings
    }


def test_required_question_and_student_visible_answer_fail_validation():
    _, intelligence, package = _source_package()
    question = next(
        value for value in package.questions
        if value.expected_answer.origin is not ContentOrigin.UNAVAILABLE
    )
    questions = [
        value.model_copy(update={"slide_ids": []})
        if value.question_id == question.question_id else value
        for value in package.questions
    ]
    slide = package.student_slides[0].model_copy(update={
        "visible_student_content": [question.expected_answer.text]
    })
    changed = package.model_copy(update={
        "questions": questions,
        "student_slides": [slide, *package.student_slides[1:]],
    })
    report = TeachingPackageValidator().validate(changed, intelligence)
    codes = {value.code for value in report.findings}
    assert "question_slide_missing" in codes
    assert "student_visible_answer" in codes


def test_local_renderers_are_deterministic_complete_and_keep_answers_in_notes():
    _, _, package = _source_package()
    teacher = TeacherCompanionMarkdownRenderer().render(package)
    slides = StudentSlidesMarkdownRenderer().render(package)
    assert teacher == TeacherCompanionMarkdownRenderer().render(package)
    assert slides == StudentSlidesMarkdownRenderer().render(package)
    for heading in (
        "Lesson Dashboard",
        "Lesson at a Glance",
        "Objectives",
        "Step-by-Step Teaching Walkthrough",
        "Discussion Guide",
        "Teacher Reflection",
    ):
        assert heading in teacher
    visible = "\n".join(
        text
        for slide in package.student_slides
        for text in slide.visible_student_content
    )
    for question in package.questions:
        if question.expected_answer.origin is not ContentOrigin.UNAVAILABLE:
            assert question.expected_answer.text not in visible
    assert len(package.student_slides) == len({
        value.slide_id for value in package.student_slides
    })


def test_artifacts_resume_and_changed_identity_invalidates_cache(tmp_path):
    bundle, intelligence, package = _source_package()
    paths = write_teaching_package_artifacts(package, tmp_path)
    before = {
        key: hashlib.sha256(value.read_bytes()).hexdigest()
        for key, value in paths.items()
    }
    cached = load_cached_teaching_package(
        paths["package"],
        bundle_digest=bundle.bundle_digest,
        intelligence_digest=intelligence.package_digest,
    )
    assert cached == package
    assert load_cached_teaching_package(
        paths["package"],
        bundle_digest="changed",
        intelligence_digest=intelligence.package_digest,
    ) is None
    write_teaching_package_artifacts(cached, tmp_path)
    assert before == {
        key: hashlib.sha256(value.read_bytes()).hexdigest()
        for key, value in paths.items()
    }
    paths["package"].write_text("{corrupt", encoding="utf-8")
    assert load_cached_teaching_package(
        paths["package"],
        bundle_digest=bundle.bundle_digest,
        intelligence_digest=intelligence.package_digest,
    ) is None


def test_generate_package_does_not_change_existing_lesson_intelligence(tmp_path):
    if not LESSON_CACHE.is_dir() or not DB.is_file():
        pytest.skip("Reviewed Lesson 1 source cache is unavailable.")
    direct = tmp_path / "direct"
    generate_lesson_intelligence(
        lesson=1,
        output_directory=direct,
        cache_root=CACHE_ROOT,
        database_path=DB,
    )
    before = {
        path.name: path.read_bytes() for path in direct.iterdir()
    }
    package, paths, resumed = generate_teaching_package(
        lesson=1,
        output_directory=tmp_path / "teaching",
        cache_root=CACHE_ROOT,
        database_path=DB,
    )
    assert package.validation.status != "fail"
    assert not resumed
    assert set(paths) == {
        "package", "validation_json", "validation_markdown",
        "teacher_json", "teacher_markdown", "slides_json",
        "slides_markdown",
    }
    assert before == {
        path.name: path.read_bytes() for path in direct.iterdir()
    }


def test_google_slides_adapter_is_one_to_one_and_publisher_is_injected():
    _, _, package = _source_package()
    lesson = package_to_google_lesson(package)
    assert len(lesson.slides) == len(package.student_slides)
    assert [value.slide_id for value in lesson.slides] == [
        value.slide_id for value in package.student_slides
    ]
    assert all(
        "Expected answer (teacher only)" in value.speaker_notes
        for value in lesson.slides
        if any(
            question_id in value.speaker_notes
            for question_id in [q.question_id for q in package.questions]
        )
    )

    class FakeRenderer:
        received = None

        def create_presentation(self, value):
            self.received = value
            return {
                "presentationId": "safe-id",
                "url": "https://docs.google.com/presentation/d/safe-id/edit",
                "slideIds": [slide.slide_id for slide in value.slides],
            }

    fake = FakeRenderer()
    result = TeachingPackageGoogleSlidesPublisher(
        renderer=fake
    ).publish(package)
    assert fake.received == lesson
    assert len(result["slideIds"]) == len(package.student_slides)


def test_google_docs_requests_are_structured_and_no_network_is_used():
    _, _, package = _source_package()
    publisher = GoogleDocsPublisher(
        docs_service=object(), drive_service=object()
    )
    requests = publisher.build_requests(package)
    assert requests[0]["insertText"]["location"]["index"] == 1
    assert GoogleDocsPublisher.AGENDA_MARKER in (
        requests[0]["insertText"]["text"]
    )
    styles = [
        value["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"]
        for value in requests[1:]
    ]
    assert "TITLE" in styles
    assert "HEADING_1" in styles


def test_google_docs_publish_uses_injected_service_and_builds_agenda_table():
    _, _, package = _source_package()

    class Operation:
        def __init__(self, result):
            self.result = result

        def execute(self):
            return self.result

    class Documents:
        def __init__(self):
            self.updates = []

        def create(self, body):
            return Operation({"documentId": "doc-id"})

        def batchUpdate(self, documentId, body):
            self.updates.append((documentId, body))
            return Operation({})

        def get(self, documentId):
            cells = [
                {
                    "content": [{
                        "startIndex": 1_000_000 + index * 2
                    }]
                }
                for index in range((len(package.agenda) + 1) * 5)
            ]
            return Operation({
                "body": {
                    "content": [{
                        "startIndex": 999_999,
                        "table": {
                            "tableRows": [
                                {"tableCells": cells[index:index + 5]}
                                for index in range(0, len(cells), 5)
                            ]
                        },
                    }]
                }
            })

    class Service:
        def __init__(self):
            self.resource = Documents()

        def documents(self):
            return self.resource

    service = Service()
    result = GoogleDocsPublisher(
        docs_service=service, drive_service=object()
    ).publish(package)

    assert result["documentId"] == "doc-id"
    assert len(service.resource.updates) == 3
    table_request = service.resource.updates[1][1]["requests"][1]
    assert table_request["insertTable"]["rows"] == len(package.agenda) + 1
    assert table_request["insertTable"]["columns"] == 5


def test_lesson_one_acceptance_has_grounding_and_honest_limitations():
    bundle, intelligence, package = _source_package()
    assert package.schema_version == TEACHING_PACKAGE_SCHEMA_VERSION
    assert package.source_bundle_digest == bundle.bundle_digest
    assert package.lesson_intelligence_digest == intelligence.package_digest
    assert package.validation.status == "pass_with_warnings"
    assert all(
        value.source_references
        for value in package.objectives
        for value in [value.official]
    )
    unavailable = [
        value for value in package.questions
        if value.expected_answer.origin is ContentOrigin.UNAVAILABLE
    ]
    assert unavailable
    assert all("not located" in value.expected_answer.text for value in unavailable)
    assert "theme_analysis_unavailable" in {
        value.code for value in package.validation.findings
    }
    assert "literary_analysis_unavailable" in {
        value.code for value in package.validation.findings
    }


def test_json_output_has_stable_order_and_no_credentials():
    _, _, package = _source_package()
    payload = deterministic_json(package)
    parsed = json.loads(payload)
    assert parsed["package_digest"] == package.package_digest
    assert "access_token" not in payload
    assert "refresh_token" not in payload
    assert "client_secret" not in payload


def test_publishing_metadata_is_safe_and_merges_publishers(tmp_path):
    path = write_publishing_metadata(
        tmp_path,
        google_doc={
            "documentId": "doc-id",
            "url": "https://docs.google.com/document/d/doc-id/edit",
            "access_token": "must-not-be-saved",
        },
    )
    write_publishing_metadata(
        tmp_path,
        google_slides={
            "presentationId": "slides-id",
            "url": (
                "https://docs.google.com/presentation/d/slides-id/edit"
            ),
            "refresh_token": "must-not-be-saved",
        },
    )
    payload = path.read_text(encoding="utf-8")
    assert "doc-id" in payload and "slides-id" in payload
    assert "access_token" not in payload
    assert "refresh_token" not in payload
