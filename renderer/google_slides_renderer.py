"""Render validated TeacherOS lessons as editable Google Slides decks."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from schemas.lesson_schema import Lesson, Slide


class GoogleSlidesRenderer:
    """Deterministically map validated lesson fields to Google Slides API calls."""

    SCOPES = (
        "https://www.googleapis.com/auth/presentations",
        "https://www.googleapis.com/auth/drive.file",
    )
    SUPPORTED_LAYOUTS = {
        "title", "title-slide", "content", "title-and-content", "vocabulary",
        "activity", "discussion", "assessment", "objective", "agenda",
        "background knowledge", "instructions", "reading", "check for understanding",
        "writing", "homework", "closure", "day divider",
    }
    MIME_TYPES = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pdf": "application/pdf",
    }

    def __init__(self, credentials_path: str | os.PathLike[str] = "credentials.json",
                 token_path: str | os.PathLike[str] = "token.json", *,
                 slides_service: Any | None = None, drive_service: Any | None = None,
                 credentials: Credentials | None = None,
                 service_builder: Callable[..., Any] = build) -> None:
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.credentials = credentials
        self.slides_service = slides_service
        self.drive_service = drive_service
        self._service_builder = service_builder
        self.presentation_id: str | None = None
        self._slide_ids: list[str] = []

    def authenticate(self) -> Credentials:
        """Run desktop OAuth when necessary and initialize Slides and Drive clients."""
        credentials = self.credentials
        if credentials is None and self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(f"OAuth client file not found: {self.credentials_path}")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), self.SCOPES)
                credentials = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        self.credentials = credentials
        if self.slides_service is None:
            self.slides_service = self._service_builder("slides", "v1", credentials=credentials, cache_discovery=False)
        if self.drive_service is None:
            self.drive_service = self._service_builder("drive", "v3", credentials=credentials, cache_discovery=False)
        return credentials

    def create_presentation(self, lesson: Lesson) -> dict[str, Any]:
        """Create and fully render one widescreen presentation in lesson order."""
        self._validate_lesson(lesson)
        self._ensure_services()
        title = f"{lesson.unit} — Lesson {lesson.lesson_number} (Grade {lesson.grade})"
        created = self.slides_service.presentations().create(body={
            "title": title,
            "pageSize": {
                "width": {"magnitude": 12_192_000, "unit": "EMU"},
                "height": {"magnitude": 6_858_000, "unit": "EMU"},
            },
        }).execute()
        self.presentation_id = created["presentationId"]
        self._slide_ids = []
        if created.get("slides"):
            self._batch_update([{"deleteObject": {"objectId": item["objectId"]}} for item in created["slides"]])
        for index, slide in enumerate(lesson.slides):
            self._render_slide(slide, index)
        return {"presentationId": self.presentation_id,
                "url": f"https://docs.google.com/presentation/d/{self.presentation_id}/edit",
                "slideIds": list(self._slide_ids)}

    def create_title_slide(self, slide: Slide, index: int | None = None) -> str:
        return self._create_slide(slide, "title", index)

    def create_content_slide(self, slide: Slide, index: int | None = None) -> str:
        return self._create_slide(slide, "content", index)

    def create_vocabulary_slide(self, slide: Slide, index: int | None = None) -> str:
        return self._create_slide(slide, "vocabulary", index)

    def create_activity_slide(self, slide: Slide, index: int | None = None) -> str:
        return self._create_slide(slide, "activity", index)

    def create_discussion_slide(self, slide: Slide, index: int | None = None) -> str:
        return self._create_slide(slide, "discussion", index)

    def create_assessment_slide(self, slide: Slide, index: int | None = None) -> str:
        return self._create_slide(slide, "assessment", index)

    def add_speaker_notes(self, slide_id: str, slide: Slide) -> None:
        """Put all available teacher metadata in the slide's notes page."""
        presentation = self.slides_service.presentations().get(presentationId=self.presentation_id).execute()
        api_slide = next((item for item in presentation.get("slides", []) if item["objectId"] == slide_id), None)
        if api_slide is None:
            raise ValueError(f"Google Slides response did not contain slide {slide_id!r}")
        notes_id = api_slide["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
        self._batch_update([
            {"insertText": {"objectId": notes_id, "insertionIndex": 0,
                            "text": self._format_speaker_notes(slide)}},
        ])

    def apply_layout(self, slide: Slide, layout: str | None = None) -> dict[str, Any]:
        """Return fixed geometry and typography for a supported layout."""
        selected = (layout or slide.layout_type).strip().lower().replace("_", "-")
        if selected not in self.SUPPORTED_LAYOUTS:
            raise ValueError(f"Unsupported slide layout: {slide.layout_type!r}")
        is_title = selected in {"title", "title-slide"}
        return {
            "layout": selected,
            "title": {"x": 685_800, "y": 1_500_000 if is_title else 480_000,
                      "w": 10_820_400, "h": 1_250_000 if is_title else 760_000,
                      "font": 30 if is_title else 24},
            "body": {"x": 914_400, "y": 3_000_000 if is_title else 1_500_000,
                     "w": 10_363_200, "h": 2_650_000 if is_title else 4_650_000,
                     "font": self._body_font_size(self._body_text(slide))},
        }

    def export(self, presentation: Any = None,
               destination: str | os.PathLike[str] | None = None) -> Path:
        """Export the current deck through Drive as ``.pptx`` or ``.pdf``."""
        self._ensure_services()
        presentation_id = self._presentation_id_from(presentation)
        if destination is None:
            raise ValueError("An export destination is required")
        path = Path(destination)
        mime_type = self.MIME_TYPES.get(path.suffix.lower())
        if mime_type is None:
            raise ValueError("Export destination must end in .pptx or .pdf")
        path.parent.mkdir(parents=True, exist_ok=True)
        request = self.drive_service.files().export_media(fileId=presentation_id, mimeType=mime_type)
        with path.open("wb") as stream:
            downloader = MediaIoBaseDownload(stream, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return path

    def _render_slide(self, slide: Slide, index: int) -> str:
        layout = slide.layout_type.strip().lower().replace("_", "-")
        dispatch = {
            "title": self.create_title_slide, "title-slide": self.create_title_slide,
            "day divider": self.create_title_slide,
            "content": self.create_content_slide, "title-and-content": self.create_content_slide,
            "objective": self.create_content_slide, "agenda": self.create_content_slide,
            "background knowledge": self.create_content_slide,
            "instructions": self.create_content_slide, "reading": self.create_content_slide,
            "check for understanding": self.create_content_slide,
            "writing": self.create_content_slide, "homework": self.create_content_slide,
            "closure": self.create_content_slide,
            "vocabulary": self.create_vocabulary_slide, "activity": self.create_activity_slide,
            "discussion": self.create_discussion_slide, "assessment": self.create_assessment_slide,
        }
        try:
            slide_id = dispatch[layout](slide, index)
        except KeyError as exc:
            raise ValueError(f"Unsupported slide layout: {slide.layout_type!r}") from exc
        self.add_speaker_notes(slide_id, slide)
        return slide_id

    def _create_slide(self, slide: Slide, layout: str, index: int | None) -> str:
        self._require_presentation()
        geometry = self.apply_layout(slide, layout)
        slide_id = self._google_id("slide", slide.slide_id)
        title_id = self._google_id("title", slide.slide_id)
        body_id = self._google_id("body", slide.slide_id)
        requests: list[dict[str, Any]] = [{"createSlide": {
            "objectId": slide_id, "insertionIndex": len(self._slide_ids) if index is None else index,
            "slideLayoutReference": {"predefinedLayout": "BLANK"}}}]
        requests.extend(self._text_box_requests(slide_id, title_id, slide.title, geometry["title"], True))
        body = self._body_text(slide)
        if body:
            requests.extend(self._text_box_requests(slide_id, body_id, body, geometry["body"], False))
        self._batch_update(requests)
        self._slide_ids.append(slide_id)
        return slide_id

    def _text_box_requests(self, slide_id: str, object_id: str, text: str,
                           box: dict[str, Any], title: bool) -> list[dict[str, Any]]:
        return [
            {"createShape": {"objectId": object_id, "shapeType": "TEXT_BOX",
             "elementProperties": {"pageObjectId": slide_id,
               "size": {"width": {"magnitude": box["w"], "unit": "EMU"},
                        "height": {"magnitude": box["h"], "unit": "EMU"}},
               "transform": {"scaleX": 1, "scaleY": 1, "translateX": box["x"],
                             "translateY": box["y"], "unit": "EMU"}}}},
            {"insertText": {"objectId": object_id, "insertionIndex": 0, "text": text}},
            {"updateTextStyle": {"objectId": object_id, "textRange": {"type": "ALL"},
              "style": {"fontFamily": "Arial", "fontSize": {"magnitude": box["font"], "unit": "PT"},
                        "bold": title, "foregroundColor": {"opaqueColor": {"rgbColor":
                        {"red": 0.11, "green": 0.20, "blue": 0.32}}}},
              "fields": "fontFamily,fontSize,bold,foregroundColor"}},
        ]

    @staticmethod
    def _body_text(slide: Slide) -> str:
        parts = [slide.student_content.strip()]
        parts.extend(f"• {point.strip()}" for point in slide.bullet_points if point.strip())
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _body_font_size(text: str) -> int:
        if len(text) > 1_200: return 12
        if len(text) > 750: return 14
        if len(text) > 400: return 16
        return 20

    @staticmethod
    def _format_speaker_notes(slide: Slide) -> str:
        notes = [
            f"Teacher notes: {slide.speaker_notes.strip()}",
            f"Timing: {f'{slide.timing} minutes' if slide.timing else ''}",
            f"Teacher directions: {(slide.interaction or '').strip()}",
            f"Materials: {(slide.visual_instructions or '').strip()}",
            f"Layout type: {slide.layout_type}",
        ]
        if slide.image_prompt:
            notes.append(f"Image prompt: {slide.image_prompt.strip()}")
        if slide.source_references:
            notes.append("Source references: " + " | ".join(slide.source_references))
        return "\n".join(notes)

    @staticmethod
    def _google_id(prefix: str, source_id: str) -> str:
        return f"tos_{prefix}_{hashlib.sha1(source_id.encode('utf-8')).hexdigest()[:16]}"

    def _batch_update(self, requests: list[dict[str, Any]]) -> Any:
        if not requests: return None
        return self.slides_service.presentations().batchUpdate(
            presentationId=self.presentation_id, body={"requests": requests}).execute()

    def _validate_lesson(self, lesson: Lesson) -> None:
        if not isinstance(lesson, Lesson):
            raise TypeError("lesson must be a validated Lesson object")
        ids = [slide.slide_id for slide in lesson.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("slide_id values must be unique within a lesson")
        for slide in lesson.slides:
            self.apply_layout(slide)

    def _ensure_services(self) -> None:
        if self.slides_service is None or self.drive_service is None:
            self.authenticate()

    def _require_presentation(self) -> None:
        if not self.presentation_id:
            raise RuntimeError("create_presentation must be called before adding slides")

    def _presentation_id_from(self, presentation: Any) -> str:
        if isinstance(presentation, str): return presentation
        if isinstance(presentation, dict) and presentation.get("presentationId"):
            return presentation["presentationId"]
        if self.presentation_id: return self.presentation_id
        raise ValueError("No presentation ID is available for export")
