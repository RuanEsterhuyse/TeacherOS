"""Markdown formatting for a compiled Lesson Intelligence Package."""

from __future__ import annotations

from schemas.lesson_intelligence_package_schema import LessonIntelligencePackage


def _content(item) -> str:
    label = {
        "publisher_source": "Publisher source",
        "teacheros_interpretation": "TeacherOS interpretation",
        "teacheros_ai_support": "TeacherOS AI support — draft/unreviewed",
        "source_limitation": "Source limitation",
    }[item.classification.value]
    citations = "; ".join(
        f"{c.source_document}, PDF {c.pdf_page_number} (display {c.display_page_number}"
        + (f", printed {c.printed_page}" if c.printed_page else "") + ")"
        for c in item.citations
    )
    return f"**{label}:** {item.text}" + (f"  \n*Source: {citations}*" if citations else "")


class LessonIntelligenceMarkdownRenderer:
    def render(self, package: LessonIntelligencePackage) -> str:
        i = package.identity
        lines = [
            "# Lesson Identity", "",
            f"- Curriculum/program: {i.curriculum_program}",
            f"- Grade: {i.grade}", f"- Unit: {i.unit}",
            f"- Lesson number: {i.lesson_number}", f"- Lesson title: {i.lesson_title}",
            f"- Estimated duration: {i.estimated_duration_minutes} minutes",
            f"- Source document: {i.source_document_identity}",
            f"- Source page range: {i.source_page_range}",
            f"- Package metadata: compiler 1.0; generated {package.generated_at}",
            f"- Bundle digest: `{package.bundle_digest}`",
            f"- Package digest: `{package.package_digest}`", "",
            "# Lesson at a Glance", "",
        ]
        lines += [f"- {_content(x)}" for x in package.lesson_at_a_glance]
        lines += ["", "# Learning Objectives", ""]
        for n, objective in enumerate(package.objectives, 1):
            lines += [f"## Objective {n}", "", _content(objective.publisher_objective), "",
                      _content(objective.student_friendly_interpretation), "",
                      _content(objective.evidence_of_mastery), "",
                      f"Related phases: {', '.join(objective.phase_ids)}", ""]
        lines += ["# Standards and Language Demands", ""]
        lines += [f"- {_content(x)}" for x in package.standards]
        for d in package.language_demands:
            lines += ["", f"## {d.phase_id}", "",
                      f"- Function: {d.language_function}", f"- Domain: {d.language_domain}",
                      f"- Forms: {', '.join(d.language_forms)}",
                      f"- Likely ELD difficulty: {d.likely_eld_difficulty}",
                      f"- Supports: {', '.join(d.supports)}"]
        lines += ["", "# Before You Teach", ""]
        lines += [f"- {_content(x)}" for x in package.before_you_teach]
        lines += ["", "# Vocabulary Guide", ""]
        if not package.vocabulary:
            lines.append("No discrete vocabulary entries were present in the verified canonical source.")
        for word in package.vocabulary:
            lines += [f"## {word.word}", "", _content(word.student_friendly_explanation),
                      "", f"- Example: {word.example.text}", f"- Likely misconception: {word.misconception}",
                      f"- ELD support: {word.eld_support}", f"- Visual suggestion: {word.visual_suggestion}", ""]
        lines += ["# Lesson Sequence and Pacing", ""]
        for phase in package.phases:
            lines += [f"## {phase.sequence}. {phase.title}", "",
                      f"- Intended time: {phase.duration_minutes if phase.duration_minutes is not None else 'Preparation / not timed'}",
                      f"- Purpose: {phase.purpose.text}", "- Teacher actions:"]
            lines += [f"  - {x.text}" for x in phase.teacher_actions]
            lines += ["- Student actions:"] + [f"  - {x.text}" for x in phase.student_actions]
            lines += [f"- Materials: {', '.join(phase.materials)}",
                      f"- Transition in: {phase.transition_in.text}", f"- Watch for: {phase.watch_for.text}",
                      f"- Check for understanding: {phase.check_for_understanding.text}",
                      f"- Language support: {phase.language_support.text}",
                      f"- Transition out: {phase.transition_out.text}", ""]
        lines += ["# Reading or Text Walkthrough", ""]
        for reading in package.reading_guides:
            lines += [f"## {reading.title}", "", f"- Assigned pages: {reading.page_reference}",
                      f"- Source available: {'yes' if reading.source_available else 'no'}",
                      f"- Purpose: {reading.purpose.text}",
                      f"- Likely difficulties: {', '.join(reading.comprehension_difficulties)}",
                      f"- Pause points: {', '.join(reading.pause_points)}",
                      f"- ELD scaffolds: {', '.join(reading.eld_scaffolds)}"]
            lines += [f"- {_content(x)}" for x in reading.limitations] + [""]
        lines += ["# Complete Question and Answer Guide", ""]
        for q in package.questions:
            answer = q.publisher_answer.text if q.publisher_answer else "Not located in the verified Teacher Guide source."
            lines += [f"## Question {q.sequence}: {q.question_id}", "",
                      f"- Lesson phase: {q.phase_id}", f"- Question: {q.question.text}",
                      f"- Interaction: {q.interaction_format}",
                      f"- Source page: {', '.join(str(c.display_page_number) for c in q.question.citations)}",
                      f"- Publisher answer: {answer}",
                      f"- Publisher answer source page: {', '.join(str(c.display_page_number) for c in q.publisher_answer.citations) if q.publisher_answer else 'Not located'}",
                      f"- Answer provenance status: `{q.answer_provenance_status.value}`",
                      f"- Teacher explanation: {q.teacher_explanation.text}",
                      f"- Why supported: {q.support_rationale.text}",
                      f"- Likely incomplete responses: {', '.join(q.likely_incomplete_responses)}",
                      f"- Misconception: {q.misconception}", f"- Follow-up: {q.follow_up}",
                      f"- Check for understanding: {q.check_for_understanding}",
                      f"- Sentence frame: {q.sentence_frame}",
                      f"- Differentiation/extension: {q.differentiation_or_extension}", ""]
        lines += ["# Activity Book and Student Materials Guide", ""]
        for a in package.activities:
            lines += [f"## {a.name}", "", f"- Purpose: {a.purpose.text}",
                      f"- Teacher directions: {a.teacher_directions.text}",
                      f"- Student task: {a.student_task.text}", f"- Expected product: {a.expected_product.text}",
                      f"- Common difficulty: {a.common_difficulty}", f"- Language support: {a.language_support}",
                      f"- Completion check: {a.completion_check}", ""]
        lines += ["# Discussion Facilitation Guide", ""]
        lines += [f"- {_content(x)}" for x in package.discussion_facilitation] + [""]
        lines += ["# Differentiation and ELD Support", ""]
        for phase_id, items in package.differentiation_and_eld.items():
            lines += [f"## {phase_id}", ""] + [f"- {_content(x)}" for x in items] + [""]
        for title, items in [
            ("# Checks for Understanding", package.checks_for_understanding),
            ("# Assessment and Evidence of Learning", package.assessment_and_evidence),
            ("# Homework or Closing Tasks", package.homework_and_closing),
        ]:
            lines += [title, ""] + [f"- {_content(x)}" for x in items] + [""]
        lines += ["# Teacher Preparation Checklist", ""]
        for title, items in package.teacher_preparation_checklist.items():
            lines += [f"## {title.title()}", ""] + [f"- [ ] {x}" for x in items] + [""]
        lines += ["# Source and Provenance Index", ""]
        for c in package.provenance_index:
            lines.append(f"- {c.stable_source_id}: {c.source_document}, PDF {c.pdf_page_number}, display {c.display_page_number}, classification publisher_source")
        return "\n".join(lines).rstrip() + "\n"


__all__ = ["LessonIntelligenceMarkdownRenderer"]
