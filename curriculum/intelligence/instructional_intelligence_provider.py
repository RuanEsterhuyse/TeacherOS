"""Provider abstraction for isolated instructional-intelligence generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from config.settings import Settings, get_settings
from schemas.phase_teacher_support_schema import (
    GeneratedPhaseTeacherSupport,
    PhaseTeacherSupportContext,
)
from services.openai_client import OpenAIClient


@dataclass(frozen=True)
class InstructionalIntelligenceProviderResponse:
    raw_payload: Any
    retry_count: int = 0
    usage: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class InstructionalIntelligenceProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def generate_phase_teacher_support(
        self,
        context: PhaseTeacherSupportContext,
        prompt_contract: str,
    ) -> InstructionalIntelligenceProviderResponse:
        ...


class OpenAIInstructionalIntelligenceProvider:
    """Optional live provider using the project's existing settings."""

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

    def generate_phase_teacher_support(
        self,
        context: PhaseTeacherSupportContext,
        prompt_contract: str,
    ) -> InstructionalIntelligenceProviderResponse:
        generated = self.client.generate(
            schema=GeneratedPhaseTeacherSupport,
            instructions=prompt_contract,
            input_data=context,
        )
        return InstructionalIntelligenceProviderResponse(
            raw_payload=generated.model_dump(mode="json"),
            retry_count=0,
            usage=dict(self.client.last_usage),
        )


__all__ = [
    "InstructionalIntelligenceProvider",
    "InstructionalIntelligenceProviderResponse",
    "OpenAIInstructionalIntelligenceProvider",
]
