"""Environment-backed settings for instructional generation."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    openai_api_key: Optional[str] = None
    teacheros_model: str = Field(default="gpt-5-mini", min_length=1)

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            teacheros_model=os.getenv("TEACHEROS_MODEL", "gpt-5-mini").strip(),
        )

    def require_api_key(self) -> str:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for live lesson generation")
        return self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
