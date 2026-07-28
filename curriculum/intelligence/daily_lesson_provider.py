"""Provider-neutral boundary for the optional Daily Lesson Generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from config.settings import Settings, get_settings
from schemas.daily_lesson_schema import (
    DailyPlaybookContext,
    DailySlideContext,
    GeneratedDailyPlaybook,
    GeneratedDailySlideOutline,
)
from services.openai_client import OpenAIClient


@dataclass(frozen=True)
class DailyProviderResponse:
    raw_payload: Any
    usage: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DailyLessonProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate_playbook(
        self, context: DailyPlaybookContext, prompt_contract: str
    ) -> DailyProviderResponse: ...

    def generate_slide_outline(
        self, context: DailySlideContext, prompt_contract: str
    ) -> DailyProviderResponse: ...


class OpenAIDailyLessonProvider:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: OpenAIClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or OpenAIClient(settings=self.settings)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.settings.teacheros_model

    def generate_playbook(
        self, context: DailyPlaybookContext, prompt_contract: str
    ) -> DailyProviderResponse:
        result = self.client.generate(
            schema=GeneratedDailyPlaybook,
            instructions=prompt_contract,
            input_data=context,
        )
        return DailyProviderResponse(
            result.model_dump(mode="json"), dict(self.client.last_usage)
        )

    def generate_slide_outline(
        self, context: DailySlideContext, prompt_contract: str
    ) -> DailyProviderResponse:
        result = self.client.generate(
            schema=GeneratedDailySlideOutline,
            instructions=prompt_contract,
            input_data=context,
        )
        return DailyProviderResponse(
            result.model_dump(mode="json"), dict(self.client.last_usage)
        )


__all__ = [
    "DailyLessonProvider",
    "DailyProviderResponse",
    "OpenAIDailyLessonProvider",
]
