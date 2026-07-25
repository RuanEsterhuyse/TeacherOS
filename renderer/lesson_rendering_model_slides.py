"""Strict one-to-one Google Slides rendering for LessonRenderingModel."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from curriculum.intelligence.ids import content_digest
from renderer.google_slides_renderer import GoogleSlidesRenderer
from renderer.lesson_rendering_model_adapter import (
    RENDER_INSTRUCTION_SCHEMA_VERSION,
    LessonRenderingModelSlidesAdapter,
    NormalizedSlideInstruction,
    RenderLayout,
)
from schemas.lesson_rendering_model_schema import (
    LessonRenderingModel,
    LessonRenderingValidationReport,
)


RENDERER_VERSION = "1.0"
MANIFEST_SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RenderReadiness(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"


class ExportStatus(StrictModel):
    format: str = Field(min_length=1)
    status: str = Field(min_length=1)
    path: Optional[str] = None
    message: Optional[str] = None


class RenderedSlideRecord(StrictModel):
    slide_number: int = Field(ge=1)
    source_slide_id: str = Field(min_length=1)
    google_slide_object_id: str = Field(min_length=1)
    slide_type: str = Field(min_length=1)
    layout_name: str = Field(min_length=1)
    notes_written: bool
    visible_text_digest: str = Field(min_length=1)
    notes_digest: str = Field(min_length=1)
    question_ids: list[str] = Field(default_factory=list)
    answer_ids: list[str] = Field(default_factory=list)
    resource_references: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class GoogleSlidesRenderManifest(StrictModel):
    lesson_id: str = Field(min_length=1)
    presentation_id: str = Field(min_length=1)
    presentation_url: str = Field(min_length=1)
    rendering_schema_version: str = RENDER_INSTRUCTION_SCHEMA_VERSION
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION
    renderer_version: str = RENDERER_VERSION
    source_model_content_digest: str = Field(min_length=1)
    source_model_artifact_digest: str = Field(min_length=1)
    expected_slide_count: int = Field(ge=0)
    created_slide_count: int = Field(ge=0)
    ordered_slide_records: list[RenderedSlideRecord]
    export_statuses: list[ExportStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    readiness_status: RenderReadiness
    content_digest: str = Field(min_length=1)
    manifest_digest: str = Field(min_length=1)


class ContentOverflowError(ValueError):
    pass


class LessonRenderingModelGoogleSlidesRenderer(GoogleSlidesRenderer):
    """Render exactly one API slide for each normalized source instruction."""

    def create_from_rendering_model(
        self,
        model: LessonRenderingModel,
        validation: LessonRenderingValidationReport,
        *,
        output_directory: str | Path,
        asset_registry: dict[str, str] | None = None,
        export_pptx: bool = False,
        export_pdf: bool = False,
        presentation_title: str | None = None,
        existing_presentation_id: str | None = None,
    ) -> GoogleSlidesRenderManifest:
        instructions = LessonRenderingModelSlidesAdapter().adapt(
            model, validation, asset_registry=asset_registry
        )
        self._preflight(instructions)
        self._ensure_services()
        if existing_presentation_id:
            self.presentation_id = existing_presentation_id
            created = self.slides_service.presentations().get(
                presentationId=self.presentation_id
            ).execute()
        else:
            dims = self.theme["dimensions"]
            created = self.slides_service.presentations().create(body={
                "title": presentation_title or model.lesson_title,
                "pageSize": {
                    "width": {
                        "magnitude": self._emu(dims["width_inches"]),
                        "unit": "EMU",
                    },
                    "height": {
                        "magnitude": self._emu(dims["height_inches"]),
                        "unit": "EMU",
                    },
                },
            }).execute()
            self.presentation_id = created["presentationId"]
        page_size = created.get("pageSize", {})
        actual_width = (
            page_size.get("width", {}).get("magnitude")
        )
        expected_width = self._emu(
            self.theme["dimensions"]["width_inches"]
        )
        self._canvas_scale = (
            actual_width / expected_width
            if actual_width else 1.0
        )
        self._slide_ids = []
        if created.get("slides"):
            self._batch_update([
                {"deleteObject": {"objectId": item["objectId"]}}
                for item in created["slides"]
            ])
        render_requests = []
        records = []
        for instruction in instructions:
            google_id, requests = self._render_instruction_requests(
                instruction, len(records)
            )
            render_requests.extend(requests)
            records.append(RenderedSlideRecord(
                slide_number=instruction.slide_number,
                source_slide_id=instruction.source_slide_id,
                google_slide_object_id=google_id,
                slide_type=instruction.slide_type.value,
                layout_name=instruction.layout_name.value,
                notes_written=True,
                visible_text_digest=instruction.visible_text_digest,
                notes_digest=instruction.notes_digest,
                question_ids=instruction.question_ids,
                answer_ids=instruction.answer_ids,
                resource_references=instruction.resource_references,
                warnings=instruction.warnings,
                blockers=instruction.blockers,
            ))
        self._batch_update(render_requests)
        self._slide_ids = [
            value.google_slide_object_id for value in records
        ]
        self._write_instruction_notes_batch(instructions, records)
        self._verify_remote_order(records)
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        exports = []
        if export_pptx:
            path = self.export(
                self.presentation_id, output / f"{model.lesson_id}.pptx"
            )
            exports.append(ExportStatus(
                format="pptx", status="exported", path=str(path)
            ))
        if export_pdf:
            path = self.export(
                self.presentation_id, output / f"{model.lesson_id}.pdf"
            )
            exports.append(ExportStatus(
                format="pdf", status="exported", path=str(path)
            ))
        manifest = self._manifest(model, records, exports)
        self._write_manifest(output, manifest)
        return manifest

    def _preflight(
        self, instructions: list[NormalizedSlideInstruction]
    ) -> None:
        for instruction in instructions:
            for role, text, box, preferred, minimum in self._text_blocks(
                instruction
            ):
                if text and self._fit_font(
                    text, box, preferred, minimum
                ) is None:
                    raise ContentOverflowError(
                        "content_overflow:"
                        f"{instruction.source_slide_id}:{role}"
                    )

    def _render_instruction_requests(
        self,
        instruction: NormalizedSlideInstruction,
        insertion_index: int,
    ) -> tuple[str, list[dict[str, Any]]]:
        self._require_presentation()
        slide_id = self._google_id(
            "slide", instruction.source_slide_id
        )
        requests: list[dict[str, Any]] = [{
            "createSlide": {
                "objectId": slide_id,
                "insertionIndex": insertion_index,
                "slideLayoutReference": {"predefinedLayout": "BLANK"},
            }
        }, {
            "updatePageProperties": {
                "objectId": slide_id,
                "pageProperties": {
                    "pageBackgroundFill": {
                        "solidFill": {
                            "color": {
                                "rgbColor": self._rgb(
                                    self.theme["colors"]["background"]
                                )
                            }
                        }
                    }
                },
                "fields": "pageBackgroundFill",
            }
        }]
        for role, text, box, preferred, minimum in self._text_blocks(
            instruction
        ):
            if not text:
                continue
            font = self._fit_font(
                text, box, preferred, minimum
            )
            if font is None:
                raise ContentOverflowError(
                    f"content_overflow:{instruction.source_slide_id}:{role}"
                )
            requests.extend(self._strict_text_requests(
                slide_id, instruction.source_slide_id, role,
                text, box, font,
            ))
        for index, visual in enumerate(instruction.visuals):
            box = {"x": 9.05, "y": 1.45 + index * 2.5,
                   "w": 3.55, "h": 2.15, "font": 16}
            live_box = self._live_box(box)
            object_id = self._google_id(
                f"visual_{index}", instruction.source_slide_id
            )
            if visual.asset_reference:
                requests.append({"createImage": {
                    "objectId": object_id,
                    "url": visual.asset_reference,
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": self._size(
                            live_box["w"], live_box["h"]
                        ),
                        "transform": self._transform(
                            live_box["x"], live_box["y"]
                        ),
                    },
                }})
            elif visual.placeholder_text:
                requests.extend(self._strict_text_requests(
                    slide_id, instruction.source_slide_id,
                    f"visual_placeholder_{index}",
                    visual.placeholder_text, box, 16,
                ))
        return slide_id, requests

    def _text_blocks(self, instruction):
        title = {
            "x": .7, "y": .45, "w": 11.9, "h": .72, "font": 30
        }
        layout = instruction.layout_name
        blocks = [(
            "title", instruction.title, title,
            34 if layout in {RenderLayout.TITLE, RenderLayout.DIVIDER} else 30,
            24,
        )]
        if instruction.subtitle:
            blocks.append((
                "subtitle", instruction.subtitle,
                {"x": .75, "y": 1.25, "w": 11.8, "h": .55, "font": 22},
                22, 18,
            ))
        lines = instruction.content_lines
        if layout == RenderLayout.TITLE:
            blocks[0] = (
                "title", instruction.title,
                {"x": .9, "y": 2.0, "w": 11.55, "h": 1.35, "font": 38},
                38, 28,
            )
            if lines:
                blocks.append((
                    "body", "\n".join(lines),
                    {"x": 1.2, "y": 3.65, "w": 10.9, "h": 1.65, "font": 22},
                    22, 18,
                ))
        elif layout == RenderLayout.DIVIDER:
            blocks[0] = (
                "title", instruction.title,
                {"x": 1.0, "y": 2.55, "w": 11.3, "h": 1.3, "font": 38},
                38, 28,
            )
        elif layout == RenderLayout.TWO_COLUMN:
            midpoint = self._balanced_column_split(lines)
            for role, x, values in (
                ("left_column", .75, lines[:midpoint]),
                ("right_column", 6.75, lines[midpoint:]),
            ):
                if values:
                    blocks.append((
                        role, "\n".join(values),
                        {"x": x, "y": 1.2, "w": 5.65,
                         "h": 5.65, "font": 18},
                        18, 15,
                    ))
        elif layout in {RenderLayout.QUESTION, RenderLayout.DISCUSSION}:
            if lines:
                blocks.append((
                    "questions", "\n\n".join(lines),
                    {"x": 1.0, "y": 1.55, "w": 11.3,
                     "h": 4.75, "font": 26},
                    26, 18,
                ))
        else:
            if lines:
                body_width = 7.85 if instruction.visuals else 11.7
                blocks.append((
                    "body", "\n\n".join(lines),
                    {"x": .8, "y": 1.45, "w": body_width,
                     "h": 4.95, "font": 20},
                    20, 18,
                ))
        if instruction.cue_lines:
            blocks.append((
                "cue", " • ".join(instruction.cue_lines),
                {"x": .8, "y": 6.55, "w": 8.0, "h": .38, "font": 14},
                14, 12,
            ))
        if instruction.footer:
            blocks.append((
                "footer", instruction.footer,
                {"x": 8.9, "y": 6.75, "w": 3.7, "h": .28, "font": 10},
                10, 9,
            ))
        return blocks

    def _balanced_column_split(self, lines: list[str]) -> int:
        """Choose the best content-preserving split for two fixed columns."""
        if len(lines) < 2:
            return len(lines)
        box = {"w": 5.65, "h": 5.65}
        candidates = []
        for index in range(1, len(lines)):
            left = "\n".join(lines[:index])
            right = "\n".join(lines[index:])
            left_font = self._fit_font(left, box, 18, 15)
            right_font = self._fit_font(right, box, 18, 15)
            if left_font is not None and right_font is not None:
                candidates.append((
                    min(left_font, right_font),
                    -abs(len(left) - len(right)),
                    -index,
                    index,
                ))
        if candidates:
            return max(candidates)[-1]
        return (len(lines) + 1) // 2

    def _strict_text_requests(
        self,
        slide_id: str,
        source_slide_id: str,
        role: str,
        text: str,
        box: dict[str, float],
        font: int,
    ) -> list[dict[str, Any]]:
        object_id = self._google_id(role, source_slide_id)
        live_box = self._live_box(box)
        live_font = self._live_font(font)
        colors = self.theme["colors"]
        typography = self.theme["typography"]
        title = role in {"title", "subtitle"}
        return [
            {"createShape": {
                "objectId": object_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": self._size(
                        live_box["w"], live_box["h"]
                    ),
                    "transform": self._transform(
                        live_box["x"], live_box["y"]
                    ),
                },
            }},
            {"insertText": {
                "objectId": object_id,
                "insertionIndex": 0,
                "text": text,
            }},
            {"updateTextStyle": {
                "objectId": object_id,
                "textRange": {"type": "ALL"},
                "style": {
                    "fontFamily": typography[
                        "title_font" if title else "body_font"
                    ],
                    "fontSize": {
                        "magnitude": live_font, "unit": "PT"
                    },
                    "bold": role == "title",
                    "foregroundColor": {
                        "opaqueColor": {
                            "rgbColor": self._rgb(
                                colors["primary"]
                                if title else colors["text"]
                            )
                        }
                    },
                },
                "fields": (
                    "fontFamily,fontSize,bold,foregroundColor"
                ),
            }},
        ]

    def _live_box(self, box: dict[str, float]) -> dict[str, float]:
        scale = getattr(self, "_canvas_scale", 1.0)
        return {
            key: value * scale if key in {"x", "y", "w", "h"} else value
            for key, value in box.items()
        }

    def _live_font(self, font: int) -> float:
        return round(font * getattr(self, "_canvas_scale", 1.0), 2)

    def _write_instruction_notes_batch(
        self,
        instructions: list[NormalizedSlideInstruction],
        records: list[RenderedSlideRecord],
    ) -> None:
        presentation = self.slides_service.presentations().get(
            presentationId=self.presentation_id
        ).execute()
        slides_by_id = {
            value["objectId"]: value
            for value in presentation.get("slides", [])
        }
        if set(slides_by_id) != {
            value.google_slide_object_id for value in records
        }:
            raise ValueError(
                "Google Slides response omitted or added slides before notes."
            )
        requests = []
        for instruction, record in zip(instructions, records):
            notes_id = slides_by_id[record.google_slide_object_id][
                "slideProperties"
            ]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
            requests.append({"insertText": {
                "objectId": notes_id,
                "insertionIndex": 0,
                "text": instruction.notes_text,
            }})
        self._batch_update(requests)

    def _verify_remote_order(
        self, records: list[RenderedSlideRecord]
    ) -> None:
        presentation = self.slides_service.presentations().get(
            presentationId=self.presentation_id
        ).execute()
        actual = [
            value["objectId"] for value in presentation.get("slides", [])
        ]
        expected = [
            value.google_slide_object_id for value in records
        ]
        if actual != expected:
            raise ValueError(
                "Rendered Google slide count or order differs from source."
            )

    def _manifest(
        self,
        model: LessonRenderingModel,
        records: list[RenderedSlideRecord],
        exports: list[ExportStatus],
    ) -> GoogleSlidesRenderManifest:
        presentation_id = self.presentation_id or ""
        url = (
            "https://docs.google.com/presentation/d/"
            f"{presentation_id}/edit"
        )
        provisional = GoogleSlidesRenderManifest(
            lesson_id=model.lesson_id,
            presentation_id=presentation_id,
            presentation_url=url,
            source_model_content_digest=model.content_digest,
            source_model_artifact_digest=model.artifact_digest,
            expected_slide_count=len(model.slides),
            created_slide_count=len(records),
            ordered_slide_records=records,
            export_statuses=exports,
            warnings=[],
            blockers=[],
            readiness_status=RenderReadiness.READY,
            content_digest="pending",
            manifest_digest="pending",
        )
        deterministic = provisional.model_dump(
            mode="json",
            exclude={
                "presentation_id", "presentation_url",
                "content_digest", "manifest_digest",
            },
        )
        digest = content_digest(deterministic)
        return provisional.model_copy(update={
            "content_digest": digest,
            "manifest_digest": content_digest({
                "content_digest": digest,
                "schema": MANIFEST_SCHEMA_VERSION,
                "renderer": RENDERER_VERSION,
            }),
        })

    @staticmethod
    def _write_manifest(
        output: Path, manifest: GoogleSlidesRenderManifest
    ) -> None:
        (output / "google_slides_render_manifest.json").write_text(
            manifest.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        lines = [
            "# Google Slides Render Manifest", "",
            f"- Lesson: `{manifest.lesson_id}`",
            f"- Presentation: {manifest.presentation_url}",
            f"- Expected slides: {manifest.expected_slide_count}",
            f"- Created slides: {manifest.created_slide_count}",
            f"- Readiness: `{manifest.readiness_status.value}`", "",
            "## Ordered Slides", "",
        ]
        lines.extend(
            f"- {value.slide_number}. `{value.source_slide_id}` → "
            f"`{value.google_slide_object_id}` "
            f"({value.layout_name}, notes={value.notes_written})"
            for value in manifest.ordered_slide_records
        )
        (output / "google_slides_render_manifest.md").write_text(
            "\n".join(lines).strip() + "\n", encoding="utf-8"
        )


def create_lesson_rendering_model_deck(
    *,
    model_path: str | Path,
    validation_path: str | Path,
    output_directory: str | Path,
    credentials_path: str | Path = "credentials.json",
    token_path: str | Path = "token.json",
    asset_registry_path: str | Path | None = None,
    export_pptx: bool = False,
    export_pdf: bool = False,
    presentation_title: str | None = None,
    existing_presentation_id: str | None = None,
) -> GoogleSlidesRenderManifest:
    """Manual live entry point; automated tests never call this function."""
    model = LessonRenderingModel.model_validate_json(
        Path(model_path).read_text(encoding="utf-8")
    )
    validation = LessonRenderingValidationReport.model_validate_json(
        Path(validation_path).read_text(encoding="utf-8")
    )
    registry = (
        json.loads(
            Path(asset_registry_path).read_text(encoding="utf-8")
        )
        if asset_registry_path else {}
    )
    renderer = LessonRenderingModelGoogleSlidesRenderer(
        credentials_path=credentials_path,
        token_path=token_path,
    )
    manifest = renderer.create_from_rendering_model(
        model, validation, output_directory=output_directory,
        asset_registry=registry, export_pptx=export_pptx,
        export_pdf=export_pdf, presentation_title=presentation_title,
        existing_presentation_id=existing_presentation_id,
    )
    print(f"Google Slides URL: {manifest.presentation_url}")
    print(f"Slides created: {manifest.created_slide_count}")
    return manifest


__all__ = [
    "ContentOverflowError", "GoogleSlidesRenderManifest",
    "LessonRenderingModelGoogleSlidesRenderer", "RenderedSlideRecord",
    "create_lesson_rendering_model_deck",
]
