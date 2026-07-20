"""Small, mockable adapter around OpenAI Responses structured outputs."""

from __future__ import annotations

import json
from typing import Any, TypeVar
from pydantic import BaseModel
from config.settings import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class OpenAIClient:
    def __init__(self, *, settings: Settings | None = None, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=self.settings.require_api_key())
        self.client = client
        self.last_usage: dict[str, Any] = {}

    def generate(self, *, schema: type[T], instructions: str, input_data: BaseModel | dict) -> T:
        payload = input_data.model_dump(mode="json") if isinstance(input_data, BaseModel) else input_data
        response = self.client.responses.parse(
            model=self.settings.teacheros_model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=schema,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI returned no structured output")
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.last_usage = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
        return schema.model_validate(parsed)
