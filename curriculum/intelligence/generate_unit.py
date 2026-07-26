"""Generate cached Lesson Intelligence outputs for every indexed unit lesson."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback
from typing import Callable

from curriculum.intelligence.generate_lesson_intelligence import (
    generate_lesson_intelligence,
)
from curriculum.lesson_locator import CKLALessonLocator
from schemas.source_grounded_instruction_schema import (
    SourceGroundedInstructionPlan,
)


LessonGenerator = Callable[..., tuple[Path, Path]]


def discover_unit_lessons(
    unit: int,
    *,
    index_directory: str | Path = "data/indexes",
) -> tuple[Path, list[int]]:
    """Return one unambiguous saved CKLA unit index and its lesson numbers."""
    candidates = sorted(
        Path(index_directory).glob(f"ckla_grade_*_unit_{unit}_index.json")
    )
    if not candidates:
        raise FileNotFoundError(
            f"No saved CKLA curriculum index was found for Unit {unit}."
        )
    if len(candidates) > 1:
        raise ValueError(
            f"Unit {unit} is ambiguous across saved CKLA indexes: "
            + ", ".join(str(path) for path in candidates)
        )
    index = CKLALessonLocator().load_index(candidates[0])
    if str(index.curriculum.unit) != str(unit):
        raise ValueError(
            f"Saved index unit {index.curriculum.unit} does not match requested "
            f"Unit {unit}."
        )
    lessons = [entry.lesson_number for entry in index.lessons]
    if not lessons:
        raise ValueError(f"The saved curriculum index for Unit {unit} has no lessons.")
    if len(lessons) != len(set(lessons)):
        raise ValueError(f"The saved curriculum index for Unit {unit} has duplicate lessons.")
    return candidates[0], lessons


def _structured_counts(
    lesson: int,
    *,
    cache_root: str | Path,
) -> tuple[int | None, int | None, int | None, list[str]]:
    """Read publisher question counts from the source-grounded plan."""
    candidates = sorted(
        Path(cache_root).glob(f"*-lesson-{lesson}/source_grounded_instruction_plan.json")
    )
    if len(candidates) != 1:
        warning = (
            f"Structured statistics unavailable: expected one cached instruction "
            f"plan for Lesson {lesson}, found {len(candidates)}."
        )
        return None, None, None, [warning]
    plan = SourceGroundedInstructionPlan.model_validate_json(
        candidates[0].read_text(encoding="utf-8")
    )
    questions = [question for phase in plan.instructional_phases for question in phase.questions]
    answer_count = sum(bool(question.answers) for question in questions)
    return len(questions), answer_count, len(questions) - answer_count, []


def _summary_markdown(summary: dict) -> str:
    lines = [
        f"# Unit {summary['requested_unit']} Generation Summary",
        "",
        f"- Index: {summary['curriculum_index']}",
        f"- Lessons discovered: {summary['lessons_discovered']}",
        f"- Lessons attempted: {summary['lessons_attempted']}",
        f"- Successfully generated: {summary['lessons_successfully_generated']}",
        f"- Failed: {summary['lessons_failed']}",
        f"- Total elapsed time: {summary['total_elapsed_seconds']:.3f} seconds",
        "",
        "## Lesson Results",
        "",
        "| Lesson | Status | Questions | Publisher answers | Unanswered | Output |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for result in summary["results"]:
        lines.append(
            f"| {result['lesson']} | {result['status']} | "
            f"{result['question_count'] if result['question_count'] is not None else '—'} | "
            f"{result['publisher_answer_count'] if result['publisher_answer_count'] is not None else '—'} | "
            f"{result['unanswered_publisher_question_count'] if result['unanswered_publisher_question_count'] is not None else '—'} | "
            f"{result['output_directory']} |"
        )
        if result["failure"]:
            lines.append(
                f"\n**Lesson {result['lesson']} failure:** "
                f"{result['failure']['exception_type']}: "
                f"{result['failure']['message']}"
            )
        for warning in result["warnings"]:
            lines.append(f"\n**Lesson {result['lesson']} warning:** {warning}")
    if summary["warnings"]:
        lines += ["", "## Unit Warnings", ""]
        lines += [f"- {warning}" for warning in summary["warnings"]]
    return "\n".join(lines).rstrip() + "\n"


def generate_unit(
    *,
    unit: int,
    output_directory: str | Path,
    index_directory: str | Path = "data/indexes",
    cache_root: str | Path = "output/curriculum_intelligence",
    database_path: str | Path = "data/curriculum/library.sqlite3",
    lesson_generator: LessonGenerator = generate_lesson_intelligence,
) -> dict:
    """Attempt every discovered lesson, preserving per-lesson failures."""
    index_path, lessons = discover_unit_lessons(
        unit, index_directory=index_directory
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    print(f"Generating Unit {unit}\n")
    results = []
    for lesson in lessons:
        lesson_output = output / f"lesson_{lesson:03d}"
        failure = None
        warnings: list[str] = []
        status = "ok"
        try:
            lesson_generator(
                lesson=lesson,
                output_directory=lesson_output,
                cache_root=cache_root,
                database_path=database_path,
            )
            question_count, answer_count, unanswered_count, count_warnings = (
                _structured_counts(lesson, cache_root=cache_root)
            )
            warnings.extend(count_warnings)
            print(f"Lesson {lesson} ........ OK")
        except Exception as error:  # continue-on-failure is intentional
            status = "failed"
            question_count = answer_count = unanswered_count = None
            failure = {
                "exception_type": type(error).__name__,
                "message": str(error),
                "traceback_summary": traceback.format_exc().strip().splitlines()[-1],
            }
            print(f"Lesson {lesson} ........ FAILED")
        results.append({
            "lesson": lesson,
            "status": status,
            "output_directory": str(lesson_output),
            "lesson_intelligence_package": (
                str(lesson_output / "lesson_intelligence_package.md")
                if status == "ok" else None
            ),
            "google_slides_prompt": (
                str(lesson_output / "google_slides_prompt.md")
                if status == "ok" else None
            ),
            "question_count": question_count,
            "publisher_answer_count": answer_count,
            "unanswered_publisher_question_count": unanswered_count,
            "warnings": warnings,
            "failure": failure,
        })
    elapsed = time.monotonic() - started
    succeeded = sum(result["status"] == "ok" for result in results)
    summary = {
        "requested_unit": unit,
        "curriculum_index": str(index_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lessons_discovered": lessons,
        "lessons_attempted": len(results),
        "lessons_successfully_generated": succeeded,
        "lessons_failed": len(results) - succeeded,
        "results": results,
        "warnings": [
            "A failed lesson was retained in this summary and did not stop later lessons."
        ] if succeeded != len(results) else [],
        "total_elapsed_seconds": round(elapsed, 6),
    }
    json_path = output / "unit_generation_summary.json"
    markdown_path = output / "unit_generation_summary.md"
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")
    print(f"\nSummary: {markdown_path}")
    print(f"Machine-readable summary: {json_path}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--index-directory", default="data/indexes")
    parser.add_argument("--cache-root", default="output/curriculum_intelligence")
    parser.add_argument("--database", default="data/curriculum/library.sqlite3")
    args = parser.parse_args()
    summary = generate_unit(
        unit=args.unit,
        output_directory=args.output,
        index_directory=args.index_directory,
        cache_root=args.cache_root,
        database_path=args.database,
    )
    return 0 if summary["lessons_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["discover_unit_lessons", "generate_unit"]
