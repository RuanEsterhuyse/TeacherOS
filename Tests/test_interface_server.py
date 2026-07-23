"""Tests for the non-blocking TeacherOS interface bridge."""

import time
from types import SimpleNamespace

from app.interface_server import TeacherOSInterface
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
