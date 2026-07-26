"""Optional editable Google Docs publishing for Teacher Companions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from renderer.teaching_package_markdown import (
    TeacherCompanionMarkdownRenderer,
)
from schemas.teaching_package_schema import StructuredTeachingPackage


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
        """Convert local Markdown to clean text plus Docs heading ranges."""
        markdown = TeacherCompanionMarkdownRenderer().render(package)
        lines: list[str] = []
        headings: list[tuple[int, int, str]] = []
        cursor = 1
        inserted_agenda = False
        for source_line in markdown.splitlines():
            line = source_line
            style = ""
            if line.startswith("# "):
                line, style = line[2:], "TITLE"
            elif line.startswith("## "):
                line, style = line[3:], "HEADING_1"
            elif line.startswith("### "):
                line, style = line[4:], "HEADING_2"
            line = line.replace("**", "").replace("`", "")
            if line.startswith("|"):
                if not inserted_agenda:
                    line = self.AGENDA_MARKER
                    inserted_agenda = True
                else:
                    continue
            if line.startswith("> "):
                line = line[2:]
            start = cursor
            rendered = line + "\n"
            lines.append(rendered)
            cursor += len(rendered)
            if style and line:
                headings.append((start, cursor, style))
        return "".join(lines), headings

    def build_requests(
        self, package: StructuredTeachingPackage
    ) -> list[dict[str, Any]]:
        text, headings = self.document_text(package)
        requests: list[dict[str, Any]] = [{
            "insertText": {
                "location": {"index": 1},
                "text": text,
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
        return requests

    def publish(
        self, package: StructuredTeachingPackage
    ) -> dict[str, str]:
        if package.validation.status == "fail":
            raise ValueError("Cannot publish a failed teaching package.")
        if self.docs_service is None or self.drive_service is None:
            self.authenticate()
        created = self.docs_service.documents().create(body={
            "title": (
                f"Teacher Companion — {package.dashboard.lesson_title}"
            )
        }).execute()
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
            ]},
        ).execute()
        document = self.docs_service.documents().get(
            documentId=document_id
        ).execute()
        cell_indices = self._table_cell_indices(document, marker_start)
        values = [["Order", "Official title", "Student title", "Time", "Slides"]]
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
                ", ".join(item.slide_ids),
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
