"""Integration tests for the deterministic TeacherOS preparation entry point."""

import json

import fitz

from app.cli import main
from app.teacheros import TeacherOS
from curriculum.lesson_locator import CKLALessonLocator
from curriculum.library import CurriculumLibrary


def make_pdf(path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 760), text, fontsize=11)
    document.save(path)
    document.close()


def prepared_fixture(tmp_path, *, warnings=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    guide = tmp_path / "guide.pdf"
    reader = tmp_path / "reader.pdf"
    activity = tmp_path / "activity.pdf"
    make_pdf(guide, [
        "LESSON 1\nAT A GLANCE CHART\nLesson Time Activity Materials\n"
        "DAY 1: Reading 45 min Close Reading: \"First Story\" Reader Book Activity Page 1.1\n"
        "Primary Focus Objectives\nBy the end of this lesson, students will be able to:\nReading\n"
        "Cite textual evidence. (RL.8.1)\nADVANCE PREPARATION\nLesson one exact text",
        "Lesson one continuation\nTake-Home Material\nReading\n• Assign the story (pages 12-18) as reading homework.",
        "LESSON 2: Second Lesson\nSecond lesson exact text",
    ])
    reader.touch()
    activity.touch()
    library = CurriculumLibrary(tmp_path / "library.sqlite3", tmp_path)
    unit = library.register_unit(curriculum_name="CKLA", grade=8, unit=1,
        teacher_guide_path=guide, student_reader_path=reader, activity_book_path=activity)
    locator = CKLALessonLocator(index_directory=tmp_path / "indexes")
    index = locator.build_index(unit, guide)
    if warnings:
        index.extraction_warnings.append("Synthetic extraction warning.")
    locator.save_index(index)
    teacheros = TeacherOS(project_root=tmp_path, library=library, locator=locator,
                          output_directory=tmp_path / "outputs")
    return teacheros, locator.default_index_path(unit)


def test_success_loads_index_selects_range_hands_off_metadata_and_writes_json(tmp_path) -> None:
    teacheros, index_path = prepared_fixture(tmp_path)
    before = index_path.stat().st_mtime_ns
    result = teacheros.prepare_lesson(grade=8, unit=1, lesson_number=1)

    assert result.status in {"completed", "completed_with_warnings"}
    assert index_path.stat().st_mtime_ns == before
    assert result.lesson_title == 'Close Reading: "First Story"'
    assert result.teacher_guide_page_range.start_pdf_page == 0
    assert result.teacher_guide_page_range.end_pdf_page == 1
    assert result.lesson_metadata.standards == ["RL.8.1"]
    assert "Lesson one exact text" in result.lesson_source.extracted_text
    assert "Second lesson exact text" not in result.lesson_source.extracted_text

    output = tmp_path / "outputs/ckla_grade_8_unit_1_lesson_1_pipeline_input.json"
    assert result.output_files == [str(output)]
    payload = json.loads(output.read_text())
    assert payload["request"]["request_id"] == "ckla-grade-8-unit-1-lesson-1"
    assert payload["standards"] == ["RL.8.1"]
    assert payload["teacher_guide_lesson_text"] == result.lesson_source.extracted_text


def test_warnings_are_preserved_and_output_is_stable(tmp_path) -> None:
    teacheros, _ = prepared_fixture(tmp_path, warnings=True)
    first = teacheros.prepare_lesson(grade=8, unit=1, lesson_number=1)
    output = first.output_files[0]
    first_json = open(output, encoding="utf-8").read()
    second = teacheros.prepare_lesson(grade=8, unit=1, lesson_number=1)
    second_json = open(output, encoding="utf-8").read()
    assert "Synthetic extraction warning." in first.warnings
    assert "Synthetic extraction warning." in json.loads(first_json)["extraction_warnings"]
    assert first.model_dump() == second.model_dump()
    assert first_json == second_json


def test_missing_curriculum_missing_index_and_invalid_lesson_are_clear(tmp_path) -> None:
    empty = TeacherOS(project_root=tmp_path, database_path=tmp_path / "empty.sqlite3")
    missing_curriculum = empty.prepare_lesson(curriculum_name="Unknown", grade=8, unit=1, lesson_number=1)
    assert missing_curriculum.status == "failed"
    assert "curriculum lookup failed" in missing_curriculum.errors[0]

    teacheros, index_path = prepared_fixture(tmp_path / "registered")
    index_path.unlink()
    missing_index = teacheros.prepare_lesson(grade=8, unit=1, lesson_number=1)
    assert missing_index.status == "failed"
    assert "index loading failed" in missing_index.errors[0]

    teacheros, _ = prepared_fixture(tmp_path / "lesson")
    invalid = teacheros.prepare_lesson(grade=8, unit=1, lesson_number=99)
    assert invalid.status == "failed"
    assert "lesson selection failed" in invalid.errors[0]


def test_cli_returns_nonzero_on_failure_and_prints_success(tmp_path, capsys, monkeypatch) -> None:
    teacheros, _ = prepared_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["prepare-lesson", "--grade", "8", "--unit", "1", "--lesson", "1",
                 "--database", "library.sqlite3", "--index-directory", "indexes",
                 "--output-directory", "cli-output"]) == 0
    assert "Prepared CKLA Grade 8 Unit 1 Lesson 1" in capsys.readouterr().out
    assert main(["prepare-lesson", "--curriculum", "Missing", "--grade", "8", "--unit", "1",
                 "--lesson", "1", "--database", "library.sqlite3"]) == 2
    assert "Preparation failed" in capsys.readouterr().err
