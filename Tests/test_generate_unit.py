from __future__ import annotations

import json
from pathlib import Path

from curriculum.intelligence.generate_unit import (
    discover_unit_lessons,
    generate_unit,
)
from schemas.curriculum_schema import CurriculumIndex, CurriculumUnit, LessonIndexEntry


def _index(path: Path, lessons=(1, 2, 3)) -> Path:
    curriculum = CurriculumUnit(
        curriculum_name="CKLA",
        grade="8",
        unit="1",
        unit_title="Unit One",
        teacher_guide_path="ignored.pdf",
    )
    entries = [
        LessonIndexEntry(
            lesson_number=number,
            start_pdf_page=number,
            end_pdf_page=number,
            detected_heading=f"Lesson {number}",
            confidence=1,
            source_file="ignored.pdf",
        )
        for number in lessons
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        CurriculumIndex(
            curriculum=curriculum,
            total_pdf_pages=10,
            lessons=entries,
        ).model_dump_json(indent=2)
    )
    return path


def test_discovers_unit_lessons_from_saved_metadata(tmp_path):
    index = _index(tmp_path / "ckla_grade_8_unit_1_index.json")
    path, lessons = discover_unit_lessons(1, index_directory=tmp_path)
    assert path == index
    assert lessons == [1, 2, 3]


def test_generates_multiple_lessons_continues_and_writes_summaries(tmp_path):
    indexes = tmp_path / "indexes"
    _index(indexes / "ckla_grade_8_unit_1_index.json")
    calls = []

    def fake_generator(*, lesson, output_directory, **_):
        calls.append(lesson)
        if lesson == 2:
            raise RuntimeError("fixture failure")
        output = Path(output_directory)
        output.mkdir(parents=True)
        teacher = output / "lesson_intelligence_package.md"
        slides = output / "google_slides_prompt.md"
        teacher.write_text(f"teacher-{lesson}\n")
        slides.write_text(f"slides-{lesson}\n")
        return teacher, slides

    summary = generate_unit(
        unit=1,
        output_directory=tmp_path / "unit_01",
        index_directory=indexes,
        cache_root=tmp_path / "cache",
        database_path=tmp_path / "library.sqlite3",
        lesson_generator=fake_generator,
    )
    assert calls == [1, 2, 3]
    assert summary["lessons_attempted"] == 3
    assert summary["lessons_successfully_generated"] == 2
    assert summary["lessons_failed"] == 1
    assert summary["results"][1]["failure"]["exception_type"] == "RuntimeError"
    assert (tmp_path / "unit_01/lesson_001/lesson_intelligence_package.md").is_file()
    assert not (tmp_path / "unit_01/lesson_002/lesson_intelligence_package.md").exists()
    assert (tmp_path / "unit_01/lesson_003/google_slides_prompt.md").is_file()
    saved = json.loads(
        (tmp_path / "unit_01/unit_generation_summary.json").read_text()
    )
    assert saved["lessons_failed"] == 1
    assert "# Unit 1 Generation Summary" in (
        tmp_path / "unit_01/unit_generation_summary.md"
    ).read_text()


def test_unit_output_is_byte_equivalent_to_direct_single_lesson(tmp_path):
    indexes = tmp_path / "indexes"
    _index(indexes / "ckla_grade_8_unit_1_index.json", lessons=(1,))

    def deterministic_generator(*, lesson, output_directory, **_):
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        teacher = output / "lesson_intelligence_package.md"
        slides = output / "google_slides_prompt.md"
        teacher.write_bytes(f"package:{lesson}\n".encode())
        slides.write_bytes(f"prompt:{lesson}\n".encode())
        return teacher, slides

    direct = tmp_path / "direct"
    deterministic_generator(lesson=1, output_directory=direct)
    generate_unit(
        unit=1, output_directory=tmp_path / "unit",
        index_directory=indexes, cache_root=tmp_path / "cache",
        database_path=tmp_path / "db", lesson_generator=deterministic_generator,
    )
    assert (direct / "lesson_intelligence_package.md").read_bytes() == (
        tmp_path / "unit/lesson_001/lesson_intelligence_package.md"
    ).read_bytes()
    assert (direct / "google_slides_prompt.md").read_bytes() == (
        tmp_path / "unit/lesson_001/google_slides_prompt.md"
    ).read_bytes()


def test_existing_single_lesson_function_is_not_modified():
    from curriculum.intelligence.generate_lesson_intelligence import (
        generate_lesson_intelligence,
    )

    assert generate_lesson_intelligence.__name__ == "generate_lesson_intelligence"
