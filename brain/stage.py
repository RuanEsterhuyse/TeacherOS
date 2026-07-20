"""Common behavior for prompt-backed generation stages."""

from __future__ import annotations

from pathlib import Path
from typing import Generic, TypeVar
from pydantic import BaseModel
from services.openai_client import OpenAIClient

T = TypeVar("T", bound=BaseModel)


class GenerationStage(Generic[T]):
    schema: type[T]
    prompt_filename: str

    def __init__(self, client: OpenAIClient, prompt_directory: Path | None = None) -> None:
        self.client = client
        self.prompt_directory = prompt_directory or Path(__file__).parent / "prompts"

    def load_prompt(self) -> str:
        path = self.prompt_directory / self.prompt_filename
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Prompt is empty: {path}")
        return text

    def run(self, input_data):
        return self.client.generate(schema=self.schema, instructions=self.load_prompt(), input_data=input_data)
