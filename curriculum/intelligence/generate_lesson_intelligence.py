"""Generate teacher-readable Lesson Intelligence documents from cache."""

from __future__ import annotations

import argparse
from pathlib import Path

from curriculum.intelligence.lesson_intelligence import (
    LessonIntelligenceCompiler,
    load_cached_support,
)
from curriculum.intelligence.repository import CurriculumIntelligenceRepository
from renderer.lesson_intelligence_markdown import LessonIntelligenceMarkdownRenderer
from renderer.lesson_slide_prompt import LessonSlidePromptRenderer
from schemas.canonical_lesson_schema import CanonicalLesson
from schemas.instructional_relationship_graph_schema import InstructionalRelationshipGraph
from schemas.prepared_curriculum_source_schema import PreparedCurriculumSourceBundle
from schemas.source_grounded_instruction_schema import SourceGroundedInstructionPlan


def generate_lesson_intelligence(
    *,
    lesson: int,
    output_directory: str | Path,
    cache_root: str | Path = "output/curriculum_intelligence",
    database_path: str | Path = "data/curriculum/library.sqlite3",
) -> tuple[Path, Path]:
    if lesson != 1:
        raise ValueError("Only cached indexed Lesson 1 is supported by this command.")
    cache = Path(cache_root) / "ckla-grade-8-unit-1-lesson-1"
    required = {
        "bundle": cache / "prepared_source_bundle.json",
        "canonical": cache / "bundle_derived_canonical_lesson.json",
        "plan": cache / "source_grounded_instruction_plan.json",
        "graph": cache / "instructional_relationship_graph.json",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Required cached lesson artifacts are missing: " + ", ".join(missing))
    bundle = PreparedCurriculumSourceBundle.model_validate_json(required["bundle"].read_text())
    canonical = CanonicalLesson.model_validate_json(required["canonical"].read_text())
    plan = SourceGroundedInstructionPlan.model_validate_json(required["plan"].read_text())
    graph = InstructionalRelationshipGraph.model_validate_json(required["graph"].read_text())
    support = load_cached_support(
        cache / "phase_teacher_support",
        bundle_digest=bundle.bundle_digest,
        plan_digest=plan.digest,
        graph_digest=graph.graph_digest,
    )
    package = LessonIntelligenceCompiler().compile(
        bundle=bundle, canonical=canonical, plan=plan, graph=graph,
        repository=CurriculumIntelligenceRepository(database_path),
        cached_support=support,
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    teacher_path = output / "lesson_intelligence_package.md"
    slide_path = output / "google_slides_prompt.md"
    teacher_path.write_text(LessonIntelligenceMarkdownRenderer().render(package), encoding="utf-8")
    slide_path.write_text(LessonSlidePromptRenderer().render(package), encoding="utf-8")
    linked = sum(q.answer_provenance_status.value == "publisher_answer_elsewhere_in_guide" for q in package.questions)
    print(f"Wrote {teacher_path}")
    print(f"Wrote {slide_path}")
    print(f"Publisher answers linked from later guide sections: {linked}")
    return teacher_path, slide_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache-root", default="output/curriculum_intelligence")
    parser.add_argument("--database", default="data/curriculum/library.sqlite3")
    args = parser.parse_args()
    generate_lesson_intelligence(
        lesson=args.lesson, output_directory=args.output,
        cache_root=args.cache_root, database_path=args.database,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
