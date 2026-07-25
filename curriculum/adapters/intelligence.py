"""Optional adapter contract for source-intelligence translation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CurriculumIntelligenceAdapter(ABC):
    adapter_id: str
    adapter_version: str

    @abstractmethod
    def build_source_lesson(self, **inputs: Any) -> Any:
        """Translate publisher source conventions into generic records."""


__all__ = ["CurriculumIntelligenceAdapter"]
