"""Create a review-only Lesson 2 curriculum resource mapping proposal."""

from __future__ import annotations

import argparse
from pathlib import Path

from curriculum.intelligence.lesson_resource_mapping import (
    LessonTwoResourceMappingBuilder,
)
from curriculum.intelligence.mapping_review import lesson_mapping_review_markdown
from curriculum.intelligence.repository import CurriculumIntelligenceRepository


def propose_lesson_mapping(
    *,
    unit: int,
    lesson: int,
    index_path: str | Path = "data/indexes/ckla_grade_8_unit_1_index.json",
    database_path: str | Path = "data/curriculum/library.sqlite3",
    manifest_path: str | Path = (
        "curriculum/mappings/"
        "ckla_grade_8_unit_1_lesson_2_resource_manifest.json"
    ),
    review_path: str | Path = (
        "output/review/unit_01/lesson_002_resource_mapping_review.md"
    ),
) -> tuple[Path, Path]:
    if unit != 1 or lesson != 2:
        raise ValueError(
            "This review-only workflow is intentionally scoped to CKLA "
            "Grade 8 Unit 1 Lesson 2."
        )
    manifest = LessonTwoResourceMappingBuilder().build(
        index_path=index_path,
        repository=CurriculumIntelligenceRepository(database_path),
    )
    manifest_target = Path(manifest_path)
    manifest_target.parent.mkdir(parents=True, exist_ok=True)
    manifest_target.write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    review_target = Path(review_path)
    review_target.parent.mkdir(parents=True, exist_ok=True)
    review_target.write_text(
        lesson_mapping_review_markdown(manifest), encoding="utf-8"
    )
    deterministic = sum(
        item.verification_status.value == "deterministically_verified"
        for item in manifest.assignments
    )
    proposed = sum(
        item.verification_status.value == "proposed_for_review"
        for item in manifest.assignments
    )
    reviewed = sum(
        item.verification_status.value == "human_reviewed_override"
        for item in manifest.assignments
    )
    unresolved = sum(
        item.verification_status.value == "unresolved"
        for item in manifest.assignments
    )
    print(f"Wrote manifest: {manifest_target}")
    print(f"Wrote review document: {review_target}")
    print(
        f"Assignments: {deterministic} deterministic, "
        f"{reviewed} human reviewed, {proposed} proposed for review, "
        f"{unresolved} unresolved."
    )
    return manifest_target, review_target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", type=int, required=True)
    parser.add_argument("--lesson", type=int, required=True)
    parser.add_argument(
        "--index", default="data/indexes/ckla_grade_8_unit_1_index.json"
    )
    parser.add_argument("--database", default="data/curriculum/library.sqlite3")
    parser.add_argument(
        "--manifest",
        default=(
            "curriculum/mappings/"
            "ckla_grade_8_unit_1_lesson_2_resource_manifest.json"
        ),
    )
    parser.add_argument(
        "--review",
        default=(
            "output/review/unit_01/"
            "lesson_002_resource_mapping_review.md"
        ),
    )
    args = parser.parse_args()
    propose_lesson_mapping(
        unit=args.unit,
        lesson=args.lesson,
        index_path=args.index,
        database_path=args.database,
        manifest_path=args.manifest,
        review_path=args.review,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["propose_lesson_mapping"]
