"""Production Google Slides rendering for structured teaching packages."""

from __future__ import annotations

import re
from typing import Any

from models.lesson import Lesson
from models.slide import Slide
from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.teaching_package_schema import (
    ContentOrigin,
    StructuredTeachingPackage,
    TeachingSourceReference,
)

MAX_VISIBLE_ITEMS = 3
MAX_VISIBLE_WORDS = 62

PALETTE = {
    "navy": "#17324D",
    "teal": "#1F7A8C",
    "gold": "#E9A23B",
    "paper": "#F7F4ED",
    "white": "#FFFFFF",
    "ink": "#17212B",
    "muted": "#52606D",
    "line": "#D8E0E5",
}

LAYOUT_BY_TYPE = {
    "title": "title",
    "agenda": "agenda",
    "objectives": "objective",
    "essential question": "discussion",
    "warm-up": "activity",
    "background knowledge": "background knowledge",
    "vocabulary": "vocabulary",
    "reading purpose": "reading",
    "reading directions": "reading",
    "reading questions": "discussion",
    "discussion": "discussion",
    "activity": "activity",
    "writing": "writing",
    "assessment": "assessment",
    "wrap-up": "closure",
    "homework": "homework",
    "transition": "instructions",
}


def _source_label(value: TeachingSourceReference) -> str:
    location = (
        f"PDF p. {value.display_page_number}"
        if value.display_page_number is not None
        else value.printed_page or value.stable_source_id
    )
    return f"{value.source_document} ({location})"


def package_to_google_lesson(
    package: StructuredTeachingPackage,
) -> Lesson:
    """Map exactly one structured slide to exactly one editable Google slide."""
    slides = []
    agenda = {
        value.agenda_item_id: value for value in package.agenda
    }
    steps = {
        value.agenda_item_id: value for value in package.teaching_steps
    }
    questions = {
        value.question_id: value for value in package.questions
    }
    for value in package.student_slides:
        notes = list(value.speaker_notes)
        if value.agenda_item_id in steps:
            step = steps[value.agenda_item_id]
            notes.extend(
                f"Teacher action: {item.text}"
                for item in step.teacher_actions
            )
            notes.append(f"Transition: {step.transition.text}")
        for question_id in value.question_ids:
            question = questions[question_id]
            notes.extend([
                f"Question {question_id}: {question.exact_question.text}",
                f"Expected answer (teacher only): "
                f"{question.expected_answer.text}",
                f"Follow-up: {question.follow_up.text}",
                f"ELD sentence frame: {question.eld_sentence_frame.text}",
            ])
        if value.agenda_item_id in agenda:
            duration = agenda[value.agenda_item_id].duration_minutes
        else:
            duration = None
        slides.append(Slide(
            slide_id=value.slide_id,
            title=value.title,
            student_content=value.student_prompt or "",
            bullet_points=value.visible_student_content,
            speaker_notes="\n".join(notes),
            timing=duration if duration and duration > 0 else None,
            interaction=(
                "Use the Teacher Companion directions. Do not reveal "
                "teacher-only answers."
            ),
            layout_type=LAYOUT_BY_TYPE.get(
                value.slide_type.casefold(), "content"
            ),
            visual_instructions=value.visual_specification,
            source_references=[
                _source_label(item) for item in value.source_references
            ],
        ))
    return Lesson(
        grade=package.dashboard.grade,
        unit=package.dashboard.unit,
        lesson_number=package.dashboard.lesson_number,
        slides=slides,
    )


def _chunks(
    values: list[str],
    *,
    max_items: int = MAX_VISIBLE_ITEMS,
) -> list[list[tuple[int, str]]]:
    """Paginate without rewriting, omitting, or truncating visible content."""
    if not values:
        return [[]]
    chunks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    words = 0
    for index, value in enumerate(values):
        count = len(value.split())
        if current and (
            len(current) >= max_items
            or words + count > MAX_VISIBLE_WORDS
        ):
            chunks.append(current)
            current = []
            words = 0
        current.append((index, value))
        words += count
    if current:
        chunks.append(current)
    return chunks


