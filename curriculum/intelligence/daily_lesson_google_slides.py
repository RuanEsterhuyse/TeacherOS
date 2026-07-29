"""Persist opt-in Google Slides artifacts for saved Daily Lesson packages."""

from __future__ import annotations

from typing import Any

from google.auth.exceptions import RefreshError

from curriculum.intelligence.daily_lesson_repository import (
    DailyLessonRepository,
)
from renderer.daily_lesson_google_slides import (
    DailyLessonGoogleSlidesRenderer,
)
from schemas.daily_lesson_schema import DailyGoogleSlidesArtifact


class DailyLessonGoogleSlidesPublisher:
    def __init__(
        self,
        repository: DailyLessonRepository,
        *,
        renderer: DailyLessonGoogleSlidesRenderer | None = None,
    ) -> None:
        self.repository = repository
        self.renderer = renderer or DailyLessonGoogleSlidesRenderer()

    def publish(self, package_id: str) -> dict[str, Any]:
        try:
            package = self.repository.load(package_id)
        except FileNotFoundError as error:
            raise ValueError(
                "The saved daily lesson package was not found."
            ) from error
        if not package.slide_outline:
            raise ValueError(
                "The saved daily package has no slide outline."
            )
        try:
            result = self.renderer.create_daily_presentation(package)
        except FileNotFoundError as error:
            raise ValueError(
                "Google OAuth client credentials are missing. "
                "Add credentials.json and authorize Google Slides."
            ) from error
        except RefreshError as error:
            raise ValueError(
                "Google OAuth authorization is missing or revoked. "
                "Reauthorize TeacherOS."
            ) from error
        artifact = DailyGoogleSlidesArtifact(
            presentation_id=result["presentation_id"],
            presentation_url=result["presentation_url"],
            title=result["title"],
            slide_count=result["slide_count"],
            warnings=result["warnings"],
        )
        updated = package.model_copy(update={"google_slides": artifact})
        try:
            self.repository.save(updated)
        except Exception:
            self.renderer._cleanup(artifact.presentation_id)
            raise
        return result


__all__ = ["DailyLessonGoogleSlidesPublisher"]
