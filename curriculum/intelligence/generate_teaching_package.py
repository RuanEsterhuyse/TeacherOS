"""Generate a validated Teacher Companion and synchronized student slides."""

from __future__ import annotations

import argparse
from pathlib import Path

from curriculum.intelligence.generate_lesson_intelligence import (
    build_lesson_intelligence,
)
from curriculum.intelligence.teaching_package import (
    TeachingPackageBuilder,
    load_cached_teaching_package,
)
from renderer.teaching_package_markdown import (
    StudentSlidesMarkdownRenderer,
    TeacherCompanionMarkdownRenderer,
    deterministic_json,
    validation_markdown,
)
from schemas.teaching_package_schema import StructuredTeachingPackage


def write_teaching_package_artifacts(
    package: StructuredTeachingPackage,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Write deterministic local artifacts after successful validation."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "package": output / "teaching_package.json",
        "validation_json": output / "teaching_package_validation.json",
        "validation_markdown": output / "teaching_package_validation.md",
        "teacher_json": output / "teacher_companion.json",
        "teacher_markdown": output / "teacher_companion.md",
        "slides_json": output / "student_slides.json",
        "slides_markdown": output / "student_slides.md",
    }
    paths["package"].write_text(
        deterministic_json(package), encoding="utf-8"
    )
    paths["validation_json"].write_text(
        deterministic_json(package.validation), encoding="utf-8"
    )
    paths["validation_markdown"].write_text(
        validation_markdown(package), encoding="utf-8"
    )
    if package.validation.status == "fail":
        for key in (
            "teacher_json", "teacher_markdown",
            "slides_json", "slides_markdown",
        ):
            paths[key].unlink(missing_ok=True)
        raise ValueError(
            "Teaching package validation failed: "
            + "; ".join(
                f"{value.code}: {value.message}"
                for value in package.validation.findings
                if value.severity.value == "error"
            )
        )
    paths["teacher_json"].write_text(
        deterministic_json(package), encoding="utf-8"
    )
    paths["teacher_markdown"].write_text(
        TeacherCompanionMarkdownRenderer().render(package),
        encoding="utf-8",
    )
    paths["slides_json"].write_text(
        deterministic_json(package.student_slides), encoding="utf-8"
    )
    paths["slides_markdown"].write_text(
        StudentSlidesMarkdownRenderer().render(package),
        encoding="utf-8",
    )
    return paths


def generate_teaching_package(
    *,
    lesson: int,
    output_directory: str | Path,
    cache_root: str | Path = "output/curriculum_intelligence",
    database_path: str | Path = "data/curriculum/library.sqlite3",
    resume: bool = True,
) -> tuple[StructuredTeachingPackage, dict[str, Path], bool]:
    """Build or resume one package without AI or network calls."""
    bundle, intelligence, _ = build_lesson_intelligence(
        lesson=lesson,
        cache_root=cache_root,
        database_path=database_path,
    )
    package_path = Path(output_directory) / "teaching_package.json"
    package = (
        load_cached_teaching_package(
            package_path,
            bundle_digest=bundle.bundle_digest,
            intelligence_digest=intelligence.package_digest,
        )
        if resume
        else None
    )
    resumed = package is not None
    if package is None:
        package = TeachingPackageBuilder().build(
            bundle=bundle,
            intelligence=intelligence,
        )
    paths = write_teaching_package_artifacts(package, output_directory)
    return package, paths, resumed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--cache-root", default="output/curriculum_intelligence"
    )
    parser.add_argument(
        "--database", default="data/curriculum/library.sqlite3"
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    try:
        package, paths, resumed = generate_teaching_package(
            lesson=args.lesson,
            output_directory=args.output,
            cache_root=args.cache_root,
            database_path=args.database,
            resume=not args.no_resume,
        )
    except (OSError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    print(f"Teaching package: {paths['package']}")
    print(f"Teacher Companion: {paths['teacher_markdown']}")
    print(f"Student slides: {paths['slides_markdown']}")
    print(f"Validation: {package.validation.status}")
    print(f"Cache reused: {'yes' if resumed else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
