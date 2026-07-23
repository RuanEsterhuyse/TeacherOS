"""Tests for the non-blocking TeacherOS interface bridge."""

import json
import os
import time
from types import SimpleNamespace

from app.interface_server import GenerationJob, TeacherOSInterface
from app import interface_server
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
