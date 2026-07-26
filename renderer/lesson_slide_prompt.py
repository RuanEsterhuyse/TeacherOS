"""Renderer-neutral slide prompt derived from lesson intelligence."""

from schemas.lesson_intelligence_package_schema import LessonIntelligencePackage


class LessonSlidePromptRenderer:
    def render(self, package: LessonIntelligencePackage) -> str:
        lines = [
            "# Classroom Presentation Generation Prompt", "",
            "Create a classroom-ready student presentation from the specifications below.",
            "Do not shorten, omit, merge, reorder, rewrite, or fabricate required lesson content.",
            "Never invent curriculum facts, quotations, answers, page numbers, maps, source visuals, or book covers.",
            "Use grade-appropriate language, minimal student-facing text, strong visual hierarchy, editable objects, accessible contrast, and readable projection sizes.",
            "Include every required question. Preserve publisher answers faithfully in teacher notes or an appropriate reveal; label TeacherOS support as draft/unreviewed.",
            "Add teacher notes for every slide. Visual suggestions are recommendations only and never evidence that a source asset exists.", "",
            f"Lesson: {package.identity.lesson_title}",
            f"Duration: {package.identity.estimated_duration_minutes} minutes",
            f"Package digest: {package.package_digest}", "",
            f"Produce exactly {len(package.slide_specifications)} slides:", "",
        ]
        for slide in package.slide_specifications:
            lines += [
                f"## Slide {slide.slide_number}: {slide.title}", "",
                f"- Purpose: {slide.purpose}",
                "- Student-facing content:",
                *[f"  - {x}" for x in slide.student_facing_content],
                "- Teacher notes:",
                *[f"  - {x}" for x in slide.teacher_notes],
                f"- Question IDs: {', '.join(slide.question_ids) or 'None'}",
                "- Answer guidance:",
                *([f"  - {x}" for x in slide.answer_guidance] or ["  - None"]),
                f"- Visual recommendation: {slide.visual_recommendation}",
                f"- Interaction format: {slide.interaction_format}",
                f"- Source/provenance: {', '.join(slide.provenance_references)}", "",
            ]
        return "\n".join(lines).rstrip() + "\n"


__all__ = ["LessonSlidePromptRenderer"]
