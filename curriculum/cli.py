"""Command-line interface for the TeacherOS Curriculum Library."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from curriculum.adapters import default_adapter_registry
from curriculum.library import CurriculumLibrary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register and locate lessons in local curriculum PDFs.")
    parser.add_argument("--database", default="data/curriculum/library.sqlite3", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="Register a curriculum unit")
    register.add_argument("--curriculum", required=True)
    register.add_argument("--grade", required=True)
    register.add_argument("--unit", required=True)
    register.add_argument("--unit-title")
    register.add_argument("--teacher-guide", required=True)
    register.add_argument("--student-reader")
    register.add_argument("--activity-book")

    for name, help_text in (
        ("index", "Build and save a lesson index"),
        ("list-lessons", "List lessons in a saved index"),
        ("extract-lesson", "Extract one indexed lesson"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--curriculum", default="CKLA")
        command.add_argument("--grade", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--index-file")
        if name == "index":
            command.add_argument("--override", help="Optional manual boundary override JSON")
        if name == "extract-lesson":
            command.add_argument("--lesson", required=True, type=int)
            command.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    library = CurriculumLibrary(database_path=args.database)
    try:
        if args.command == "register":
            record = library.register_unit(
                curriculum_name=args.curriculum, grade=args.grade, unit=args.unit,
                unit_title=args.unit_title, teacher_guide_path=args.teacher_guide,
                student_reader_path=args.student_reader, activity_book_path=args.activity_book,
            )
            missing = [name for name, exists in library.verify_files_exist(record).items() if not exists and getattr(record, name)]
            print(f"Registered {record.curriculum_name} grade {record.grade} unit {record.unit}.")
            if missing:
                print(f"Warning: missing files: {', '.join(missing)}", file=sys.stderr)
            return 0

        record = library.get_unit(args.curriculum, args.grade, args.unit)
        adapter = default_adapter_registry().create(
            record.curriculum_name,
            index_directory="data/indexes",
        )
        index_path = Path(args.index_file) if args.index_file else adapter.default_index_path(record)
        if args.command == "index":
            guide = library.resolve_path(record.teacher_guide_path)
            resource_errors = adapter.validate_required_resources(
                record,
                library.resolve_path,
            )
            if resource_errors:
                raise FileNotFoundError(resource_errors[0])
            index = adapter.detect_lesson_boundaries(
                record,
                guide,
                args.override,
            )
            saved = adapter.save_index(index, index_path)
            print(f"Indexed {len(index.lessons)} lessons across {index.total_pdf_pages} PDF pages: {saved}")
            for warning in index.extraction_warnings:
                print(f"Warning: {warning}", file=sys.stderr)
            return 0


        index = adapter.load_index(index_path)
        if args.command == "list-lessons":
            for lesson in index.lessons:
                title = f" — {lesson.lesson_title}" if lesson.lesson_title else ""
                print(f"Lesson {lesson.lesson_number}{title} | PDF pages {lesson.start_pdf_page + 1}-{lesson.end_pdf_page + 1} | confidence {lesson.confidence:.2f}")
            return 0

        guide = library.resolve_path(record.teacher_guide_path)
        source = adapter.prepare_lesson(index, args.lesson, guide)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source.extracted_text, encoding="utf-8")
        print(f"Extracted Lesson {source.lesson_number}, PDF pages {source.start_page + 1}-{source.end_page + 1}: {output}")
        return 0
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
