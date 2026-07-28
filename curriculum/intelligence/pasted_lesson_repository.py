"""Isolated JSON persistence for teacher-pasted lesson runtime artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from curriculum.intelligence.ids import content_digest, stable_id
from schemas.pasted_lesson_schema import (
    PASTED_LESSON_SCHEMA_VERSION,
    PastedLessonSource,
    TeacherPlaybook,
    utc_now,
)
from schemas.playbook_enrichment_schema import (
    ApprovedPlaybookEnrichment,
    TeacherApprovalStatus,
)
from schemas.presentation_spec_schema import (
    ApprovalStatus,
    PresentationSpec,
    ValidationStatus,
)


SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


def create_pasted_lesson_source(
    *,
    grade: str,
    unit: str,
    lesson_number: int,
    lesson_title: str,
    teacher_guide_text: str,
    teacher_guide_page_start: int | None = None,
    teacher_guide_page_end: int | None = None,
    student_reader_text: str | None = None,
    activity_book_text: str | None = None,
    source_notes: str | None = None,
) -> PastedLessonSource:
    """Create a stable identity from source identity and exact pasted text."""
    basis: dict[str, Any] = {
        "grade": str(grade),
        "unit": str(unit),
        "lesson_number": lesson_number,
        "lesson_title": lesson_title,
        "teacher_guide_page_start": teacher_guide_page_start,
        "teacher_guide_page_end": teacher_guide_page_end,
        "teacher_guide_text": teacher_guide_text,
        "student_reader_text": student_reader_text,
        "activity_book_text": activity_book_text,
        "source_notes": source_notes,
        "schema_version": PASTED_LESSON_SCHEMA_VERSION,
    }
    source_id = stable_id(
        "pasted-lesson-source",
        str(grade),
        str(unit),
        str(lesson_number),
        content_digest(basis),
    )
    return PastedLessonSource(source_id=source_id, **basis)


class PastedLessonRepository:
    """Save strict JSON artifacts without touching curriculum persistence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.sources_directory = self.root / "sources"
        self.playbooks_directory = self.root / "playbooks"
        self.enriched_playbooks_directory = self.root / "enriched_playbooks"
        self.presentation_specs_directory = self.root / "presentation_specs"
        self.sources_directory.mkdir(parents=True, exist_ok=True)
        self.playbooks_directory.mkdir(parents=True, exist_ok=True)
        self.enriched_playbooks_directory.mkdir(parents=True, exist_ok=True)
        self.presentation_specs_directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_id(value: str) -> str:
        if not SAFE_ID.fullmatch(value):
            raise ValueError(f"Invalid artifact identifier: {value!r}")
        return value

    def _source_path(self, source_id: str) -> Path:
        return self.sources_directory / (
            self._validate_id(source_id) + ".json"
        )

    def _playbook_path(self, playbook_id: str) -> Path:
        return self.playbooks_directory / (
            self._validate_id(playbook_id) + ".json"
        )

    def _enriched_playbook_path(self, enrichment_id: str) -> Path:
        return self.enriched_playbooks_directory / (
            self._validate_id(enrichment_id) + ".json"
        )

    def _presentation_spec_path(self, presentation_id: str) -> Path:
        return self.presentation_specs_directory / (
            self._validate_id(presentation_id) + ".json"
        )

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(
                    payload,
                    stream,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                stream.write("\n")
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _read(path: Path, model_type):
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            return model_type.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, ValueError) as error:
            raise ValueError(f"Malformed saved artifact: {path.name}") from error

    def save_source(
        self, source: PastedLessonSource
    ) -> PastedLessonSource:
        path = self._source_path(source.source_id)
        if path.is_file():
            existing = self._read(path, PastedLessonSource)
            if (
                existing.teacher_guide_text
                != source.teacher_guide_text
            ):
                raise ValueError(
                    "A stable source ID cannot be reused for different text."
                )
            source = source.model_copy(update={
                "created_at": existing.created_at,
                "updated_at": utc_now(),
            })
        self._write(path, source.model_dump(mode="json"))
        return source

    def load_source(self, source_id: str) -> PastedLessonSource:
        return self._read(
            self._source_path(source_id), PastedLessonSource
        )

    def list_sources(self) -> list[PastedLessonSource]:
        return [
            self._read(path, PastedLessonSource)
            for path in sorted(self.sources_directory.glob("*.json"))
        ]

    def save_playbook(
        self, playbook: TeacherPlaybook
    ) -> TeacherPlaybook:
        source = self.load_source(playbook.source_id)
        if source.source_id != playbook.source_id:
            raise ValueError("Playbook source association is invalid.")
        self._write(
            self._playbook_path(playbook.playbook_id),
            playbook.model_dump(mode="json"),
        )
        return playbook

    def load_playbook(self, playbook_id: str) -> TeacherPlaybook:
        return self._read(
            self._playbook_path(playbook_id), TeacherPlaybook
        )

    def list_playbooks(self) -> list[TeacherPlaybook]:
        return [
            self._read(path, TeacherPlaybook)
            for path in sorted(self.playbooks_directory.glob("*.json"))
        ]

    def save_approved_enrichment(
        self, enrichment: ApprovedPlaybookEnrichment
    ) -> ApprovedPlaybookEnrichment:
        if (
            enrichment.teacher_approval_status
            != TeacherApprovalStatus.approved
        ):
            raise ValueError("Only teacher-approved enrichments may be saved.")
        source = self.load_source(enrichment.source_id)
        if enrichment.enriched_playbook.source_id != source.source_id:
            raise ValueError("Enrichment source association is invalid.")
        self._write(
            self._enriched_playbook_path(enrichment.enrichment_id),
            enrichment.model_dump(mode="json"),
        )
        return enrichment

    def load_approved_enrichment(
        self, enrichment_id: str
    ) -> ApprovedPlaybookEnrichment:
        return self._read(
            self._enriched_playbook_path(enrichment_id),
            ApprovedPlaybookEnrichment,
        )

    def list_approved_enrichments(
        self,
    ) -> list[ApprovedPlaybookEnrichment]:
        return [
            self._read(path, ApprovedPlaybookEnrichment)
            for path in sorted(
                self.enriched_playbooks_directory.glob("*.json")
            )
        ]

    def save_presentation_spec(
        self, spec: PresentationSpec
    ) -> PresentationSpec:
        if spec.approval_status != ApprovalStatus.approved:
            raise ValueError(
                "Only teacher-approved presentation specifications may be saved."
            )
        if spec.validation_status not in {
            ValidationStatus.passed,
            ValidationStatus.passed_with_warnings,
        }:
            raise ValueError(
                "Only validated presentation specifications may be saved."
            )
        enrichment = self.load_approved_enrichment(
            spec.approved_enrichment_id
        )
        if (
            enrichment.teacher_approval_status
            != TeacherApprovalStatus.approved
            or enrichment.enriched_playbook.playbook_id != spec.playbook_id
            or enrichment.source_id != spec.source_id
        ):
            raise ValueError(
                "Presentation specification association is invalid."
            )
        self._write(
            self._presentation_spec_path(spec.presentation_id),
            spec.model_dump(mode="json"),
        )
        return spec

    def load_presentation_spec(
        self, presentation_id: str
    ) -> PresentationSpec:
        return self._read(
            self._presentation_spec_path(presentation_id),
            PresentationSpec,
        )

    def list_presentation_specs(self) -> list[PresentationSpec]:
        return [
            self._read(path, PresentationSpec)
            for path in sorted(
                self.presentation_specs_directory.glob("*.json")
            )
        ]


__all__ = [
    "PastedLessonRepository",
    "create_pasted_lesson_source",
]
