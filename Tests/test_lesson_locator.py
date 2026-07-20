"""Tests for deterministic lesson boundary location and extraction."""

import json

import fitz

from curriculum.lesson_locator import CKLALessonLocator
from schemas.curriculum_schema import CurriculumUnit


def make_pdf(path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 760), text, fontsize=12)
    document.save(path)
    document.close()


def unit(path) -> CurriculumUnit:
    return CurriculumUnit(curriculum_name="CKLA", grade="8", unit="1", unit_title="Test",
                          teacher_guide_path=str(path))


def test_boundaries_ignore_contents_and_support_multi_digit_lessons(tmp_path) -> None:
    path = tmp_path / "guide.pdf"
    make_pdf(path, [
        "TABLE OF CONTENTS\nLesson 1 ........ 3\nLesson 2 ........ 5\nLesson 10 ....... 9\nLesson 11 ...... 12",
        "LESSON 1: Beginnings\nReal one text", "Continuation of one\nSee Lesson 10",
        "Lesson 2\nA Second Lesson\nReal two text", "More lesson two",
        "LESSON 10 — Ten Things\nReal ten text", "LESSON 2\nDuplicate reference",
        "LESSON 11: Eleven\nReal eleven text",
    ])
    locator = CKLALessonLocator(index_directory=tmp_path / "indexes")
    index = locator.build_index(unit(path), path)
    assert [item.lesson_number for item in index.lessons] == [1, 2, 10, 11]
    assert [(item.start_pdf_page, item.end_pdf_page) for item in index.lessons] == [(1, 2), (3, 4), (5, 6), (7, 7)]
    assert any("out-of-order" in warning for warning in index.extraction_warnings)
    assert index.lessons[1].lesson_title == "A Second Lesson"

    saved = locator.save_index(index)
    loaded = locator.load_index(saved)
    source = locator.extract_lesson_source(loaded, 10, path)
    assert "Real ten text" in source.extracted_text
    assert "Real two text" not in source.extracted_text
    assert "Real eleven text" not in source.extracted_text


def test_manual_override_adds_or_replaces_boundary(tmp_path) -> None:
    path = tmp_path / "guide.pdf"
    make_pdf(path, ["Preface", "Unusual heading\nLesson body", "LESSON 2: Next\nSecond body"])
    override = tmp_path / "override.json"
    override.write_text(json.dumps({"lessons": {"1": {"start_pdf_page": 1, "lesson_title": "Manual"}}}))
    locator = CKLALessonLocator()
    index = locator.build_index(unit(path), path, override)
    assert [(item.lesson_number, item.start_pdf_page, item.end_pdf_page) for item in index.lessons] == [(1, 1, 1), (2, 2, 2)]
    assert index.lessons[0].confidence == 1.0
    assert "manual override" in index.lessons[0].warnings[0].lower()


def test_standalone_reference_without_heading_support_is_ignored(tmp_path) -> None:
    path = tmp_path / "guide.pdf"
    make_pdf(path, [
        "LESSON 1: Real Start\nBody text",
        "Notes and cross references\nMore ordinary body\nLESSON 2\ncontinued discussion",
        "LESSON 2: Real Start\nSecond lesson body",
    ])
    locator = CKLALessonLocator()
    index = locator.build_index(unit(path), path)
    assert [(item.lesson_number, item.start_pdf_page) for item in index.lessons] == [(1, 0), (2, 2)]
    assert any("low-confidence" in warning for warning in index.extraction_warnings)


def test_ckla_front_matter_populates_instructional_metadata(tmp_path) -> None:
    path = tmp_path / "guide.pdf"
    make_pdf(path, [
        "LESSON 1\nAT A GLANCE CHART\nLesson Time Activity Materials\n"
        "DAY 1: Reading 45 min Close Reading: \"The Story\" Reader Book Activity Pages 1.1, 1.2\n"
        "DAY 2: Writing 30 min Draft a Response Activity Page 1.3\n"
        "Primary Focus Objectives\nBy the end of this lesson, students will be able to:\nReading\n"
        "Cite textual evidence accurately. (RL.8.1)\nWriting\nWrite a response. (W.8.3)",
        "ADVANCE PREPARATION\nTake-Home Material\nReading\n"
        "Assign the story (pages 12-18) as reading homework.\n"
        "UNIT ASSESSMENT\nComplete the Unit Assessment on Activity Page 1.3.",
    ])
    locator = CKLALessonLocator()
    entry = locator.build_index(unit(path), path).lessons[0]
    assert entry.lesson_title == 'Close Reading: "The Story"'
    assert entry.standards == ["RL.8.1", "W.8.3"]
    assert entry.lesson_duration == 75
    assert entry.activity_book_pages == ["1.1", "1.2", "1.3"]
    assert entry.reader_pages == ["12-18"]
    assert entry.homework == ["Assign the story (pages 12-18) as reading homework."]
    assert any("Unit Assessment" in value for value in entry.assessment_references)
