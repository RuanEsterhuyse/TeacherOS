"""Provider-neutral boundary for optional playbook enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from config.settings import Settings, get_settings
from schemas.playbook_enrichment_schema import (
    GeneratedPlaybookEnrichment,
    PlaybookEnrichmentContext,
)
from services.openai_client import OpenAIClient


@dataclass(frozen=True)
class PlaybookEnrichmentProviderResponse:
    raw_payload: Any
    retry_count: int = 0
    usage: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PlaybookEnrichmentProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def enrich(
        self,
        context: PlaybookEnrichmentContext,
        prompt_contract: str,
    ) -> PlaybookEnrichmentProviderResponse: ...


class OpenAIPlaybookEnrichmentProvider:
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

    def enrich(
        self,
        context: PlaybookEnrichmentContext,
        prompt_contract: str,
    ) -> PlaybookEnrichmentProviderResponse:
        generated = self.client.generate(
            schema=GeneratedPlaybookEnrichment,
            instructions=prompt_contract,
            input_data=context,
        )
        return PlaybookEnrichmentProviderResponse(
            raw_payload=generated.model_dump(mode="json"),
            usage=dict(self.client.last_usage),
        )


__all__ = [
    "OpenAIPlaybookEnrichmentProvider",
    "PlaybookEnrichmentProvider",
    "PlaybookEnrichmentProviderResponse",
]
