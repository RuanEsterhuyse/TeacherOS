"""Tests for the non-blocking TeacherOS interface bridge."""

import json
import os
import time
from types import SimpleNamespace

import pytest

from app.interface_server import GenerationJob, TeacherOSInterface
from app import interface_server
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
)
from curriculum.intelligence.playbook_enrichment_provider import (
    PlaybookEnrichmentProviderResponse,
)
from Tests.test_teacheros import prepared_fixture


def test_interface_catalog_uses_registered_curriculum_and_saved_index(tmp_path) -> None:
    teacheros, _ = prepared_fixture(tmp_path)
    interface = TeacherOSInterface(teacheros)
    catalog = interface.catalog()
    curriculum = catalog["curricula"][0]
    unit = curriculum["units"][0]
    lesson = unit["lessons"][0]

    assert curriculum["name"] == "CKLA"
    assert unit["lesson_count"] == 2
    assert lesson["title"] == 'Close Reading: "First Story"'
    assert lesson["duration"] == 45
    assert lesson["objectives"] == []


def test_generation_starts_in_background_and_returns_progress(tmp_path, monkeypatch) -> None:
    teacheros, _ = prepared_fixture(tmp_path)
    interface = TeacherOSInterface(teacheros)
    result = SimpleNamespace(
        status="completed",
        errors=[],
        model_dump=lambda mode: {
            "status": "completed",
            "completed_stages": ["prepare_lesson"],
            "validation_result": "pass",
            "slide_count": 4,
            "warnings": [],
        },
    )
    monkeypatch.setattr(teacheros, "generate_lesson", lambda **kwargs: result)

    job = interface.start_generation("CKLA", "8", "1", 1)
    for _ in range(100):
        status = interface.job_status(job.job_id)
        if status["state"] == "complete":
            break
        time.sleep(0.01)
    assert status["state"] == "complete"
    assert status["progress"] == 100
    assert status["slide_count"] == 4


def test_gamma_prompt_can_be_read_for_clipboard_and_download(
    tmp_path, monkeypatch
) -> None:
    prompt = "# Gamma Deck Prompt\n\nExact lesson content."
    path = (
        tmp_path
        / "output"
        / "generation_runs"
        / "ckla-grade-8-unit-1-lesson-2"
        / "GammaDeckPrompt.md"
    )
    path.parent.mkdir(parents=True)
    path.write_text(prompt, encoding="utf-8")
    monkeypatch.setattr(interface_server, "PROJECT_ROOT", tmp_path)

    interface = TeacherOSInterface.__new__(TeacherOSInterface)
    assert interface.read_gamma_prompt(
        "ckla-grade-8-unit-1-lesson-2"
    ) == prompt

    copied = {}
    monkeypatch.setattr(
        interface_server.subprocess,
        "run",
        lambda command, **kwargs: copied.update(command=command, **kwargs),
    )
    interface.copy_gamma_prompt("ckla-grade-8-unit-1-lesson-2")
    assert copied == {
        "command": ["pbcopy"],
        "input": prompt,
        "text": True,
        "check": True,
    }


def test_stale_artifacts_do_not_advance_current_job_progress(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(interface_server, "PROJECT_ROOT", tmp_path)
    run_dir = (
        tmp_path
        / "output"
        / "generation_runs"
        / "ckla-grade-8-unit-1-lesson-1"
    )
    run_dir.mkdir(parents=True)
    for _, filename, _ in interface_server.GENERATION_STAGES:
        if filename:
            (run_dir / filename).write_text("stale", encoding="utf-8")
    started_at_ns = time.time_ns()
    for path in run_dir.iterdir():
        os.utime(
            path,
            ns=(started_at_ns - 1_000_000, started_at_ns - 1_000_000),
        )

    interface = TeacherOSInterface.__new__(TeacherOSInterface)
    interface.jobs = {}
    interface._lock = interface_server.threading.Lock()
    job = GenerationJob(
        job_id="job-1",
        request_id="ckla-grade-8-unit-1-lesson-1",
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        lesson_number=1,
        started_at_ns=started_at_ns,
    )
    interface.jobs[job.job_id] = job

    status = interface.job_status(job.job_id)

    assert status["progress"] == 10
    assert [stage["complete"] for stage in status["stages"]] == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]


