"""Tests for SQLite-backed curriculum registration."""

from curriculum.library import CurriculumLibrary


def test_register_retrieve_update_list_and_remove(tmp_path) -> None:
    guide = tmp_path / "guide.pdf"
    guide.touch()
    library = CurriculumLibrary(tmp_path / "library.sqlite3", tmp_path)
    created = library.register_unit(curriculum_name="CKLA", grade=8, unit=1, unit_title="Fiction",
                                    teacher_guide_path=guide, student_reader_path="missing.pdf")
    assert created.teacher_guide_path == "guide.pdf"
    assert library.get_unit("CKLA", 8, 1).unit_title == "Fiction"
    assert library.list_units() == [created]
    assert library.verify_files_exist(created) == {
        "teacher_guide_path": True, "student_reader_path": False, "activity_book_path": False,
    }
    updated = library.update_unit("CKLA", 8, 1, unit_title="Updated")
    assert updated.unit_title == "Updated"
    assert updated.updated_at >= created.updated_at
    assert library.remove_unit("CKLA", 8, 1)
    assert library.list_units() == []
