"""Create review-only indexed curriculum resource mapping proposals."""

from __future__ import annotations

import argparse
from pathlib import Path
import traceback

from curriculum.intelligence.lesson_resource_mapping import (
    IndexedLessonResourceMappingBuilder,
)
from curriculum.intelligence.mapping_review import (
    consolidated_mapping_review_markdown,
    lesson_mapping_review_markdown,
)
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
from schemas.curriculum_mapping_proposal_schema import (
    LessonResourceMappingManifest,
)


def _lesson_numbers(value: str) -> list[int]:
    values = []
    for component in value.split(","):
        part = component.strip()
        if "-" in part:
            start, end = (int(item) for item in part.split("-", 1))
            if end < start:
                raise ValueError("Lesson range is reversed.")
            values.extend(range(start, end + 1))
        else:
            values.append(int(part))
    output = list(dict.fromkeys(values))
    if not output or any(value < 2 or value > 9 for value in output):
        raise ValueError("Proposal lessons must be within indexed Lessons 2–9.")
    return output


def propose_lesson_mapping(
    *,
    unit: int,
    lesson: int,
    index_path: str | Path = (
        "data/indexes/ckla_grade_8_unit_1_index.json"
    ),
    database_path: str | Path = "data/curriculum/library.sqlite3",
    manifest_path: str | Path | None = None,
    review_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write one authoritative JSON proposal and ignored review document."""
    if unit != 1:
        raise ValueError(
            "The registered review workflow currently supports Unit 1."
        )
    manifest = IndexedLessonResourceMappingBuilder().build(
        index_path=index_path,
        repository=CurriculumIntelligenceRepository(database_path),
        lesson_number=lesson,
    )
    manifest_target = (
        Path(manifest_path)
        if manifest_path is not None
        else Path(
            "curriculum/mappings/"
            f"ckla_grade_8_unit_1_lesson_{lesson}_resource_manifest.json"
        )
    )
    review_target = (
        Path(review_path)
        if review_path is not None
        else Path(
            "output/review/unit_01/"
            f"lesson_{lesson:03d}_resource_mapping_review.md"
        )
    )
    manifest_target.parent.mkdir(parents=True, exist_ok=True)
    manifest_target.write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    review_target.parent.mkdir(parents=True, exist_ok=True)
    review_target.write_text(
        lesson_mapping_review_markdown(manifest), encoding="utf-8"
    )
    counts = {
        status: sum(
            item.verification_status.value == status
            for item in manifest.assignments
        )
        for status in (
            "deterministically_verified",
            "human_reviewed_override",
            "proposed_for_review",
            "unresolved",
            "unavailable_in_registered_sources",
        )
    }
    print(f"Wrote manifest: {manifest_target}")
    print(f"Wrote review document: {review_target}")
    print(
        f"Assignments: {counts['deterministically_verified']} "
        f"deterministic, {counts['human_reviewed_override']} human "
        f"reviewed, {counts['proposed_for_review']} proposed for review, "
        f"{counts['unresolved']} unresolved, "
        f"{counts['unavailable_in_registered_sources']} unavailable."
    )
    return manifest_target, review_target


def propose_lesson_mappings(
    *,
    unit: int,
    lessons: list[int],
    index_path: str | Path = (
        "data/indexes/ckla_grade_8_unit_1_index.json"
    ),
    database_path: str | Path = "data/curriculum/library.sqlite3",
    mapping_directory: str | Path = "curriculum/mappings",
    review_directory: str | Path = "output/review/unit_01",
) -> tuple[list[Path], Path, dict[int, str]]:
    """Generate a batch while retaining explicit per-lesson failures."""
    manifests: list[LessonResourceMappingManifest] = []
    manifest_paths: list[Path] = []
    failures: dict[int, str] = {}
    repository = CurriculumIntelligenceRepository(database_path)
    builder = IndexedLessonResourceMappingBuilder()
    for lesson in lessons:
        try:
            manifest = builder.build(
                index_path=index_path,
                repository=repository,
                lesson_number=lesson,
            )
            manifest_path = (
                Path(mapping_directory)
                / f"ckla_grade_8_unit_1_lesson_{lesson}_resource_manifest.json"
            )
            review_path = (
                Path(review_directory)
                / f"lesson_{lesson:03d}_resource_mapping_review.md"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                manifest.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(
                lesson_mapping_review_markdown(manifest),
                encoding="utf-8",
            )
            manifests.append(manifest)
            manifest_paths.append(manifest_path)
            print(f"Lesson {lesson} ........ OK")
        except Exception as error:
            failures[lesson] = (
                f"{type(error).__name__}: {error}; "
                f"{traceback.format_exc().strip().splitlines()[-1]}"
            )
            print(f"Lesson {lesson} ........ FAILED")
    consolidated = (
        Path(review_directory)
        / (
            f"lessons_{min(lessons):03d}_{max(lessons):03d}"
            "_mapping_review.md"
        )
    )
    consolidated.parent.mkdir(parents=True, exist_ok=True)
    consolidated.write_text(
        consolidated_mapping_review_markdown(
            manifests, failures=failures
        ),
        encoding="utf-8",
    )
    print(f"Wrote consolidated review: {consolidated}")
    return manifest_paths, consolidated, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", type=int, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--lesson", type=int)
    selection.add_argument("--lessons")
    parser.add_argument(
        "--index",
        default="data/indexes/ckla_grade_8_unit_1_index.json",
    )
    parser.add_argument(
        "--database", default="data/curriculum/library.sqlite3"
    )
    parser.add_argument("--manifest")
    parser.add_argument("--review")
    parser.add_argument(
        "--mapping-directory", default="curriculum/mappings"
    )
    parser.add_argument(
        "--review-directory", default="output/review/unit_01"
    )
    args = parser.parse_args()
    if args.lesson is not None:
        propose_lesson_mapping(
            unit=args.unit,
            lesson=args.lesson,
            index_path=args.index,
            database_path=args.database,
            manifest_path=args.manifest,
            review_path=args.review,
        )
    else:
        if args.manifest or args.review:
            parser.error(
                "--manifest and --review apply only to one --lesson."
            )
        propose_lesson_mappings(
            unit=args.unit,
            lessons=_lesson_numbers(args.lessons),
            index_path=args.index,
            database_path=args.database,
            mapping_directory=args.mapping_directory,
            review_directory=args.review_directory,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "propose_lesson_mapping",
    "propose_lesson_mappings",
]
