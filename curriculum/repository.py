"""SQLite persistence for curriculum unit metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from schemas.curriculum_schema import CurriculumUnit


class CurriculumRepository:
    """Persist curriculum records without storing curriculum file contents."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS curriculum_units (
                    curriculum_name TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (curriculum_name, grade, unit)
                )
            """)

    def save(self, unit: CurriculumUnit) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO curriculum_units VALUES (?, ?, ?, ?)
                ON CONFLICT(curriculum_name, grade, unit) DO UPDATE SET payload=excluded.payload""",
                (unit.curriculum_name, unit.grade, unit.unit, unit.model_dump_json()),
            )

    def get(self, curriculum_name: str, grade: str, unit: str) -> CurriculumUnit | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM curriculum_units WHERE curriculum_name=? AND grade=? AND unit=?",
                (curriculum_name, grade, unit),
            ).fetchone()
        return CurriculumUnit.model_validate_json(row["payload"]) if row else None

    def list(self, curriculum_name: str | None = None) -> list[CurriculumUnit]:
        query, parameters = "SELECT payload FROM curriculum_units", ()
        if curriculum_name:
            query += " WHERE curriculum_name=?"
            parameters = (curriculum_name,)
        query += " ORDER BY curriculum_name, grade, unit"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [CurriculumUnit.model_validate_json(row["payload"]) for row in rows]

    def remove(self, curriculum_name: str, grade: str, unit: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM curriculum_units WHERE curriculum_name=? AND grade=? AND unit=?",
                (curriculum_name, grade, unit),
            )
        return cursor.rowcount > 0
