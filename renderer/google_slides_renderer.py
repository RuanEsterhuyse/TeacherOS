"""Render validated TeacherOS lessons as editable Google Slides decks."""

from __future__ import annotations

import hashlib
import re
import os
from pathlib import Path
from typing import Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from schemas.lesson_schema import Lesson, Slide
from schemas.presentation_design_schema import PresentationDesignOutput, PresentationSlide
from renderer.presentation_theme import load_presentation_theme, load_visual_theme
from schemas.lesson_package_schema import CKLA_ATTRIBUTION
from brain.presentation_expander import expand_presentation
from brain.visual_storyboard import build_visual_storyboard, evaluate_visual_quality


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
    RICH_LAYOUTS = {"title_hero", "day_divider", "split_visual", "question_focus", "quote_focus",
        "map_focus", "vocabulary_cards", "three_card", "reading_checkpoint", "discussion_prompt",
        "activity_steps", "comparison", "evidence_chart", "exit_ticket", "minimal_text", "no_visual",
        "title_slide", "objective_agenda", "vocabulary_visual", "image_and_prompt", "text_and_image",
        "turn_and_talk", "sentence_frame", "read_aloud", "quote_analysis", "evidence_analysis",
        "progressive_grouping", "homework", "two_column", "full_visual", "simple_directions"}
    MIME_TYPES = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pdf": "application/pdf",
    }

    def __init__(self, credentials_path: str | os.PathLike[str] = "credentials.json",
                 token_path: str | os.PathLike[str] = "token.json", *,
                 slides_service: Any | None = None, drive_service: Any | None = None,
                 credentials: Credentials | None = None,
                 service_builder: Callable[..., Any] = build,
                 theme_path: str | os.PathLike[str] | None = None,
                 project_root: str | os.PathLike[str] | None = None,
                 development_mode: bool = False) -> None:
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.credentials = credentials
        self.slides_service = slides_service
        self.drive_service = drive_service
        self._service_builder = service_builder
        self.presentation_id: str | None = None
        self._slide_ids: list[str] = []
        self.theme = load_presentation_theme(theme_path)
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.development_mode = development_mode
        self.warnings: list[dict[str, str]] = []
        self._rich_attribution_slide_id: str | None = None
        self._storyboard_by_id = {}

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

    def create_presentation(self, lesson: Lesson | PresentationDesignOutput) -> dict[str, Any]:
        """Create and fully render one widescreen presentation in lesson order."""
        if isinstance(lesson, PresentationDesignOutput):
            return self.create_rich_presentation(lesson)
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

    def create_rich_presentation(self, presentation: PresentationDesignOutput) -> dict[str, Any]:
        """Render Presentation Designer output without passing through the legacy package."""
        presentation = expand_presentation(presentation)
        selected_theme = presentation.theme if presentation.theme in {"modern_middle_school","warm_humanities","clean_academic"} else "warm_humanities"
        visual_theme = load_visual_theme(selected_theme)
        self.theme["colors"].update({k: visual_theme[k] for k in ("primary","secondary","accent","background")})
        self.theme["typography"].update({"title_font":visual_theme["heading_font"],"body_font":visual_theme["body_font"]})
        board = build_visual_storyboard(presentation, selected_theme)
        self._storyboard_by_id = {slide.slide_id: slide for slide in board.slides}
        self._validate_presentation(presentation)
        self._ensure_services()
        dims = self.theme["dimensions"]
        created = self.slides_service.presentations().create(body={
            "title": presentation.lesson_title or presentation.request_id,
            "pageSize": {"width": {"magnitude": self._emu(dims["width_inches"]), "unit": "EMU"},
                         "height": {"magnitude": self._emu(dims["height_inches"]), "unit": "EMU"}},
        }).execute()
        self.presentation_id = created["presentationId"]
        self._slide_ids = []
        self.warnings = []
        for finding in evaluate_visual_quality(board):
            self.warnings.append({"slide_id":"deck","code":"visual_quality","message":finding})
        self._rich_attribution_slide_id = presentation.slides[-1].slide_id if (
            presentation.slides and presentation.request_id.lower().startswith("ckla-")) else None
        if created.get("slides"):
            self._batch_update([{"deleteObject": {"objectId": item["objectId"]}} for item in created["slides"]])
        for index, slide in enumerate(presentation.slides):
            self.render_slide(slide, index)
        return {"presentationId": self.presentation_id,
                "url": f"https://docs.google.com/presentation/d/{self.presentation_id}/edit",
                "slideIds": list(self._slide_ids), "warnings": list(self.warnings)}

    def render_slide(self, slide: PresentationSlide, index: int | None = None) -> str:
        """Dispatch one rich slide to a controlled semantic layout renderer."""
        layout = slide.design.layout.value
        renderer = getattr(self, f"render_{layout}", None)
        if renderer is None:
            raise ValueError(f"Unsupported rich slide layout: {layout!r}")
        self._validate_rich_slide(slide)
        slide_id = renderer(slide, index)
        self.add_rich_speaker_notes(slide_id, slide)
        return slide_id

    def render_title_hero(self, slide, index=None): return self._render_rich(slide, index, "hero")
    def render_day_divider(self, slide, index=None): return self._render_rich(slide, index, "divider")
    def render_split_visual(self, slide, index=None): return self._render_rich(slide, index, "split")
    def render_question_focus(self, slide, index=None): return self._render_rich(slide, index, "question")
    def render_quote_focus(self, slide, index=None): return self._render_rich(slide, index, "quote")
    def render_map_focus(self, slide, index=None): return self._render_rich(slide, index, "visual_primary")
    def render_vocabulary_cards(self, slide, index=None): return self._render_rich(slide, index, "cards")
    def render_three_card(self, slide, index=None): return self._render_rich(slide, index, "cards")
    def render_reading_checkpoint(self, slide, index=None): return self._render_rich(slide, index, "checkpoint")
    def render_discussion_prompt(self, slide, index=None): return self._render_rich(slide, index, "question")
    def render_activity_steps(self, slide, index=None): return self._render_rich(slide, index, "steps")
    def render_comparison(self, slide, index=None): return self._render_rich(slide, index, "columns")
    def render_evidence_chart(self, slide, index=None): return self._render_rich(slide, index, "columns")
    def render_exit_ticket(self, slide, index=None): return self._render_rich(slide, index, "exit")
    def render_minimal_text(self, slide, index=None): return self._render_rich(slide, index, "minimal")
    def render_no_visual(self, slide, index=None): return self._render_rich(slide, index, "text")
    def render_title_slide(self, slide, index=None): return self._render_rich(slide, index, "hero")
    def render_objective_agenda(self, slide, index=None): return self._render_rich(slide, index, "steps")
    def render_vocabulary_visual(self, slide, index=None): return self._render_rich(slide, index, "split")
    def render_image_and_prompt(self, slide, index=None): return self._render_rich(slide, index, "split")
    def render_text_and_image(self, slide, index=None): return self._render_rich(slide, index, "split")
    def render_turn_and_talk(self, slide, index=None): return self._render_rich(slide, index, "question")
    def render_sentence_frame(self, slide, index=None): return self._render_rich(slide, index, "question")
    def render_read_aloud(self, slide, index=None): return self._render_rich(slide, index, "checkpoint")
    def render_quote_analysis(self, slide, index=None): return self._render_rich(slide, index, "quote")
    def render_evidence_analysis(self, slide, index=None): return self._render_rich(slide, index, "columns")
    def render_progressive_grouping(self, slide, index=None): return self._render_rich(slide, index, "steps")
    def render_homework(self, slide, index=None): return self._render_rich(slide, index, "steps")
    def render_two_column(self, slide, index=None): return self._render_rich(slide, index, "columns")
    def render_full_visual(self, slide, index=None): return self._render_rich(slide, index, "visual_primary")
    def render_simple_directions(self, slide, index=None): return self._render_rich(slide, index, "steps")

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

    def add_rich_speaker_notes(self, slide_id: str, slide: PresentationSlide) -> None:
        presentation = self.slides_service.presentations().get(presentationId=self.presentation_id).execute()
        api_slide = next((item for item in presentation.get("slides", []) if item["objectId"] == slide_id), None)
        if api_slide is None:
            raise ValueError(f"Google Slides response did not contain slide {slide_id!r}")
        notes_id = api_slide["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
        self._batch_update([{"insertText": {"objectId": notes_id, "insertionIndex": 0,
                                              "text": self._format_rich_speaker_notes(slide)}}])

    def _render_rich(self, slide: PresentationSlide, index: int | None, kind: str) -> str:
        self._require_presentation()
        slide_id = self._google_id("slide", slide.slide_id)
        requests: list[dict[str, Any]] = [{"createSlide": {
            "objectId": slide_id, "insertionIndex": len(self._slide_ids) if index is None else index,
            "slideLayoutReference": {"predefinedLayout": "BLANK"}}}]
        requests.append({"updatePageProperties": {"objectId": slide_id,
            "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor":
                self._rgb(self.theme["colors"]["background_alternate" if kind in {"divider", "exit"} else "background"])}}}},
            "fields": "pageBackgroundFill"}})
        requests.extend(self._storyboard_decoration_requests(slide_id, slide))
        boxes = self._rich_geometry(kind, slide)
        visible = self._visible_content(slide)
        storyboard = self._storyboard_by_id.get(slide.slide_id)
        active = {key: box for key, box in boxes.items() if key == "visual" and slide.visuals.visual_required
                  or key in visible and visible.get(key)}
        self._validate_boxes(slide, active)
        if visible["title"]:
            requests.extend(self._rich_text_requests(slide_id, "title", slide.slide_id,
                visible["title"], boxes["title"], "title"))
        if visible["subtitle"] and "subtitle" in boxes:
            requests.extend(self._rich_text_requests(slide_id, "subtitle", slide.slide_id,
                visible["subtitle"], boxes["subtitle"], "subtitle"))
        family_value = storyboard.family.value if storyboard else ""
        if visible["body"] and "body" in boxes and family_value not in {"lesson_goals_cards"}:
            requests.extend(self._rich_text_requests(slide_id, "body", slide.slide_id,
                visible["body"], boxes["body"], "body"))
        if visible["prompt"] and "prompt" in boxes:
            requests.extend(self._rich_text_requests(slide_id, "prompt", slide.slide_id,
                visible["prompt"], boxes["prompt"], "prompt"))
        if kind == "cards":
            requests.extend(self._card_requests(slide_id, slide, visible["cards"]))
        if kind in {"columns"}:
            requests.extend(self._column_requests(slide_id, slide))
        requests.extend(self._storyboard_component_requests(slide_id, slide))
        storyboard_family = storyboard.family.value if storyboard else ""
        if "visual" in boxes and slide.visuals.visual_required and storyboard_family != "annotated_map":
            requests.extend(self._visual_requests(slide_id, slide, boxes["visual"]))
        cue = self._interaction_cue(slide)
        if cue:
            requests.extend(self._rich_text_requests(slide_id, "cue", slide.slide_id, cue,
                {"x": .7, "y": 6.72, "w": 4.2, "h": .38, "font": 12}, "cue"))
        if visible["footer"]:
            requests.extend(self._rich_text_requests(slide_id, "footer", slide.slide_id,
                visible["footer"], {"x": 8.0, "y": 6.83, "w": 4.7, "h": .25, "font": 9}, "caption"))
        self._batch_update(requests)
        self._slide_ids.append(slide_id)
        return slide_id

    def _storyboard_decoration_requests(self, slide_id: str, slide: PresentationSlide) -> list[dict[str, Any]]:
        story = self._storyboard_by_id.get(slide.slide_id)
        if story is None: return []
        family = story.family.value; colors=self.theme["colors"]; requests=[]
        def shape(role, shape_type, x,y,w,h,color):
            oid=self._google_id(f"decor_{role}",slide.slide_id)
            requests.append({"createShape":{"objectId":oid,"shapeType":shape_type,"elementProperties":{
                "pageObjectId":slide_id,"size":self._size(w,h),"transform":self._transform(x,y)}}})
            requests.append({"updateShapeProperties":{"objectId":oid,"shapeProperties":{"shapeBackgroundFill":{
                "solidFill":{"color":{"rgbColor":self._rgb(color)}}},"outline":{"propertyState":"NOT_RENDERED"}},
                "fields":"shapeBackgroundFill,outline"}})
        if family=="cinematic_title":
            shape("band","RECTANGLE",0,0,13.333,.28,colors["accent"]); shape("orb","ELLIPSE",9.0,.7,3.5,3.5,colors["secondary"])
        elif family=="section_divider":
            shape("band","RECTANGLE",0,0,3.1,7.5,colors["primary"]); shape("dot","ELLIPSE",11.6,.65,.65,.65,colors["accent"])
        elif family=="lesson_goals_cards":
            for i in range(3): shape(f"goal{i}","ROUND_RECTANGLE",.7+i*4.15,1.7,3.75,3.9,"#FFFFFF")
        elif family=="annotated_map":
            shape("map","ROUND_RECTANGLE",6.85,1.35,5.75,5.05,"#DCEAF0")
            shape("minneapolis","ELLIPSE",8.0,2.0,.32,.32,colors["accent"])
            shape("guanajuato","ELLIPSE",10.65,4.65,.32,.32,colors["secondary"])
            # The connecting route is a native arrow, avoiding an external map dependency.
            lid=self._google_id("decor_route",slide.slide_id)
            requests.append({"createLine":{"objectId":lid,"lineCategory":"STRAIGHT","elementProperties":{
                "pageObjectId":slide_id,"size":self._size(2.65,2.65),"transform":self._transform(8.16,2.16)}}})
        elif family in {"vocabulary_cards","vocabulary_image_grid"}:
            for i in range(4):
                shape(f"vocab{i}","ROUND_RECTANGLE",.7+(i%2)*6.15,1.55+(i//2)*2.45,5.75,2.05,"#FFFFFF")
                shape(f"vicon{i}","ELLIPSE",.95+(i%2)*6.15,1.85+(i//2)*2.45,.55,.55,colors["accent"])
        elif family=="sentence_frame_spotlight":
            shape("banner","ROUND_RECTANGLE",1.0,2.0,11.3,2.9,"#FFFFFF"); shape("accent","RECTANGLE",1.0,2.0,.18,2.9,colors["accent"])
        elif family=="quote_analysis":
            shape("quote","ROUND_RECTANGLE",1.0,1.55,11.3,4.8,"#FFFFFF"); shape("quote_mark","ELLIPSE",.7,1.25,.75,.75,colors["accent"])
        elif family=="progressive_grouping":
            for i,size in enumerate((.75,1.0,1.25,1.5)): shape(f"group{i}","ELLIPSE",1.0+i*2.9,2.25-size/4,size,size,colors["secondary" if i%2 else "accent"])
        elif family in {"exit_ticket","homework_summary"}:
            shape("paper","ROUND_RECTANGLE",1.0,1.45,11.3,4.95,"#FFFFFF"); shape("tab","ROUND_RECTANGLE",9.85,.85,2.0,.7,colors["accent"])
        elif family in {"discussion_question","image_hook"}:
            shape("focus","ROUND_RECTANGLE",.9,1.45,11.5,4.9,"#FFFFFF")
        return requests

    def _storyboard_component_requests(self, slide_id: str, slide: PresentationSlide) -> list[dict[str, Any]]:
        story=self._storyboard_by_id.get(slide.slide_id)
        if not story: return []
        requests=[]; family=story.family.value
        if family=="lesson_goals_cards":
            goals=slide.student_view.bullet_points[:3]
            for i,text in enumerate(goals):
                requests.extend(self._rich_text_requests(slide_id,f"goaltext{i}",slide.slide_id,text,
                    {"x":.98+i*4.15,"y":2.15,"w":3.15,"h":2.8,"font":20},"body"))
        elif family=="annotated_map":
            for i,(label,x,y) in enumerate((("Minneapolis",7.25,2.35),("Guanajuato",10.0,5.0))):
                requests.extend(self._rich_text_requests(slide_id,f"maplabel{i}",slide.slide_id,label,
                    {"x":x,"y":y,"w":1.8,"h":.45,"font":14},"caption"))
        elif family=="progressive_grouping":
            for i,(label,x) in enumerate((("Pair",.8),("Four",3.65),("Eight",6.55),("Share",9.45))):
                requests.extend(self._rich_text_requests(slide_id,f"grouplabel{i}",slide.slide_id,label,
                    {"x":x,"y":4.2,"w":2.1,"h":.5,"font":16},"caption"))
        return requests

    def _rich_geometry(self, kind: str, slide: PresentationSlide) -> dict[str, dict[str, float]]:
        title = {"x": .7, "y": .45, "w": 11.9, "h": .65, "font": self.theme["typography"]["title_size"]}
        standard = {"title": title, "subtitle": {"x": .72, "y": 1.15, "w": 11.6, "h": .45, "font": 20},
                    "body": {"x": .75, "y": 1.75, "w": 11.7, "h": 4.65, "font": 20},
                    "prompt": {"x": 1.0, "y": 2.1, "w": 11.0, "h": 2.8, "font": 26}}
        if kind == "hero":
            return {"title": {"x": .75, "y": 1.05, "w": 6.0, "h": 1.45, "font": 34},
                    "subtitle": {"x": .8, "y": 2.65, "w": 5.6, "h": 1.0, "font": 22},
                    "visual": {"x": 7.0, "y": .65, "w": 5.6, "h": 5.9}}
        if kind == "divider":
            return {"title": {"x": 1.1, "y": 2.1, "w": 11.1, "h": 1.2, "font": 38},
                    "subtitle": {"x": 1.15, "y": 3.45, "w": 10.8, "h": .85, "font": 22}}
        if kind == "split":
            visual_right = slide.visuals.placement.value != "left" and slide.design.image_position.value != "left"
            return {"title": title,
                    "body": {"x": .75 if visual_right else 7.1, "y": 3.05, "w": 5.45, "h": 3.35, "font": 20},
                    "prompt": {"x": .75 if visual_right else 7.1, "y": 1.55, "w": 5.45, "h": 1.4, "font": 24},
                    "visual": {"x": 6.9 if visual_right else .7, "y": 1.4, "w": 5.7, "h": 5.05}}
        if kind == "visual_primary":
            return {"title": title, "prompt": {"x": .8, "y": 5.75, "w": 11.7, "h": .7, "font": 20},
                    "visual": {"x": .75, "y": 1.35, "w": 11.8, "h": 4.15}}
        if kind in {"question", "quote"}:
            return {"title": title, "prompt": {"x": 1.25, "y": 1.75, "w": 10.8, "h": 2.15, "font": 28},
                    "body": {"x": 1.35, "y": 4.15, "w": 10.6, "h": 2.1, "font": 18}}
        if kind in {"cards", "columns"}:
            return {"title": title, "body": {"x": .75, "y": 1.25, "w": 11.8, "h": .45, "font": 18}}
        if kind == "exit":
            if slide.student_view.prompt:
                return {"title": {"x": .8, "y": .65, "w": 11.7, "h": .8, "font": 30},
                        "prompt": {"x": 1.15, "y": 1.8, "w": 11.0, "h": 2.2, "font": 27},
                        "body": {"x": 1.3, "y": 4.25, "w": 10.7, "h": 1.75, "font": 18}}
            return {"title": {"x": .8, "y": .65, "w": 11.7, "h": .8, "font": 30},
                    "body": {"x": 1.15, "y": 1.75, "w": 11.0, "h": 4.5, "font": 20}}
        if kind == "minimal":
            return {"title": {"x": 1.0, "y": 2.0, "w": 11.3, "h": 1.1, "font": 34},
                    "body": {"x": 1.25, "y": 3.35, "w": 10.8, "h": 1.2, "font": 22}}
        standard["prompt"] = {"x": 1.0, "y": 1.85, "w": 11.0, "h": 1.15, "font": 24}
        standard["body"] = {"x": .75, "y": 3.2, "w": 11.7, "h": 3.15, "font": 20}
        return standard

    def _visible_content(self, slide: PresentationSlide) -> dict[str, Any]:
        view = slide.student_view
        bullets = view.bullet_points[:self.theme["content_limits"]["maximum_bullets"]]
        if len(view.bullet_points) > len(bullets):
            self._warn(slide, "bullet_overflow", "Extra bullets were omitted.")
        body_parts = [view.body_text, *[f"• {item}" for item in bullets],
                      *[f"{i}. {item}" for i, item in enumerate(view.directions[:5], 1)],
                      *[f"Sentence frame: {item}" for item in view.sentence_frames[:2]]]
        prompt = view.prompt or view.quotation or ""
        raw = {"title": view.title, "subtitle": view.subtitle or "", "body": "\n".join(x for x in body_parts if x),
               "prompt": prompt, "footer": view.footer_text or "", "cards": view.vocabulary_terms[:6]}
        for key in ("title", "subtitle", "body", "prompt", "footer"):
            raw[key] = self._sanitize_visible(raw[key], slide)
        return raw

    def _sanitize_visible(self, text: str, slide: PresentationSlide) -> str:
        value = text or ""
        if re.search(r"(?:[A-Za-z]:\\|/[^\s]+/|\\\\|\.(?:pdf|docx?|pptx?)\b)", value, re.I):
            self._warn(slide, "visible_file_path", "A local path or filename was removed from visible content.")
            value = re.sub(r"(?:[A-Za-z]:\\\S+|/\S+|\\\\\S+|\S+\.(?:pdf|docx?|pptx?))", "", value, flags=re.I)
        value = re.sub(r"\bteacheros_added\b", "", value, flags=re.I)
        return " ".join(value.split()) if "\n" not in value else "\n".join(" ".join(line.split()) for line in value.splitlines())

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

    def _rich_text_requests(self, slide_id: str, role: str, source_id: str, text: str,
                            box: dict[str, Any], style: str) -> list[dict[str, Any]]:
        object_id = self._google_id(role, source_id)
        typography, colors = self.theme["typography"], self.theme["colors"]
        preferred = box.get("font", typography["body_size"])
        minimum = (28 if style == "title" else 14 if style in {"caption", "cue"}
                   else typography["minimum_body_size"])
        preferred = max(preferred, minimum)
        font = self._fit_font(text, box, preferred, minimum)
        if font is None:
            font = minimum
            self.warnings.append({"slide_id": source_id, "code": "text_does_not_fit",
                                  "message": f"{role} content needs an additional slide; it was not truncated."})
        color_key = "primary" if style in {"title", "prompt"} else "muted_text" if style in {"caption", "cue"} else "text"
        return [
            {"createShape": {"objectId": object_id, "shapeType": "ROUND_RECTANGLE" if style == "cue" else "TEXT_BOX",
                "elementProperties": {"pageObjectId": slide_id, "size": self._size(box["w"], box["h"]),
                    "transform": self._transform(box["x"], box["y"])}}},
            {"insertText": {"objectId": object_id, "insertionIndex": 0, "text": text}},
            {"updateTextStyle": {"objectId": object_id, "textRange": {"type": "ALL"},
                "style": {"fontFamily": typography["title_font" if style in {"title", "prompt"} else "body_font"],
                    "fontSize": {"magnitude": font, "unit": "PT"}, "bold": style in {"title", "prompt", "cue"},
                    "foregroundColor": {"opaqueColor": {"rgbColor": self._rgb(colors[color_key])}}},
                "fields": "fontFamily,fontSize,bold,foregroundColor"}},
        ]

    def _card_requests(self, slide_id: str, slide: PresentationSlide, terms: list[str]) -> list[dict[str, Any]]:
        cards = terms or slide.student_view.bullet_points[:3]
        if len(cards) > 6:
            self._warn(slide, "card_overflow", "Only the first six cards were rendered.")
        cards = cards[:6]
        requests: list[dict[str, Any]] = []
        columns = 2 if len(cards) <= 4 else 3
        for i, text in enumerate(cards):
            row, col = divmod(i, columns)
            if columns == 2:
                box = {"x": 1.65 + col * 6.15, "y": 1.8 + row * 2.45, "w": 4.55, "h": 1.55, "font": 18}
            else:
                box = {"x": .75 + col * 4.05, "y": 1.75 + row * 2.25, "w": 3.65, "h": 1.75, "font": 18}
            requests.extend(self._rich_text_requests(slide_id, f"card{i}", slide.slide_id, text, box, "body"))
        return requests

    def _column_requests(self, slide_id: str, slide: PresentationSlide) -> list[dict[str, Any]]:
        values = slide.student_view.bullet_points or slide.student_view.directions
        midpoint = max(1, (len(values) + 1) // 2)
        left, right = values[:midpoint], values[midpoint:]
        requests = []
        for role, x, heading, items in (("leftcol", .75, "Evidence", left), ("rightcol", 6.75, "Interpretation", right)):
            text = heading + "\n\n" + "\n".join(f"• {item}" for item in items[:4])
            requests.extend(self._rich_text_requests(slide_id, role, slide.slide_id, text,
                {"x": x, "y": 1.75, "w": 5.65, "h": 4.55, "font": 18}, "body"))
        return requests

    def _visual_requests(self, slide_id: str, slide: PresentationSlide, box: dict[str, Any]) -> list[dict[str, Any]]:
        reference = slide.visuals.source_asset_reference
        if reference:
            candidate = Path(reference)
            if not candidate.is_absolute(): candidate = self.project_root / candidate
            if candidate.is_file():
                self._warn(slide, "local_asset_placeholder", "Local asset exists but requires an approved Google-accessible URL; a placeholder was rendered.")
            else:
                self._warn(slide, "missing_visual_asset", "The referenced visual asset was not found; a placeholder was rendered.")
        else:
            self._warn(slide, "missing_visual_asset", "A required visual has no local asset; a placeholder was rendered.")
        label = slide.visuals.visual_description or "Visual asset pending"
        return self._rich_text_requests(slide_id, "visual", slide.slide_id, label, {**box, "font": 18}, "caption")

    def _interaction_cue(self, slide: PresentationSlide) -> str:
        interaction = slide.interaction
        if interaction.interaction_type.value == "none": return ""
        labels = {"think_pair_share": "Think–Pair–Share", "turn_and_talk": "Turn & Talk",
                  "quick_write": "Quick Write", "small_group_discussion": "Small-Group Discussion",
                  "independent_response": "Independent Response", "exit_ticket": "Exit Ticket",
                  "partner_annotation": "Partner Annotation", "evidence_collection": "Evidence Collection",
                  "cold_call": "Whole-Class Share", "poll": "Poll"}
        cue = labels.get(interaction.interaction_type.value, interaction.interaction_type.value.replace("_", " ").title())
        if interaction.duration_minutes: cue += f" · {interaction.duration_minutes} min"
        return cue

    def _format_rich_speaker_notes(self, slide: PresentationSlide) -> str:
        notes = slide.teacher_notes
        sections = [("Instructional Purpose", notes.instructional_purpose), ("Teacher Script", notes.teacher_script),
            ("Timing", f"{slide.timing} minutes" if slide.timing else None),
            ("Directions", notes.teacher_directions), ("Questions", notes.questions),
            ("Anticipated Responses", notes.anticipated_responses), ("Misconceptions", notes.misconceptions),
            ("Checks for Understanding", notes.checks_for_understanding), ("ELD Supports", notes.eld_supports),
            ("Differentiation", notes.differentiation), ("Transition", notes.transition),
            ("Pacing", notes.pacing_notes), ("Materials", slide.materials),
            ("Sensitivity Notes", notes.safety_or_sensitivity_notes),
            ("Sources", slide.source_references)]
        rendered = []
        for heading, value in sections:
            if value:
                body = "\n".join(f"• {item}" for item in value) if isinstance(value, list) else value
                rendered.append(f"{heading}\n{body}")
        if slide.slide_id == self._rich_attribution_slide_id:
            rendered.append(f"Attribution\n{CKLA_ATTRIBUTION}")
        return "\n\n".join(rendered)

    def _validate_presentation(self, presentation: PresentationDesignOutput) -> None:
        if not isinstance(presentation, PresentationDesignOutput):
            raise TypeError("presentation must be a validated PresentationDesignOutput object")
        for slide in presentation.slides: self._validate_rich_slide(slide)

    def _validate_rich_slide(self, slide: PresentationSlide) -> None:
        if slide.design.layout.value not in self.RICH_LAYOUTS:
            raise ValueError(f"Unsupported rich slide layout: {slide.design.layout.value!r}")
        if slide.design.layout.value not in {"day_divider"} and not slide.student_view.title.strip():
            self._warn(slide, "missing_title", "This layout normally requires a title.")
        if slide.visuals.visual_required and not slide.visuals.alt_text:
            self._warn(slide, "missing_alt_text", "Required visual has no alt text.")

    def _warn(self, slide: PresentationSlide, code: str, message: str) -> None:
        warning = {"slide_id": slide.slide_id, "code": code, "message": message}
        if warning not in self.warnings: self.warnings.append(warning)

    @staticmethod
    def _fit_font(text: str, box: dict[str, Any], preferred: int, minimum: int) -> int | None:
        """Conservative classroom text estimate using box area and average glyph width."""
        for font in range(int(preferred), int(minimum) - 1, -1):
            chars_per_line = max(1, int(box["w"] * 72 / (font * .56)))
            lines = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line)
                        for line in text.splitlines() or [""])
            line_capacity = max(1, int(box["h"] * 72 / (font * 1.22)))
            if lines <= line_capacity:
                return font
        return None

    def _validate_boxes(self, slide: PresentationSlide, boxes: dict[str, dict[str, float]]) -> None:
        width = float(self.theme["dimensions"]["width_inches"])
        height = float(self.theme["dimensions"]["height_inches"])
        items = list(boxes.items())
        for name, box in items:
            if box["x"] < 0 or box["y"] < 0 or box["x"] + box["w"] > width or box["y"] + box["h"] > height:
                raise ValueError(f"Layout region {name!r} is outside slide bounds for {slide.slide_id}")
        for index, (left_name, left) in enumerate(items):
            for right_name, right in items[index + 1:]:
                overlap = (left["x"] < right["x"] + right["w"] and left["x"] + left["w"] > right["x"]
                           and left["y"] < right["y"] + right["h"] and left["y"] + left["h"] > right["y"])
                if overlap:
                    raise ValueError(f"Layout regions {left_name!r} and {right_name!r} overlap for {slide.slide_id}")

    @staticmethod
    def _emu(inches: float) -> int: return round(float(inches) * 914_400)

    def _size(self, width: float, height: float) -> dict[str, Any]:
        return {"width": {"magnitude": self._emu(width), "unit": "EMU"},
                "height": {"magnitude": self._emu(height), "unit": "EMU"}}

    def _transform(self, x: float, y: float) -> dict[str, Any]:
        return {"scaleX": 1, "scaleY": 1, "translateX": self._emu(x), "translateY": self._emu(y), "unit": "EMU"}

    @staticmethod
    def _rgb(value: str) -> dict[str, float]:
        value = value.lstrip("#")
        try: return {"red": int(value[0:2], 16) / 255, "green": int(value[2:4], 16) / 255, "blue": int(value[4:6], 16) / 255}
        except (ValueError, IndexError): return {"red": 1, "green": 1, "blue": 1}

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
