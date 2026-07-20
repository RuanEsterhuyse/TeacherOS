"""Command-line application entry point for TeacherOS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from app.teacheros import TeacherOS
from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.lesson_schema import Lesson


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare curriculum lessons for TeacherOS.")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-lesson", help="Prepare a deterministic lesson pipeline input")
    prepare.add_argument("--curriculum", default="CKLA")
    prepare.add_argument("--grade", required=True)
    prepare.add_argument("--unit", required=True)
    prepare.add_argument("--lesson", required=True, type=int)
    prepare.add_argument("--database", default="data/curriculum/library.sqlite3", help=argparse.SUPPRESS)
    prepare.add_argument("--index-directory", default="data/indexes", help=argparse.SUPPRESS)
    prepare.add_argument("--output-directory", default="output/pipeline_inputs", help=argparse.SUPPRESS)
    generate = commands.add_parser("generate-lesson", help="Generate a validated renderer-ready lesson")
    generate.add_argument("--curriculum", default="CKLA")
    generate.add_argument("--grade", required=True)
    generate.add_argument("--unit", required=True)
    generate.add_argument("--lesson", required=True, type=int)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--no-resume", action="store_true", help="Repeat all generation stages")
    generate.add_argument("--database", default="data/curriculum/library.sqlite3", help=argparse.SUPPRESS)
    generate.add_argument("--index-directory", default="data/indexes", help=argparse.SUPPRESS)
    generate.add_argument("--output-directory", default="output/pipeline_inputs", help=argparse.SUPPRESS)
    generate.add_argument("--generation-output-directory", default="output/generation_runs", help=argparse.SUPPRESS)
    slides = commands.add_parser("create-slides", help="Render an existing validated lesson in Google Slides")
    slides.add_argument("--curriculum", default="CKLA")
    slides.add_argument("--grade", required=True)
    slides.add_argument("--unit", required=True)
    slides.add_argument("--lesson", required=True, type=int)
    slides.add_argument("--generation-output-directory", default="output/generation_runs", help=argparse.SUPPRESS)
    slides.add_argument("--credentials", default="credentials.json", help=argparse.SUPPRESS)
    slides.add_argument("--token", default="token.json", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    teacheros = TeacherOS(database_path=getattr(args, "database", "data/curriculum/library.sqlite3"),
                          index_directory=getattr(args, "index_directory", "data/indexes"),
                          output_directory=getattr(args, "output_directory", "output/pipeline_inputs"),
                          generation_output_directory=getattr(args, "generation_output_directory", "output/generation_runs"))
    if args.command == "create-slides":
        request = teacheros.create_lesson_request(curriculum_name=args.curriculum, grade=args.grade,
                                                  unit=args.unit, lesson_number=args.lesson)
        lesson_path = teacheros.generation_output_directory / request.request_id / "07_validated_lesson.json"
        try:
            lesson = Lesson.model_validate_json(lesson_path.read_text(encoding="utf-8"))
            expected = (request.grade, request.unit, request.lesson_number)
            actual = (lesson.grade, lesson.unit, lesson.lesson_number)
            if actual != expected:
                raise ValueError(
                    "Validated lesson identity does not match the request: "
                    f"expected Grade {expected[0]} Unit {expected[1]} Lesson {expected[2]}, "
                    f"found Grade {actual[0]} Unit {actual[1]} Lesson {actual[2]}"
                )
            renderer = GoogleSlidesRenderer(credentials_path=args.credentials, token_path=args.token)
            presentation = renderer.create_presentation(lesson)
        except FileNotFoundError as error:
            print(f"Error: {error}", file=sys.stderr)
            missing = Path(error.filename) if error.filename else None
            if not Path(args.credentials).is_file() or (
                missing and missing.resolve() == Path(args.credentials).resolve()
            ):
                print("Google OAuth setup: enable the Google Slides and Drive APIs, create a Desktop app "
                      "OAuth client, download it as credentials.json, then run this command again.", file=sys.stderr)
            return 2
        except (OSError, ValidationError, ValueError, TypeError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        print(f"Google Slides URL: {presentation['url']}")
        print(f"Presentation ID: {presentation['presentationId']}")
        print(f"Slides created: {len(presentation['slideIds'])}")
        print("Rendering warnings: none")
        return 0
    if args.command == "generate-lesson":
        result = teacheros.generate_lesson(curriculum_name=args.curriculum, grade=args.grade,
            unit=args.unit, lesson_number=args.lesson, dry_run=args.dry_run, resume=not args.no_resume)
        print(f"Request ID: {result.request_id}")
        if result.status == "dry_run":
            print("Dry run successful; no OpenAI API calls were made.")
            print("Planned stages: " + ", ".join(result.usage.get("planned_stages", [])))
        else:
            for stage in result.completed_stages:
                print(f"Completed: {stage}")
            print(f"Validation result: {result.validation_result or 'not reached'}")
            print(f"Slide count: {result.slide_count}")
            if result.usage:
                print(f"Usage: {result.usage}")
        print(f"Output directory: {result.output_directory}")
        for warning in result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        for error in result.errors:
            print(f"Error: {error}", file=sys.stderr)
        return 2 if result.status == "failed" else 0
    result = teacheros.prepare_lesson(curriculum_name=args.curriculum, grade=args.grade,
                                      unit=args.unit, lesson_number=args.lesson)
    if result.status == "failed":
        print(f"Preparation failed for {result.curriculum_name} Grade {result.grade} "
              f"Unit {result.unit} Lesson {result.lesson_number}.", file=sys.stderr)
    else:
        title = result.lesson_title or "title unavailable"
        pages = result.teacher_guide_page_range
        page_text = f"PDF pages {pages.display_start_page}-{pages.display_end_page}" if pages else "pages unavailable"
        print(f"Prepared {result.curriculum_name} Grade {result.grade} Unit {result.unit} "
              f"Lesson {result.lesson_number}: {title} ({page_text}).")
        print(f"Pipeline input: {result.output_files[0]}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"Error: {error}", file=sys.stderr)
    return 2 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