def test_validation_failure_returns_current_blocking_findings_only(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(interface_server, "PROJECT_ROOT", tmp_path)
    run_dir = (
        tmp_path
        / "output"
        / "generation_runs"
        / "ckla-grade-8-unit-1-lesson-1"
    )
    run_dir.mkdir(parents=True)
    started_at_ns = time.time_ns()
    report = {
        "status": "fail",
        "findings": [
            {
                "code": "missing_homework",
                "severity": "error",
                "message": "Required homework was not preserved.",
                "slide_id": None,
            },
            {
                "code": "student_word_count",
                "severity": "warning",
                "message": "Review slide density.",
                "slide_id": "S01",
            },
        ],
        "timing_total_minutes": 10,
        "slide_count": 1,
    }
    report_path = run_dir / "06_validation_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    interface = TeacherOSInterface.__new__(TeacherOSInterface)
    interface.jobs = {}
    interface._lock = interface_server.threading.Lock()
    job = GenerationJob(
        job_id="job-2",
        request_id="ckla-grade-8-unit-1-lesson-1",
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        lesson_number=1,
        started_at_ns=started_at_ns,
        state="failed",
        result={
            "completed_stages": [
                "prepare_lesson",
                "curriculum_reader",
                "curriculum_analyzer",
                "instruction_designer",
                "presentation_designer",
                "lesson_assembler",
                "lesson_validator",
            ],
            "failed_stage": "lesson_validator",
            "validation_result": "fail",
            "slide_count": 1,
            "warnings": [],
        },
        errors=["Lesson validation failed"],
    )
    interface.jobs[job.job_id] = job

    status = interface.job_status(job.job_id)

    assert status["failed_stage"] == "lesson_validator"
    assert status["progress"] == 70
    assert status["blocking_findings"] == [report["findings"][0]]
    assert status["stages"][6]["complete"] is True
    assert status["stages"][7]["complete"] is False


def test_teaching_package_job_status_and_artifact_access(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(interface_server, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "output" / "lesson_001"
    output.mkdir(parents=True)
    (output / "teacher_companion.md").write_text(
        "# Teacher Companion", encoding="utf-8"
    )
    interface = TeacherOSInterface.__new__(TeacherOSInterface)
    interface.jobs = {}
    interface._lock = interface_server.threading.Lock()
    job = GenerationJob(
        job_id="teaching-1",
        request_id="ckla-grade-8-unit-1-lesson-1",
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        lesson_number=1,
        state="complete",
        result={
            "validation_result": "pass_with_warnings",
            "agenda": [{"order": 1, "official": "Opening"}],
            "objectives": [],
            "teaching_steps": 1,
            "questions": 2,
            "student_slides": 3,
            "warnings": ["Review optional analysis."],
        },
        job_kind="teaching_package",
    )
    interface.jobs[job.job_id] = job

    status = interface.job_status(job.job_id)

    assert status["kind"] == "teaching_package"
    assert status["progress"] == 100
    assert status["student_slides"] == 3
    assert interface.read_teaching_artifact(
        1, "teacher_companion.md"
    ) == "# Teacher Companion"
    with pytest.raises(ValueError, match="unsupported"):
        interface.read_teaching_artifact(1, "../token.json")


def test_pasted_lesson_interface_save_analyze_review_and_save(tmp_path):
    teacheros, _ = prepared_fixture(tmp_path)
    interface = TeacherOSInterface(
        teacheros,
        pasted_repository=PastedLessonRepository(
            tmp_path / "output" / "pasted_lesson_intake"
        ),
    )
    payload = {
        "grade": "8",
        "unit": "1",
        "lesson_number": 1,
        "lesson_title": "Synthetic Review Lesson",
        "teacher_guide_page_start": 2,
        "teacher_guide_page_end": 4,
        "teacher_guide_text": (
            "Objectives:\n- Analyze a character.\n"
            "Day 1\nActivity: Evidence Talk — 10 minutes\n"
            "Question: What evidence supports the claim?\n"
            "Student Reader pp. 2–3\n"
            "Unclassified note."
        ),
        "student_reader_text": "Short synthetic reader text.",
        "activity_book_text": None,
    }

    source = interface.save_pasted_lesson_source(payload)
    analysis = interface.analyze_pasted_lesson_source(source["source_id"])
    playbook = interface.save_preliminary_playbook(source["source_id"])

    assert interface.list_pasted_lesson_sources() == [source]
    assert interface.load_pasted_lesson_source(
        source["source_id"]
    ) == source
    assert analysis["playbook"]["source_id"] == source["source_id"]
    assert analysis["playbook"]["activities"][0]["duration_minutes"] == 10
    assert "Unclassified note." in analysis["unclassified_sections"]
    assert playbook["source_id"] == source["source_id"]
    assert interface.list_teacher_playbooks() == [playbook]
    assert interface.load_teacher_playbook(
        playbook["playbook_id"]
    ) == playbook


def test_pasted_lesson_enrichment_requires_review_before_save(tmp_path):
    class Provider:
        provider_name = "fake"
        model_name = "review-model"

        def enrich(self, context, prompt_contract):
            playbook = context.baseline.playbook.model_copy(deep=True)
            playbook.teacher_survival_guide.append(
                "Keep the evidence chart visible."
            )
            return PlaybookEnrichmentProviderResponse(raw_payload={
                "enriched_playbook": playbook.model_dump(mode="json"),
                "source_backed_fields": ["objectives"],
                "inferred_fields": ["teacher_survival_guide.0"],
                "omitted_unsupported_fields": [],
            })

    teacheros, _ = prepared_fixture(tmp_path)
    repository = PastedLessonRepository(tmp_path / "pasted")
    interface = TeacherOSInterface(
        teacheros,
        pasted_repository=repository,
        playbook_enrichment_provider=Provider(),
    )
    source = interface.save_pasted_lesson_source({
        "grade": "8",
        "unit": "1",
        "lesson_number": 1,
        "lesson_title": "Synthetic Review",
        "teacher_guide_text": (
            "Objectives:\n- Analyze evidence.\n"
            "Activity: Evidence Talk — 10 minutes\n"
        ),
    })

    preview = interface.enrich_pasted_lesson_source(
        source["source_id"], {}
    )
    assert preview["status"] == "success"
    assert repository.list_approved_enrichments() == []

    approved = interface.approve_playbook_enrichment(
        preview["enrichment_id"]
    )
    assert approved["teacher_approval_status"] == "approved"
    assert len(repository.list_approved_enrichments()) == 1
    with pytest.raises(KeyError):
        interface.approve_playbook_enrichment(
            preview["enrichment_id"]
        )
