"""Provider-neutral boundary for the optional Daily Lesson Generator."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable
from urllib import error as urlerror
from urllib import request as urlrequest

from config.settings import Settings, get_settings
from schemas.daily_lesson_schema import (
    DailyPlaybookContext,
    DailySlideContext,
    GeneratedDailyPlaybook,
    GeneratedDailySlideOutline,
)
from services.openai_client import OpenAIClient


DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
DAILY_PROVIDER_ENVIRONMENT_VARIABLE = "TEACHEROS_DAILY_PROVIDER"
DAILY_PROVIDER_CONFIGURATION_ERROR = (
    "Configure GEMINI_API_KEY or OPENAI_API_KEY for live lesson generation."
)


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


GeminiTransport = Callable[
    [str, dict[str, Any], float, str], dict[str, Any]
]


def _gemini_http_transport(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    api_key: str,
) -> dict[str, Any]:
    request = urlrequest.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(
            request, timeout=timeout_seconds
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as error:
        raise TimeoutError("Gemini request timed out.") from error
    except urlerror.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError("Gemini request timed out.") from error
        raise ValueError("Gemini request failed.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Gemini returned malformed JSON.") from error


class GeminiDailyLessonProvider:
    """Gemini structured-output adapter with an injectable HTTP transport."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        transport: GeminiTransport | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY") or ""
        if not self._api_key:
            raise ValueError(DAILY_PROVIDER_CONFIGURATION_ERROR)
        self._model_name = (
            model_name
            or os.getenv("TEACHEROS_DAILY_GEMINI_MODEL")
            or DEFAULT_GEMINI_MODEL
        ).strip()
        self._transport = transport or _gemini_http_transport
        self._timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate(
        self,
        *,
        schema,
        context: DailyPlaybookContext | DailySlideContext,
        prompt_contract: str,
    ) -> DailyProviderResponse:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model_name}:generateContent"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": prompt_contract}],
            },
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": json.dumps(
                        context.model_dump(mode="json"),
                        ensure_ascii=False,
                    )
                }],
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema.model_json_schema(),
            },
        }
        response = self._transport(
            endpoint, payload, self._timeout_seconds, self._api_key
        )
        try:
            candidates = response["candidates"]
            text = candidates[0]["content"]["parts"][0]["text"]
            raw_payload = json.loads(text)
        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError(
                "Gemini returned a malformed structured response."
            ) from error
        usage = response.get("usageMetadata") or {}
        if not isinstance(usage, dict):
            usage = {}
        return DailyProviderResponse(
            raw_payload=raw_payload,
            usage=dict(usage),
        )

    def generate_playbook(
        self, context: DailyPlaybookContext, prompt_contract: str
    ) -> DailyProviderResponse:
        return self._generate(
            schema=GeneratedDailyPlaybook,
            context=context,
            prompt_contract=prompt_contract,
        )

    def generate_slide_outline(
        self, context: DailySlideContext, prompt_contract: str
    ) -> DailyProviderResponse:
        return self._generate(
            schema=GeneratedDailySlideOutline,
            context=context,
            prompt_contract=prompt_contract,
        )


def select_daily_lesson_provider(
    provider: DailyLessonProvider | None = None,
    *,
    configured_provider: str | None = None,
) -> DailyLessonProvider:
    """Select only the Daily workflow's live provider."""
    if provider is not None:
        return provider
    requested = (
        configured_provider
        if configured_provider is not None
        else os.getenv(DAILY_PROVIDER_ENVIRONMENT_VARIABLE, "")
    ).strip().casefold()
    if requested:
        if requested == "gemini":
            return GeminiDailyLessonProvider()
        if requested == "openai":
            settings = Settings.from_environment()
            if not settings.openai_api_key:
                raise ValueError(DAILY_PROVIDER_CONFIGURATION_ERROR)
            return OpenAIDailyLessonProvider(settings=settings)
        raise ValueError(
            "TEACHEROS_DAILY_PROVIDER must be 'gemini' or 'openai'."
        )
    if os.getenv("GEMINI_API_KEY"):
        return GeminiDailyLessonProvider()
    settings = Settings.from_environment()
    if settings.openai_api_key:
        return OpenAIDailyLessonProvider(settings=settings)
    raise ValueError(DAILY_PROVIDER_CONFIGURATION_ERROR)


__all__ = [
    "DAILY_PROVIDER_CONFIGURATION_ERROR",
    "DAILY_PROVIDER_ENVIRONMENT_VARIABLE",
    "DEFAULT_GEMINI_MODEL",
    "DailyLessonProvider",
    "DailyProviderResponse",
    "GeminiDailyLessonProvider",
    "OpenAIDailyLessonProvider",
    "select_daily_lesson_provider",
]