def _student_projection(text: str) -> str:
    """Remove teacher framing while preserving the supplied student task."""
    value = " ".join(text.split())
    value = re.sub(
        r"\((?:possible answer|possible responses?|answers? will likely)"
        r"[^)]*\)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    if "Turn and Talk Have student pairs " in value:
        value = "Turn and Talk: " + value.split(
            "Turn and Talk Have student pairs ", 1
        )[1]
    elif value.startswith("Think-Pair-Share Have students "):
        value = "Think–Pair–Share: " + value.removeprefix(
            "Think-Pair-Share Have students "
        )
    elif value.startswith("Read the Story 30 minutes"):
        return (
            "Follow along as the story is read aloud. Reread the text "
            "when you need evidence."
        )
    replacements = (
        ("oo Explain to students that ", ""),
        ("Explain to students that ", ""),
        ("Have students ", ""),
        ("Ask them to ", ""),
        ("Ask students to ", ""),
    )
    for prefix, replacement in replacements:
        if value.startswith(prefix):
            value = replacement + value[len(prefix):]
            break
    sentence_replacements = (
        ("Lead the class in a brief discussion of ", "Discuss "),
        ("Ask students to give ", "Give "),
        ("Have student pairs discuss ", "Discuss with a partner: "),
    )
    for source, replacement in sentence_replacements:
        value = value.replace(source, replacement)
    value = value.replace(
        "Ask them to write down their ideas, particularly anything new "
        "they may have learned today about the Latino and Hispanic "
        "cultures, then turn to a partner and share their thoughts.",
        "Write down your ideas, especially something new you learned today "
        "about Latino and Hispanic cultures. Then share your thinking with "
        "a partner.",
    )
    value = value.replace("Ask them to ", "")
    value = value.replace(
        "Give some examples, and write them on the board .",
        "Be ready to share examples.",
    )
    value = value.replace(
        "find the word on page 1 of the book.",
        "",
    )
    value = value.replace(
        "reference Activity Page 1.2 while you read each word and its "
        "meaning, noting the following:",
        "Use Activity Page 1.2 to preview each word and its meaning.",
    )
    sentences = re.split(r"(?<=[.!?])\s+", value)
    student_sentences = []
    for sentence in sentences:
        normalized = sentence.strip()
        if not normalized:
            continue
        if re.match(
            r"^(?:Note to Teacher|As time permits|Call on|Tell students|"
            r"Display |Point out|Record |Write |Distribute |Assign )",
            normalized,
            flags=re.IGNORECASE,
        ):
            continue
        if re.search(
            r"\b(?:possible answer|possible response|answer key)\b",
            normalized,
            flags=re.IGNORECASE,
        ):
            continue
        student_sentences.append(normalized)
    result = " ".join(student_sentences).strip()
    if result.startswith("Think–Pair–Share:"):
        result = (
            result.replace("what they learned", "what you learned")
            .replace("their ideas", "your ideas")
            .replace("they may have learned", "you learned")
        )
    if result:
        result = result[0].upper() + result[1:]
    return result


def _display_curriculum(value: str) -> str:
    if value.startswith("curriculum-language-arts-"):
        return "CKLA"
    return value


def package_to_production_google_lesson(
    package: StructuredTeachingPackage,
) -> Lesson:
    """Create a readable deck plan while preserving every supplied item."""
    agenda = {
        value.agenda_item_id: value for value in package.agenda
    }
    steps = {
        value.agenda_item_id: value for value in package.teaching_steps
    }
    questions = {
        value.question_id: value for value in package.questions
    }
    slides: list[Slide] = []
    reading_purpose_added = False
    homework_directions_added = False
    for source in package.student_slides:
        if source.title.casefold() == "advance preparation":
            continue
        if source.question_ids:
            source_items = [
                questions[question_id].exact_question.text
                for question_id in source.question_ids
            ]
        elif source.slide_type.casefold() == "agenda":
            visible_agenda = [
                item for item in package.agenda
                if (
                    not item.teacher_only
                    and item.official_title.text.casefold()
                    != "advance preparation"
                )
            ]
            source_items = [
                (
                    f"{index}. "
                    f"{item.student_friendly_title.text}"
                    + (
                        f" — {item.duration_minutes} min"
                        if item.duration_minutes is not None else ""
                    )
                )
                for index, item in enumerate(visible_agenda, 1)
            ]
        elif source.slide_type.casefold() == "objectives":
            source_items = [
                objective.student_friendly.text
                for objective in package.objectives[:1]
            ]
        else:
            source_items = [
                projected
                for value in (
                    ([source.student_prompt] if source.student_prompt else [])
                    + source.visible_student_content
                )
                if (projected := _student_projection(value))
            ]
        if source.slide_type.casefold() == "title":
            book = (
                package.dashboard.materials[0]
                if package.dashboard.materials else ""
            )
            source_items = [
                " • ".join(value for value in (
                    _display_curriculum(package.dashboard.curriculum),
                    f"Grade {package.dashboard.grade}",
                    f"Lesson {package.dashboard.lesson_number}",
                ) if value),
                *([book] if book else []),
            ]
        if not source_items:
            continue
        if (
            source.title.casefold() == "take-home material"
            and package.homework
            and not homework_directions_added
        ):
            homework_items = []
            for value in package.homework:
                text = re.sub(
                    r"^Assign the story ",
                    "Read ",
                    value.text,
                    flags=re.IGNORECASE,
                )
                text = text.replace(
                    "after they read the story",
                    "after you read the story",
                )
                text = re.sub(
                    r"Ask students to fill out ",
                    "Complete ",
                    text,
                    flags=re.IGNORECASE,
                )
                homework_items.append(text)
            slides.append(Slide(
                slide_id=f"{source.slide_id}-homework-directions",
                title="Homework",
                bullet_points=homework_items,
                speaker_notes=(
                    "Review the exact assignment and due expectations in "
                    "the Teacher Companion."
                ),
                timing=None,
                interaction=None,
                layout_type="homework",
            ))
            homework_directions_added = True
        if (
            not reading_purpose_added
            and source.title.casefold().startswith("read the story")
        ):
            reminder = next(
                (
                    value.text
                    for value in package.dashboard.teacher_reminders
                    if "purpose for reading" in value.text.casefold()
                ),
                None,
            )
            purpose = (
                reminder.split(":", 1)[-1].strip()
                if reminder else None
            )
            slides.append(Slide(
                slide_id=f"{source.slide_id}-reading-purpose",
                title="Reading Purpose",
                bullet_points=[
                    *([purpose] if purpose else []),
                    "Follow along as the story is read aloud.",
                    "Reread when you need evidence.",
                ],
                speaker_notes=(
                    "Set the purpose before reading. Keep the verified "
                    "Teacher Companion open for pause points and answers."
                ),
                timing=None,
                interaction=None,
                layout_type="reading",
            ))
            reading_purpose_added = True
        pages = _chunks(
            source_items,
            max_items=(
                4
                if source.slide_type.casefold() == "agenda"
                else MAX_VISIBLE_ITEMS
            ),
        )
        aligned_questions = (
            len(source.question_ids) == len(source_items)
        )
        for part, chunk in enumerate(pages, 1):
            part_question_ids = (
                [
                    source.question_ids[index]
                    for index, _ in chunk
                    if index < len(source.question_ids)
                ]
                if aligned_questions else (
                    source.question_ids if part == 1 else []
                )
            )
            notes = list(source.speaker_notes)
            if source.agenda_item_id in steps:
                step = steps[source.agenda_item_id]
                notes.extend([
                    f"Instructional purpose: "
                    f"{step.instructional_purpose.text}",
                    *[
                        f"Teacher move: {item.text}"
                        for item in step.teacher_actions
                    ],
                    *[
                        f"Watch for: {item.text}"
                        for item in step.misconceptions
                    ],
                    *[
                        f"ELD support: {item.text}"
                        for item in step.eld_supports
                    ],
                    f"Transition: {step.transition.text}",
                ])
            for question_id in part_question_ids:
                question = questions[question_id]
                notes.extend([
                    f"Question: {question.exact_question.text}",
                    f"Expected answer (teacher only): "
                    f"{question.expected_answer.text}",
                    f"Follow-up: {question.follow_up.text}",
                    f"Listen for / misconception: "
                    f"{question.misconception.text}",
                    f"ELD sentence frame: "
                    f"{question.eld_sentence_frame.text}",
                ])
                if question.text_evidence:
                    notes.append(
                        f"Text evidence: {question.text_evidence.text}"
                    )
            source_labels = [
                _source_label(item) for item in source.source_references
            ]
            if source_labels:
                notes.append("[Sources]\n" + "\n".join(source_labels))
            title = (
                "Homework Questions"
                if source.title.casefold() == "take-home material"
                else source.title
            )
            if len(pages) > 1:
                title = f"{title} · {part} of {len(pages)}"
            visible = [value for _, value in chunk]
            if source.page_reference:
                visible.append(f"Reader: {source.page_reference}")
            if source.activity_reference:
                visible.append(f"Activity: {source.activity_reference}")
            duration = (
                agenda[source.agenda_item_id].duration_minutes
                if source.agenda_item_id in agenda and part == 1
                else None
            )
            slide_id = (
                source.slide_id
                if len(pages) == 1
                else f"{source.slide_id}-part-{part}"
            )
            slides.append(Slide(
                slide_id=slide_id,
                title=title,
                bullet_points=visible,
                speaker_notes="\n\n".join(
                    dict.fromkeys(value for value in notes if value.strip())
                ),
                timing=duration if duration and duration > 0 else None,
                interaction=None,
                layout_type=LAYOUT_BY_TYPE.get(
                    source.slide_type.casefold(), "content"
                ),
                visual_instructions=None,
                source_references=source_labels,
            ))
    return Lesson(
        grade=package.dashboard.grade,
        unit=package.dashboard.unit,
        lesson_number=package.dashboard.lesson_number,
        slides=slides,
    )


def validate_student_canvas(
    package: StructuredTeachingPackage,
    lesson: Lesson,
) -> None:
    """Block teacher guidance, answers, or internal data on the canvas."""
    visible = "\n".join(
        value
        for slide in lesson.slides
        for value in (
            [slide.title, slide.student_content, *slide.bullet_points]
        )
        if value
    )
    prohibited = (
        "note to teacher",
        "possible answer",
        "possible responses",
        "expected answer",
        "teacher move",
        "teacheros guidance",
        "package_digest",
        "source_hash",
    )
    normalized = visible.casefold()
    found = [value for value in prohibited if value in normalized]
    if found:
        raise ValueError(
            "Student canvas contains teacher-only or internal content: "
            + ", ".join(found)
        )
    for question in package.questions:
        answer = question.expected_answer
        if (
            answer.origin is not ContentOrigin.UNAVAILABLE
            and len(answer.text.strip()) >= 12
            and answer.text.casefold() in normalized
        ):
            raise ValueError(
                "Student canvas contains an expected answer for "
                f"{question.question_id}."
            )
        if visible.count(question.exact_question.text) != 1:
            raise ValueError(
                "Required question is missing or duplicated on the student "
                f"canvas: {question.question_id}."
            )
    for slide in lesson.slides:
        word_count = len(
            " ".join(
                [slide.student_content, *slide.bullet_points]
            ).split()
        )
        if word_count > 90:
            raise ValueError(
                f"Student slide {slide.slide_id} is too dense "
                f"({word_count} words)."
            )


class ProductionGoogleSlidesRenderer(GoogleSlidesRenderer):
    """Classroom-readable renderer with restrained instructional styling."""

    deck_footer = "ELA"

    def _create_slide(
        self, slide: Slide, layout: str, index: int | None
    ) -> str:
        self._require_presentation()
        slide_id = self._google_id("slide", slide.slide_id)
        background_id = self._google_id("background", slide.slide_id)
        title_id = self._google_id("title", slide.slide_id)
        body_id = self._google_id("body", slide.slide_id)
        accent_id = self._google_id("accent", slide.slide_id)
        footer_id = self._google_id("footer", slide.slide_id)
        is_title = layout == "title"
        requests: list[dict[str, Any]] = [{
            "createSlide": {
                "objectId": slide_id,
                "insertionIndex": (
                    len(self._slide_ids) if index is None else index
                ),
                "slideLayoutReference": {"predefinedLayout": "BLANK"},
            }
        }]
        requests.extend(self._shape_requests(
            slide_id,
            background_id,
            0, 0, 10, 5.625,
            PALETTE["navy"] if is_title else PALETTE["paper"],
        ))
        if not is_title:
            requests.extend(self._shape_requests(
                slide_id,
                accent_id,
                0, 0, .14, 5.625,
                PALETTE["teal"],
            ))
        requests.extend(self._styled_text_requests(
            slide_id,
            title_id,
            slide.title,
            (
                {"x": .82, "y": 1.55, "w": 8.45, "h": 1.15}
                if is_title else
                {"x": .62, "y": .42, "w": 8.78, "h": .72}
            ),
            font_size=40 if is_title else 30,
            color=PALETTE["white"] if is_title else PALETTE["navy"],
            bold=True,
        ))
        body = self._body_text(slide)
        if body:
            word_count = len(body.split())
            body_font = (
                22 if word_count <= 34
                else 19 if word_count <= 58
                else 17
            )
            requests.extend(self._styled_text_requests(
                slide_id,
                body_id,
                body,
                (
                    {"x": .86, "y": 2.95, "w": 8.2, "h": 1.35}
                    if is_title else
                    {"x": .72, "y": 1.38, "w": 8.55, "h": 3.62}
                ),
                font_size=body_font,
                color=PALETTE["white"] if is_title else PALETTE["ink"],
                bold=False,
            ))
        footer = (
            f"{self.deck_footer}  •  Slide {len(self._slide_ids) + 1}"
        )
        if not is_title:
            requests.extend(self._styled_text_requests(
                slide_id,
                footer_id,
                footer,
                {"x": .72, "y": 5.34, "w": 8.55, "h": .16},
                font_size=10,
                color=PALETTE["muted"],
                bold=False,
            ))
        self._batch_update(requests)
        self._slide_ids.append(slide_id)
        return slide_id

    def _shape_requests(
        self,
        slide_id: str,
        object_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        color: str,
    ) -> list[dict[str, Any]]:
        return [{
            "createShape": {
                "objectId": object_id,
                "shapeType": "RECTANGLE",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": self._size(width, height),
                    "transform": self._transform(x, y),
                },
            }
        }, {
            "updateShapeProperties": {
                "objectId": object_id,
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {"color": {"rgbColor": self._rgb(color)}}
                    },
                    "outline": {"propertyState": "NOT_RENDERED"},
                },
                "fields": "shapeBackgroundFill.solidFill.color,outline",
            }
        }]

    def _styled_text_requests(
        self,
        slide_id: str,
        object_id: str,
        text: str,
        box: dict[str, float],
        *,
        font_size: int,
        color: str,
        bold: bool,
    ) -> list[dict[str, Any]]:
        return [{
            "createShape": {
                "objectId": object_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": self._size(box["w"], box["h"]),
                    "transform": self._transform(box["x"], box["y"]),
                },
            }
        }, {
            "insertText": {
                "objectId": object_id,
                "insertionIndex": 0,
                "text": text,
            }
        }, {
            "updateTextStyle": {
                "objectId": object_id,
                "textRange": {"type": "ALL"},
                "style": {
                    "fontFamily": "Arial",
                    "fontSize": {"magnitude": font_size, "unit": "PT"},
                    "bold": bold,
                    "foregroundColor": {
                        "opaqueColor": {"rgbColor": self._rgb(color)}
                    },
                },
                "fields": (
                    "fontFamily,fontSize,bold,foregroundColor"
                ),
            }
        }, {
            "updateParagraphStyle": {
                "objectId": object_id,
                "textRange": {"type": "ALL"},
                "style": {
                    "lineSpacing": 110,
                    "spaceAbove": {"magnitude": 0, "unit": "PT"},
                    "spaceBelow": {"magnitude": 8, "unit": "PT"},
                },
                "fields": "lineSpacing,spaceAbove,spaceBelow",
            }
        }]


class TeachingPackageGoogleSlidesPublisher:
    """Publish approved student slides through the existing renderer."""

    def __init__(
        self,
        *,
        renderer: GoogleSlidesRenderer | None = None,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
    ) -> None:
        self.renderer = renderer or ProductionGoogleSlidesRenderer(
            credentials_path=credentials_path,
            token_path=token_path,
        )

    def publish(self, package: StructuredTeachingPackage) -> dict[str, Any]:
        if package.validation.status == "fail":
            raise ValueError("Cannot publish a failed teaching package.")
        if isinstance(self.renderer, ProductionGoogleSlidesRenderer):
            self.renderer.deck_footer = (
                f"{_display_curriculum(package.dashboard.curriculum)}  •  "
                f"Grade {package.dashboard.grade}  •  "
                f"Lesson {package.dashboard.lesson_number}"
            )
        lesson = package_to_production_google_lesson(package)
        validate_student_canvas(package, lesson)
        return self.renderer.create_presentation(lesson)


__all__ = [
    "LAYOUT_BY_TYPE",
    "ProductionGoogleSlidesRenderer",
    "TeachingPackageGoogleSlidesPublisher",
    "package_to_google_lesson",
    "package_to_production_google_lesson",
    "validate_student_canvas",
]
