"""Curriculum adapter registration and selection."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from curriculum.adapters.base import CurriculumAdapter
from curriculum.adapters.ckla import CKLAAdapter


AdapterFactory = Callable[[Path], CurriculumAdapter]


class CurriculumAdapterRegistry:
    """Select provider behavior without coupling TeacherOS to an adapter."""

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(
        self,
        curriculum_name: str,
        factory: AdapterFactory,
    ) -> None:
        key = curriculum_name.strip().casefold()
        if not key:
            raise ValueError("curriculum adapter name may not be empty")
        self._factories[key] = factory

    def create(
        self,
        curriculum_name: str,
        *,
        index_directory: str | Path,
    ) -> CurriculumAdapter:
        key = curriculum_name.strip().casefold()
        factory = self._factories.get(key)
        if factory is None:
            raise KeyError(
                f"No curriculum adapter registered for: {curriculum_name}"
            )
        adapter = factory(Path(index_directory))
        if not adapter.supports(curriculum_name):
            raise ValueError(
                "Selected curriculum adapter does not support "
                f"{curriculum_name}"
            )
        return adapter


def default_adapter_registry() -> CurriculumAdapterRegistry:
    registry = CurriculumAdapterRegistry()
    registry.register(
        "CKLA",
        lambda index_directory: CKLAAdapter(
            index_directory=index_directory
        ),
    )
    return registry


__all__ = [
    "AdapterFactory",
    "CurriculumAdapterRegistry",
    "default_adapter_registry",
]
