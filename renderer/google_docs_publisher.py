"""Optional editable Google Docs publishing for Teacher Companions."""

from __future__ import annotations

from html import escape
import os
from pathlib import Path
from typing import Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

from schemas.teaching_package_schema import (
    ContentOrigin,
    GroundedText,
    StructuredTeachingPackage,
    TeachingSourceReference,
)


class GoogleDocsPublisher:
    """Publish approved package content; local generation never depends on it."""

    SCOPES = (
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file",
    )
    AGENDA_MARKER = "[[TEACHEROS_AGENDA_TABLE]]"

    def __init__(
        self,
        credentials_path: str | os.PathLike[str] = "credentials.json",
        token_path: str | os.PathLike[str] = "token.json",
        *,
        docs_service: Any | None = None,
        drive_service: Any | None = None,
        credentials: Credentials | None = None,
        service_builder: Callable[..., Any] = build,
    ) -> None:
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.credentials = credentials
        self.docs_service = docs_service
        self.drive_service = drive_service
        self._service_builder = service_builder

    def authenticate(self) -> Credentials:
        credentials = self.credentials
        if credentials is None and self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self.token_path), self.SCOPES
            )
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth client file not found: {self.credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.SCOPES
                )
                credentials = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(
                credentials.to_json(), encoding="utf-8"
            )
        self.credentials = credentials
        if self.docs_service is None:
            self.docs_service = self._service_builder(
                "docs",
                "v1",
                credentials=credentials,
                cache_discovery=False,
            )
        if self.drive_service is None:
            self.drive_service = self._service_builder(
                "drive",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )
        return credentials

    def document_text(
        self, package: StructuredTeachingPackage
    ) -> tuple[str, list[tuple[int, int, str]]]:
        """Render teacher-facing structured fields, never Markdown."""
        blocks = self._document_blocks(package)
        lines: list[str] = []
        headings: list[tuple[int, int, str]] = []
        cursor = 1
        for line, style, _ in blocks:
            start = cursor
            rendered = line + "\n"
            lines.append(rendered)
            cursor += len(rendered)
            if style and line:
                headings.append((start, cursor, style))
        return "".join(lines), headings

    @staticmethod
    def _source_label(
        references: list[TeachingSourceReference],
    ) -> str:
        values = []
        for reference in references:
            location = (
                f"PDF p. {reference.display_page_number}"
                if reference.display_page_number is not None
                else reference.printed_page or reference.stable_source_id
            )
            values.append(f"{reference.source_document} ({location})")
        return "; ".join(dict.fromkeys(values))

    @classmethod
    def _grounded_text(cls, value: GroundedText) -> str:
        if value.origin is ContentOrigin.UNAVAILABLE:
            return f"Unavailable — {value.text}"
        if value.origin is ContentOrigin.MODEL_ANALYSIS:
            return f"TeacherOS guidance — review: {value.text}"
        return value.text

    @staticmethod
    def _display_curriculum(value: str) -> str:
        if value.startswith("curriculum-language-arts-"):
            return "CKLA"
        return value

    @classmethod
    def _document_blocks(
        cls, package: StructuredTeachingPackage
    ) -> list[tuple[str, str, bool]]:
        dashboard = package.dashboard
        blocks: list[tuple[str, str, bool]] = []

        def add(text: str, style: str = "", bullet: bool = False) -> None:
            if text.strip():
                blocks.append((text.strip(), style, bullet))

        def heading(text: str, level: int = 1) -> None:
            add(text, f"HEADING_{level}")

        def grounded_list(values: list[GroundedText]) -> None:
            for value in values:
                add(cls._grounded_text(value), bullet=True)

        add(
            f"Teacher Companion: {dashboard.lesson_title}",
            "TITLE",
        )
        add(
            f"{cls._display_curriculum(dashboard.curriculum)} • "
            f"Grade {dashboard.grade} • Lesson {dashboard.lesson_number}",
            "SUBTITLE",
        )
        if dashboard.materials:
            add(dashboard.materials[0])
        add(
            "A classroom-ready guide built from the validated curriculum "
            "package. Generated guidance is labeled for teacher review."
        )

        heading("Lesson Dashboard")
        add(
            f"Estimated time: {dashboard.estimated_duration_minutes} minutes",
            bullet=True,
        )
        add(
            "Materials: "
            + (", ".join(dashboard.materials) or "No materials located"),
            bullet=True,
        )
        add(
            "Student Reader: "
            + (
                ", ".join(dashboard.student_reader_pages)
                or "No assigned pages located"
            ),
            bullet=True,
        )
        add(
            "Activity resources: "
            + (
                ", ".join(dashboard.activity_book_pages)
                or "No assigned activity resource located"
            ),
            bullet=True,
        )
        heading("What this lesson is for", 2)
        add(cls._grounded_text(dashboard.lesson_purpose))
        heading("Big idea", 2)
        add(cls._grounded_text(dashboard.big_idea))
        heading("Why it matters", 2)
        add(cls._grounded_text(dashboard.why_it_matters))

        heading("Teach This Lesson in Five Minutes")
        grounded_list(package.five_minute_summary)

        heading("Lesson at a Glance")
        add(cls.AGENDA_MARKER)

        heading("Objectives")
        for objective in package.objectives:
            heading(objective.objective_type.replace("_", " ").title(), 2)
            add(f"Official objective: {objective.official.text}")
            add(
                "Student-friendly objective: "
                f"{objective.student_friendly.text}"
            )
            add(
                "Evidence of mastery: "
                f"{objective.evidence_of_mastery.text}"
            )
            source = cls._source_label(
                objective.official.source_references
            )
            if source:
                add(f"Source: {source}")

        heading("Before Class")
        for reminder in dashboard.teacher_reminders:
            add(cls._grounded_text(reminder), bullet=True)
        for warning in dashboard.missing_resource_warnings:
            add(f"Resource warning: {warning}", bullet=True)

        heading("Vocabulary")
        if not package.vocabulary:
            add("No required vocabulary was located.")
        for vocabulary in package.vocabulary:
            heading(vocabulary.word, 2)
            if vocabulary.official_definition:
                add(
                    "Curriculum definition: "
                    f"{vocabulary.official_definition.text}"
                )
            add(
                "Student-friendly explanation: "
                f"{vocabulary.student_friendly_definition.text}"
            )
            add(f"Teaching example: {vocabulary.example.text}")
            add(f"ELD support: {vocabulary.eld_support.text}")
            add(f"Watch for: {vocabulary.misconception.text}")

        heading("Step-by-Step Teaching Guide")
        questions = {
            value.question_id: value for value in package.questions
        }
        for step in package.teaching_steps:
            heading(step.official_title, 2)
            add(
                f"Time: "
                f"{step.duration_minutes if step.duration_minutes is not None else 'Not specified'} "
                "minutes"
            )
            add(f"Purpose: {step.instructional_purpose.text}")
            if step.materials:
                add("Materials: " + ", ".join(step.materials))
            heading("Teacher moves", 3)
            for action in step.teacher_actions:
                add(action.text, bullet=True)
            heading("Student actions", 3)
            for action in step.student_actions:
                add(action.text, bullet=True)
            if step.question_ids:
                heading("Ask", 3)
                for question_id in step.question_ids:
                    add(
                        questions[question_id].exact_question.text,
                        bullet=True,
                    )
            if step.checks_for_understanding:
                heading("Check for understanding", 3)
                grounded_list(step.checks_for_understanding)
            if step.misconceptions:
                heading("Watch for", 3)
                grounded_list(step.misconceptions)
            if step.eld_supports:
                heading("ELD supports", 3)
                grounded_list(step.eld_supports)
            heading("Transition", 3)
            add(step.transition.text)
            source = cls._source_label(step.source_references)
            if source:
                add(f"Source: {source}")

        heading("Discussion and Answer Guide")
        for question in package.questions:
            heading(
                f"Question {question.sequence}: "
                f"{question.exact_question.text}",
                2,
            )
            add(
                "Expected answer: "
                f"{question.expected_answer.text}"
            )
            if question.text_evidence:
                add(f"Text evidence: {question.text_evidence.text}")
            add(f"Follow-up: {question.follow_up.text}")
            add(
                f"Likely misconception: {question.misconception.text}"
            )
            add(f"ELD sentence frame: {question.eld_sentence_frame.text}")
            source = cls._source_label(
                question.exact_question.source_references
            )
            if source:
                add(f"Source: {source}")

        for title, values in (
            ("Student Reader Guidance", package.student_reader_guidance),
            ("Activity Resource Guidance", package.activity_book_guidance),
            ("Assessment", package.assessment),
            ("Wrap-Up", package.wrap_up),
            ("Homework", package.homework),
            ("ELD and Differentiation", (
                package.eld_supports + package.differentiation
            )),
        ):
            heading(title)
            if values:
                grounded_list(values)
            else:
                add(
                    "No source-supported guidance was available. "
                    "Nothing was invented."
                )

        heading("Teacher Reflection")
        for prompt in (
            "What worked well?",
            "Where did students struggle?",
            "Which misconception appeared?",
            "Which supports were effective?",
            "What should change next time?",
            "Which students need follow-up?",
            "Was the pacing realistic?",
        ):
            add(prompt + "  ____________________________________", bullet=True)

        if package.warnings or package.validation.findings:
            heading("Review Notes")
            for warning in package.warnings:
                add(warning, bullet=True)
            for finding in package.validation.findings:
                add(
                    f"{finding.severity.value.title()}: "
                    f"{finding.message}",
                    bullet=True,
                )
        return blocks

    def build_requests(
        self, package: StructuredTeachingPackage
    ) -> list[dict[str, Any]]:
        text, headings = self.document_text(package)
        blocks = self._document_blocks(package)
        requests: list[dict[str, Any]] = [{
            "insertText": {
                "location": {"index": 1},
                "text": text,
            }
        }, {
            "updateDocumentStyle": {
                "documentStyle": {
                    "marginTop": {"magnitude": 54, "unit": "PT"},
                    "marginBottom": {"magnitude": 54, "unit": "PT"},
                    "marginLeft": {"magnitude": 58, "unit": "PT"},
                    "marginRight": {"magnitude": 58, "unit": "PT"},
                },
                "fields": (
                    "marginTop,marginBottom,marginLeft,marginRight"
                ),
            }
        }, {
            "updateTextStyle": {
                "range": {"startIndex": 1, "endIndex": len(text) + 1},
                "textStyle": {
                    "weightedFontFamily": {"fontFamily": "Arial"},
                    "fontSize": {"magnitude": 10.5, "unit": "PT"},
                    "foregroundColor": {
                        "color": {
                            "rgbColor": {
                                "red": .09, "green": .13, "blue": .17
                            }
                        }
                    },
                },
                "fields": (
                    "weightedFontFamily,fontSize,foregroundColor"
                ),
            }
        }, {
            "updateParagraphStyle": {
                "range": {"startIndex": 1, "endIndex": len(text) + 1},
                "paragraphStyle": {
                    "lineSpacing": 115,
                    "spaceBelow": {"magnitude": 5, "unit": "PT"},
                },
                "fields": "lineSpacing,spaceBelow",
            }
        }]
        for start, end, style in headings:
            requests.append({
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": start,
                        "endIndex": end,
                    },
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            })
            if style in {"TITLE", "HEADING_1", "HEADING_2"}:
                requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": start,
                            "endIndex": end - 1,
                        },
                        "textStyle": {
                            "foregroundColor": {
                                "color": {
                                    "rgbColor": (
                                        {"red": .09, "green": .20, "blue": .30}
                                        if style != "HEADING_2" else
                                        {"red": .12, "green": .48, "blue": .55}
                                    )
                                }
                            },
                            "bold": True,
                        },
                        "fields": "foregroundColor,bold",
                    }
                })
        cursor = 1
        for line, _, bullet in blocks:
            end = cursor + len(line) + 1
            if bullet:
                requests.append({
                    "createParagraphBullets": {
                        "range": {
                            "startIndex": cursor,
                            "endIndex": end,
                        },
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                })
            cursor = end
        return requests

    def document_html(self, package: StructuredTeachingPackage) -> str:
        """Build a styled, editable-document fallback for Drive import."""
        parts = [
            "<!doctype html><html><head><meta charset=\"utf-8\">",
            "<style>",
            (
                "body{font-family:Arial,sans-serif;color:#1c2935;"
                "font-size:11pt;line-height:1.35;margin:42pt}"
            ),
            (
                "h1{color:#17334d;font-size:26pt;margin:0 0 5pt}"
                "h2{color:#17334d;font-size:18pt;margin:20pt 0 7pt;"
                "border-bottom:2px solid #217b8c;padding-bottom:3pt}"
                "h3{color:#217b8c;font-size:14pt;margin:15pt 0 5pt}"
                "h4{color:#17334d;font-size:11.5pt;margin:11pt 0 4pt}"
            ),
            (
                ".subtitle{color:#526371;font-size:13pt;margin:0 0 4pt}"
                "p{margin:3pt 0 6pt}ul{margin:2pt 0 8pt 18pt}"
                "li{margin:0 0 3pt}"
            ),
            (
                "table{border-collapse:collapse;width:100%;margin:8pt 0 14pt}"
                "th{background:#17334d;color:#fff;text-align:left;"
                "padding:6pt;border:1px solid #d7dde1}"
                "td{padding:5pt;border:1px solid #d7dde1;vertical-align:top}"
                "tr:nth-child(even) td{background:#f5f2eb}"
            ),
            "</style></head><body>",
        ]
        bullets: list[str] = []

        def flush_bullets() -> None:
            if bullets:
                parts.append("<ul>")
                parts.extend(f"<li>{escape(value)}</li>" for value in bullets)
                parts.append("</ul>")
                bullets.clear()

        for line, style, bullet in self._document_blocks(package):
            if line == self.AGENDA_MARKER:
                flush_bullets()
                parts.append(self._agenda_html(package))
                continue
            if bullet:
                bullets.append(line)
                continue
            flush_bullets()
            tag = {
                "TITLE": "h1",
                "HEADING_1": "h2",
                "HEADING_2": "h3",
                "HEADING_3": "h4",
            }.get(style)
            if tag:
                parts.append(f"<{tag}>{escape(line)}</{tag}>")
            elif style == "SUBTITLE":
                parts.append(
                    f"<p class=\"subtitle\">{escape(line)}</p>"
                )
            elif line:
                parts.append(f"<p>{escape(line)}</p>")
        flush_bullets()
        parts.append("</body></html>")
        return "".join(parts)

    @staticmethod
    def _agenda_html(package: StructuredTeachingPackage) -> str:
        rows = [
            "<table><thead><tr>",
            "<th>Order</th><th>Lesson stage</th>",
            "<th>Student focus</th><th>Time</th><th>Materials</th>",
            "</tr></thead><tbody>",
        ]
        for item in package.agenda:
            values = (
                str(item.official_order),
                item.official_title.text,
                item.student_friendly_title.text,
                (
                    f"{item.duration_minutes} min"
                    if item.duration_minutes is not None else "—"
                ),
                ", ".join(item.materials) or "—",
            )
            rows.append(
                "<tr>"
                + "".join(f"<td>{escape(value)}</td>" for value in values)
                + "</tr>"
            )
        rows.append("</tbody></table>")
        return "".join(rows)

    def _publish_via_drive_import(
        self, package: StructuredTeachingPackage
    ) -> dict[str, str]:
        media = MediaInMemoryUpload(
            self.document_html(package).encode("utf-8"),
            mimetype="text/html",
            resumable=False,
        )
        created = self.drive_service.files().create(
            body={
                "name": (
                    f"Teacher Companion — "
                    f"{package.dashboard.lesson_title}"
                ),
                "mimeType": "application/vnd.google-apps.document",
            },
            media_body=media,
            fields="id",
        ).execute()
        document_id = created["id"]
        return {
            "documentId": document_id,
            "url": (
                f"https://docs.google.com/document/d/"
                f"{document_id}/edit"
            ),
        }

    def publish(
        self, package: StructuredTeachingPackage
    ) -> dict[str, str]:
        if package.validation.status == "fail":
            raise ValueError("Cannot publish a failed teaching package.")
        if self.docs_service is None or self.drive_service is None:
            self.authenticate()
        try:
            created = self.docs_service.documents().create(body={
                "title": (
                    f"Teacher Companion — "
                    f"{package.dashboard.lesson_title}"
                )
            }).execute()
        except HttpError as error:
            if (
                error.resp.status == 403
                and b"SERVICE_DISABLED" in error.content
            ):
                return self._publish_via_drive_import(package)
            raise
        document_id = created["documentId"]
        text, _ = self.document_text(package)
        self.docs_service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": self.build_requests(package)},
        ).execute()
        marker_start = text.index(self.AGENDA_MARKER) + 1
        marker_end = marker_start + len(self.AGENDA_MARKER)
        self.docs_service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": marker_start,
                            "endIndex": marker_end,
                        }
                    }
                },
                {
                    "insertTable": {
                        "rows": len(package.agenda) + 1,
                        "columns": 5,
                        "location": {"index": marker_start},
                    }
                },
                {
                    "updateTableCellStyle": {
                        "tableStartLocation": {"index": marker_start},
                        "tableRange": {
                            "tableCellLocation": {
                                "rowIndex": 0,
                                "columnIndex": 0,
                            },
                            "rowSpan": 1,
                            "columnSpan": 5,
                        },
                        "tableCellStyle": {
                            "backgroundColor": {
                                "color": {
                                    "rgbColor": {
                                        "red": .09,
                                        "green": .20,
                                        "blue": .30,
                                    }
                                }
                            }
                        },
                        "fields": "backgroundColor",
                    }
                },
            ]},
        ).execute()
        document = self.docs_service.documents().get(
            documentId=document_id
        ).execute()
        cell_indices = self._table_cell_indices(document, marker_start)
        values = [[
            "Order", "Lesson stage", "Student focus", "Time", "Materials"
        ]]
        values.extend([
            [
                str(item.official_order),
                item.official_title.text,
                item.student_friendly_title.text,
                (
                    str(item.duration_minutes)
                    if item.duration_minutes is not None
                    else "—"
                ),
                ", ".join(item.materials) or "—",
            ]
            for item in package.agenda
        ])
        inserts = []
        for index, value in zip(cell_indices, sum(values, [])):
            inserts.append({
                "insertText": {
                    "location": {"index": index},
                    "text": value,
                }
            })
        if inserts:
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={"requests": list(reversed(inserts))},
            ).execute()
        return {
            "documentId": document_id,
            "url": f"https://docs.google.com/document/d/{document_id}/edit",
        }

    @staticmethod
    def _table_cell_indices(
        document: dict[str, Any], minimum_index: int
    ) -> list[int]:
        for element in document.get("body", {}).get("content", []):
            table = element.get("table")
            if table and element.get("startIndex", 0) >= minimum_index:
                return [
                    cell["content"][0]["startIndex"]
                    for row in table.get("tableRows", [])
                    for cell in row.get("tableCells", [])
                ]
        return []


__all__ = ["GoogleDocsPublisher"]
