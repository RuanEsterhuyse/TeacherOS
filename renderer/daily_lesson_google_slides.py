"""Opt-in Google Slides publishing for saved Daily Lesson packages."""

from __future__ import annotations

import os
from typing import Any

from googleapiclient.errors import HttpError

from renderer.daily_lesson_markdown import format_reference
from renderer.google_slides_renderer import GoogleSlidesRenderer
from schemas.daily_lesson_schema import (
    DailyLessonPackage,
    DailySlideOutlineItem,
    DailySpeakerNotes,
)


DAILY_GOOGLE_DRIVE_FOLDER_ENV = "TEACHEROS_DAILY_GOOGLE_DRIVE_FOLDER_ID"
DAILY_SLIDES_COLORS = {
    "background": "#F7F4EE",
    "aqua": "#67C7D8",
    "teal": "#3B97A8",
    "coral": "#E97F7C",
    "text": "#2E2E2E",
    "white": "#FFFFFF",
}
DAILY_SLIDES_LAYOUTS = {
    "title_slide",
    "title_and_bullets",
    "two_column",
    "discussion_question",
    "vocabulary",
    "exit_ticket",
}


class DailyLessonGoogleSlidesRenderer(GoogleSlidesRenderer):
    """Render one saved Daily Slide Outline without regenerating content."""

    def __init__(
        self,
        *args,
        drive_folder_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.drive_folder_id = (
            drive_folder_id
            if drive_folder_id is not None
            else os.getenv(DAILY_GOOGLE_DRIVE_FOLDER_ENV, "")
        ).strip() or None

    @staticmethod
    def resolve_layout(slide: DailySlideOutlineItem) -> tuple[str, str | None]:
        raw = slide.suggested_layout.strip().casefold()
        normalized = "_".join(part for part in raw.replace("-", " ").split())
        if normalized in DAILY_SLIDES_LAYOUTS:
            return normalized, None
        if "vocab" in normalized:
            return "vocabulary", None
        if "exit" in normalized or "reflection" in normalized:
            return "exit_ticket", None
        if "two" in normalized and "column" in normalized:
            return "two_column", None
        if "balanced" in normalized and ("area" in normalized or "column" in normalized):
            return "two_column", None
        if any(value in normalized for value in (
            "discussion", "question", "turn_and_talk", "prompt"
        )):
            return "discussion_question", None
        if any(value in normalized for value in (
            "bullet", "agenda", "objective", "steps", "activity", "list"
        )):
            return "title_and_bullets", None
        if any(value in normalized for value in ("title", "opening", "hero")):
            return "title_slide", None
        warning = (
            f"Slide {slide.slide_number} layout "
            f"{slide.suggested_layout!r} is unsupported; "
            "used title_and_bullets."
        )
        return "title_and_bullets", warning

    @staticmethod
    def _box(
        slide_id: str,
        object_id: str,
        *,
        shape_type: str,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: str | None = None,
    ) -> dict[str, Any]:
        return {
            "createShape": {
                "objectId": object_id,
                "shapeType": shape_type,
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width": {
                            "magnitude": round(width * 914_400),
                            "unit": "EMU",
                        },
                        "height": {
                            "magnitude": round(height * 914_400),
                            "unit": "EMU",
                        },
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": round(x * 914_400),
                        "translateY": round(y * 914_400),
                        "unit": "EMU",
                    },
                },
            }
        }

    @classmethod
    def _fill_request(
        cls, object_id: str, fill: str
    ) -> dict[str, Any]:
        return {
            "updateShapeProperties": {
                "objectId": object_id,
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {
                            "color": {
                                "rgbColor": cls._rgb(fill)
                            }
                        }
                    },
                    "outline": {"propertyState": "NOT_RENDERED"},
                },
                "fields": "shapeBackgroundFill,outline",
            }
        }

    @classmethod
    def _text_requests(
        cls,
        slide_id: str,
        object_id: str,
        text: str,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        font_size: int,
        bold: bool = False,
        color: str = DAILY_SLIDES_COLORS["text"],
        shape_type: str = "TEXT_BOX",
        fill: str | None = None,
    ) -> list[dict[str, Any]]:
        if not text.strip():
            return []
        requests = [
            cls._box(
                slide_id,
                object_id,
                shape_type=shape_type,
                x=x,
                y=y,
                width=width,
                height=height,
                fill=fill,
            ),
        ]
        if fill:
            requests.append(cls._fill_request(object_id, fill))
        requests.extend([
            {
                "insertText": {
                    "objectId": object_id,
                    "insertionIndex": 0,
                    "text": text,
                }
            },
            {
                "updateTextStyle": {
                    "objectId": object_id,
                    "textRange": {"type": "ALL"},
                    "style": {
                        "fontFamily": "Arial",
                        "fontSize": {
                            "magnitude": font_size,
                            "unit": "PT",
                        },
                        "bold": bold,
                        "foregroundColor": {
                            "opaqueColor": {
                                "rgbColor": cls._rgb(color)
                            }
                        },
                    },
                    "fields": (
                        "fontFamily,fontSize,bold,foregroundColor"
                    ),
                }
            },
            {
                "updateParagraphStyle": {
                    "objectId": object_id,
                    "textRange": {"type": "ALL"},
                    "style": {
                        "lineSpacing": 112,
                        "spaceBelow": {
                            "magnitude": 8,
                            "unit": "PT",
                        },
                    },
                    "fields": "lineSpacing,spaceBelow",
                }
            },
        ])
        return requests

    @classmethod
    def _slide_requests(
        cls,
        slide: DailySlideOutlineItem,
        layout: str,
    ) -> list[dict[str, Any]]:
        slide_id = cls._google_id("daily_slide", str(slide.slide_number))
        requests: list[dict[str, Any]] = [{
            "createSlide": {
                "objectId": slide_id,
                "insertionIndex": slide.slide_number - 1,
                "slideLayoutReference": {"predefinedLayout": "BLANK"},
            }
        }, {
            "updatePageProperties": {
                "objectId": slide_id,
                "pageProperties": {
                    "pageBackgroundFill": {
                        "solidFill": {
                            "color": {
                                "rgbColor": cls._rgb(
                                    DAILY_SLIDES_COLORS["background"]
                                )
                            }
                        }
                    }
                },
                "fields": "pageBackgroundFill",
            }
        }]
        title_size = 50 if layout == "title_slide" else 35
        title_y = 1.35 if layout == "title_slide" else 0.48
        requests.extend(cls._text_requests(
            slide_id,
            cls._google_id("daily_title", str(slide.slide_number)),
            slide.title,
            x=0.75,
            y=title_y,
            width=11.8,
            height=1.1,
            font_size=title_size,
            bold=True,
            color=DAILY_SLIDES_COLORS["teal"],
        ))
        lines = list(slide.exact_student_facing_text)
        if layout == "title_slide":
            body = "\n".join(lines[:2])
            requests.extend(cls._text_requests(
                slide_id,
                cls._google_id("daily_body", str(slide.slide_number)),
                body,
                x=1.3,
                y=3.0,
                width=10.7,
                height=2.1,
                font_size=24,
            ))
        elif layout == "two_column":
            midpoint = max(1, (len(lines) + 1) // 2)
            for role, x, values in (
                ("left", 0.75, lines[:midpoint]),
                ("right", 6.85, lines[midpoint:]),
            ):
                requests.extend(cls._text_requests(
                    slide_id,
                    cls._google_id(
                        f"daily_{role}", str(slide.slide_number)
                    ),
                    "\n".join(f"• {value}" for value in values),
                    x=x,
                    y=1.65,
                    width=5.7,
                    height=4.75,
                    font_size=21,
                    shape_type="ROUND_RECTANGLE",
                    fill=DAILY_SLIDES_COLORS["white"],
                ))
        else:
            body = (
                "\n".join(f"• {value}" for value in lines)
                if layout in {
                    "title_and_bullets", "vocabulary", "exit_ticket"
                }
                else "\n".join(lines)
            )
            accent = (
                DAILY_SLIDES_COLORS["coral"]
                if layout == "exit_ticket"
                else DAILY_SLIDES_COLORS["aqua"]
            )
            accent_id = cls._google_id(
                "daily_accent", str(slide.slide_number)
            )
            requests.extend([
                cls._box(
                    slide_id,
                    accent_id,
                    shape_type="RECTANGLE",
                    x=0.75,
                    y=1.62,
                    width=1.1,
                    height=0.12,
                ),
                cls._fill_request(accent_id, accent),
            ])
            requests.extend(cls._text_requests(
                slide_id,
                cls._google_id("daily_body", str(slide.slide_number)),
                body,
                x=0.95,
                y=1.82,
                width=11.4,
                height=4.65,
                font_size=24 if layout == "discussion_question" else 21,
                bold=layout == "discussion_question",
                shape_type="ROUND_RECTANGLE",
                fill=DAILY_SLIDES_COLORS["white"],
            ))
        if slide.suggested_visual:
            requests.extend(cls._text_requests(
                slide_id,
                cls._google_id("daily_visual", str(slide.slide_number)),
                "Editable visual placeholder",
                x=9.5,
                y=6.58,
                width=2.8,
                height=0.5,
                font_size=16,
                color=DAILY_SLIDES_COLORS["teal"],
            ))
        return requests

    @staticmethod
    def _speaker_notes(slide: DailySlideOutlineItem) -> str:
        notes = slide.speaker_notes
        sections = [
            ("Instructional purpose", [slide.instructional_purpose]),
            ("Teacher says", notes.teacher_says),
            ("Teacher does", notes.teacher_does),
            ("Discussion prompts", notes.discussion_prompts),
            ("Anticipated responses", notes.anticipated_responses),
            ("Likely misconceptions", notes.misconception_support),
            ("Checks for understanding", notes.checks_for_understanding),
        ]
        output = []
        if notes.timing_minutes is not None:
            output.append(f"Pacing\n{notes.timing_minutes} minutes")
        for heading, values in sections:
            if values:
                output.append(
                    heading + "\n"
                    + "\n".join(f"• {value}" for value in values)
                )
        if notes.transition:
            output.append(f"Transition\n{notes.transition}")
        references = []
        seen = set()
        for reference in (
            slide.source_references + notes.source_references
        ):
            key = (
                reference.source_type,
                reference.page_start,
                reference.page_end,
                reference.section,
                reference.activity_reference,
            )
            if key not in seen:
                seen.add(key)
                references.append(reference)
        if references:
            output.append(
                "Supported source references\n"
                + "\n".join(
                    f"• {format_reference(reference)}"
                    for reference in references
                )
            )
        return "\n\n".join(output)

    def _move_to_folder(self, presentation_id: str) -> None:
        if not self.drive_folder_id:
            return
        current = self.drive_service.files().get(
            fileId=presentation_id,
            fields="parents",
        ).execute()
        parents = ",".join(current.get("parents", []))
        self.drive_service.files().update(
            fileId=presentation_id,
            addParents=self.drive_folder_id,
            removeParents=parents or None,
            fields="id,parents",
        ).execute()

    def _cleanup(self, presentation_id: str) -> None:
        try:
            self.drive_service.files().delete(
                fileId=presentation_id
            ).execute()
        except Exception:
            pass

    def create_daily_presentation(
        self,
        package: DailyLessonPackage,
    ) -> dict[str, Any]:
        if not package.slide_outline:
            raise ValueError(
                "The saved daily package has no slide outline."
            )
        self._ensure_services()
        title = (
            f"{package.source_identity.lesson_title} — "
            f"Lesson {package.source_identity.lesson_number}"
        )
        presentation_id = None
        warnings = []
        stage = "Slides"
        try:
            created = self.slides_service.presentations().create(body={
                "title": title,
                "pageSize": {
                    "width": {
                        "magnitude": 12_192_000,
                        "unit": "EMU",
                    },
                    "height": {
                        "magnitude": 6_858_000,
                        "unit": "EMU",
                    },
                },
            }).execute()
            presentation_id = created["presentationId"]
            self.presentation_id = presentation_id
            requests = [
                {"deleteObject": {"objectId": value["objectId"]}}
                for value in created.get("slides", [])
            ]
            layouts = []
            for slide in package.slide_outline:
                layout, warning = self.resolve_layout(slide)
                layouts.append(layout)
                if warning:
                    warnings.append(warning)
                requests.extend(self._slide_requests(slide, layout))
            self._batch_update(requests)
            stage = "speaker-notes"
            rendered = self.slides_service.presentations().get(
                presentationId=presentation_id
            ).execute()
            note_ids = {
                value["objectId"]: value["slideProperties"]["notesPage"][
                    "notesProperties"
                ]["speakerNotesObjectId"]
                for value in rendered.get("slides", [])
            }
            note_requests = []
            for slide in package.slide_outline:
                slide_id = self._google_id(
                    "daily_slide", str(slide.slide_number)
                )
                if slide_id not in note_ids:
                    raise ValueError(
                        f"Google Slides did not return speaker notes for "
                        f"slide {slide.slide_number}."
                    )
                notes = self._speaker_notes(slide)
                if notes:
                    note_requests.append({
                        "insertText": {
                            "objectId": note_ids[slide_id],
                            "insertionIndex": 0,
                            "text": notes,
                        }
                    })
            self._batch_update(note_requests)
            stage = "Drive"
            self._move_to_folder(presentation_id)
        except HttpError as error:
            if presentation_id:
                self._cleanup(presentation_id)
            raise ValueError(
                f"Google {stage} API failed while creating the deck."
            ) from error
        except Exception:
            if presentation_id:
                self._cleanup(presentation_id)
            raise
        return {
            "status": "created",
            "presentation_id": presentation_id,
            "presentation_url": (
                f"https://docs.google.com/presentation/d/"
                f"{presentation_id}/edit"
            ),
            "title": title,
            "slide_count": len(package.slide_outline),
            "warnings": warnings,
        }


__all__ = [
    "DAILY_GOOGLE_DRIVE_FOLDER_ENV",
    "DAILY_SLIDES_COLORS",
    "DAILY_SLIDES_LAYOUTS",
    "DailyLessonGoogleSlidesRenderer",
]
