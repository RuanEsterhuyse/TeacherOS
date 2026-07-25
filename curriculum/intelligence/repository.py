"""SQLite persistence for source intelligence records.

The existing ``curriculum_units`` compatibility table is never altered.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel

from schemas.curriculum_intelligence_schema import (
    BuildManifest,
    Curriculum,
    CurriculumLesson,
    CurriculumUnit,
    InstructionalResource,
    ReadinessReport,
    ResourceAssignment,
    ResourcePage,
    SourceCoordinateMapping,
    TextSegment,
)


T = TypeVar("T", bound=BaseModel)


class CurriculumIntelligenceRepository:
    TABLES = {
        "ci_curricula": Curriculum,
        "ci_units": CurriculumUnit,
        "ci_resources": InstructionalResource,
        "ci_resource_pages": ResourcePage,
        "ci_lessons": CurriculumLesson,
        "ci_assignments": ResourceAssignment,
        "ci_coordinate_mappings": SourceCoordinateMapping,
        "ci_text_segments": TextSegment,
        "ci_readiness": ReadinessReport,
        "ci_build_manifests": BuildManifest,
    }

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        statements = {
            "ci_curricula": """
                CREATE TABLE IF NOT EXISTS ci_curricula (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL
                )""",
            "ci_units": """
                CREATE TABLE IF NOT EXISTS ci_units (
                    id TEXT PRIMARY KEY, curriculum_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                )""",
            "ci_resources": """
                CREATE TABLE IF NOT EXISTS ci_resources (
                    id TEXT PRIMARY KEY, curriculum_id TEXT NOT NULL,
                    checksum TEXT NOT NULL, resource_version TEXT NOT NULL,
                    payload TEXT NOT NULL
                )""",
            "ci_resource_pages": """
                CREATE TABLE IF NOT EXISTS ci_resource_pages (
                    id TEXT PRIMARY KEY, resource_id TEXT NOT NULL,
                    pdf_page_number INTEGER NOT NULL,
                    display_page_number INTEGER NOT NULL,
                    printed_page_label TEXT, document_page_label TEXT,
                    payload TEXT NOT NULL
                )""",
            "ci_lessons": """
                CREATE TABLE IF NOT EXISTS ci_lessons (
                    id TEXT PRIMARY KEY, curriculum_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )""",
            "ci_assignments": """
                CREATE TABLE IF NOT EXISTS ci_assignments (
                    id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL, assignment_type TEXT NOT NULL,
                    resolution_status TEXT NOT NULL, payload TEXT NOT NULL
                )""",
            "ci_coordinate_mappings": """
                CREATE TABLE IF NOT EXISTS ci_coordinate_mappings (
                    id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL, resource_id TEXT NOT NULL,
                    review_status TEXT NOT NULL, resource_checksum TEXT NOT NULL,
                    payload TEXT NOT NULL
                )""",
            "ci_text_segments": """
                CREATE TABLE IF NOT EXISTS ci_text_segments (
                    id TEXT PRIMARY KEY, resource_id TEXT NOT NULL,
                    title TEXT NOT NULL, segment_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                )""",
            "ci_readiness": """
                CREATE TABLE IF NOT EXISTS ci_readiness (
                    lesson_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    payload TEXT NOT NULL
                )""",
            "ci_build_manifests": """
                CREATE TABLE IF NOT EXISTS ci_build_manifests (
                    build_id TEXT PRIMARY KEY, curriculum_id TEXT NOT NULL,
                    lesson_id TEXT NOT NULL, snapshot_digest TEXT NOT NULL,
                    payload TEXT NOT NULL
                )""",
        }
        with self._connect() as connection:
            for statement in statements.values():
                connection.execute(statement)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ci_pages_resource "
                "ON ci_resource_pages(resource_id, pdf_page_number)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ci_assignments_lesson "
                "ON ci_assignments(lesson_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ci_mappings_assignment "
                "ON ci_coordinate_mappings(assignment_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ci_segments_resource "
                "ON ci_text_segments(resource_id)"
            )

    def resource_checksum(self, resource_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT checksum FROM ci_resources WHERE id=?",
                (resource_id,),
            ).fetchone()
        return str(row["checksum"]) if row else None

    def save_curriculum(self, value: Curriculum) -> None:
        self._save("ci_curricula", value, (value.id,))

    def save_unit(self, value: CurriculumUnit) -> None:
        self._save("ci_units", value, (value.id, value.curriculum_id))

    def save_resource(self, value: InstructionalResource) -> None:
        self._save(
            "ci_resources",
            value,
            (
                value.id,
                value.curriculum_id,
                value.checksum,
                value.resource_version,
            ),
        )

    def replace_pages(
        self, resource_id: str, values: Iterable[ResourcePage]
    ) -> None:
        values = list(values)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM ci_resource_pages WHERE resource_id=?",
                (resource_id,),
            )
            connection.executemany(
                "INSERT INTO ci_resource_pages VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        value.id,
                        value.resource_id,
                        value.pdf_page_number,
                        value.display_page_number,
                        value.printed_page_label,
                        value.document_page_label,
                        value.model_dump_json(),
                    )
                    for value in values
                ],
            )

    def save_lesson(self, value: CurriculumLesson) -> None:
        self._save(
            "ci_lessons",
            value,
            (
                value.id,
                value.curriculum_id,
                value.unit_id,
                value.sequence,
            ),
        )

    def replace_assignments(
        self, lesson_id: str, values: Iterable[ResourceAssignment]
    ) -> None:
        values = list(values)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM ci_assignments WHERE lesson_id=?",
                (lesson_id,),
            )
            connection.executemany(
                "INSERT INTO ci_assignments VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        value.id,
                        value.lesson_id,
                        value.resource_id,
                        value.assignment_type,
                        value.resolution_status,
                        value.model_dump_json(),
                    )
                    for value in values
                ],
            )

    def replace_segments(
        self, resource_ids: Iterable[str], values: Iterable[TextSegment]
    ) -> None:
        resource_ids = list(dict.fromkeys(resource_ids))
        values = list(values)
        with self._connect() as connection:
            for resource_id in resource_ids:
                connection.execute(
                    "DELETE FROM ci_text_segments WHERE resource_id=?",
                    (resource_id,),
                )
            connection.executemany(
                "INSERT INTO ci_text_segments VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        value.id,
                        value.resource_id,
                        value.title,
                        value.segment_type,
                        value.model_dump_json(),
                    )
                    for value in values
                ],
            )

    def replace_coordinate_mappings(
        self,
        lesson_id: str,
        values: Iterable[SourceCoordinateMapping],
    ) -> None:
        values = list(values)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM ci_coordinate_mappings WHERE lesson_id=?",
                (lesson_id,),
            )
            connection.executemany(
                "INSERT INTO ci_coordinate_mappings VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        value.id,
                        value.lesson_id,
                        value.assignment_id,
                        value.resource_id,
                        value.review_status,
                        value.resource_checksum,
                        value.model_dump_json(),
                    )
                    for value in values
                ],
            )

    def save_readiness(self, value: ReadinessReport) -> None:
        self._save(
            "ci_readiness", value, (value.lesson_id, value.state)
        )

    def save_build_manifest(self, value: BuildManifest) -> None:
        self._save(
            "ci_build_manifests",
            value,
            (
                value.build_id,
                value.curriculum_id,
                value.lesson_id,
                value.snapshot_digest,
            ),
        )

    def _save(self, table: str, value: BaseModel, columns: tuple) -> None:
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        with self._connect() as connection:
            connection.execute(
                f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})",
                (*columns, value.model_dump_json()),
            )

    def count(self, table: str) -> int:
        if table not in self.TABLES:
            raise ValueError(f"Unknown intelligence table: {table}")
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            ).fetchone()
        return int(row["count"])


__all__ = ["CurriculumIntelligenceRepository"]
