"""Load renderer prompt themes without coupling them to a renderer."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from renderer.presentation_theme import DEFAULT_THEME


class LoadedTheme(BaseModel):
    """Normalized theme data plus non-fatal loading warnings."""

    name: str
    settings: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


def _merge(base: dict[str, Any], supplied: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in supplied.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        elif value is not None:
            base[key] = deepcopy(value)
    return base


def _from_mapping(value: Mapping[str, Any]) -> LoadedTheme:
    settings = _merge(deepcopy(DEFAULT_THEME), value)
    name = str(settings.get("name") or "grade_8_modern")
    settings["name"] = name
    return LoadedTheme(name=name, settings=settings)


def load_prompt_theme(
    theme: Mapping[str, Any] | str | Path | None = None,
    *,
    default_path: str | Path | None = None,
) -> LoadedTheme:
    """Load a mapping or JSON theme over deterministic classroom-safe defaults."""
    if isinstance(theme, Mapping):
        return _from_mapping(theme)

    configured_default = Path(default_path) if default_path else (
        Path(__file__).parents[1] / "config" / "presentation_theme.json"
    )
    target = Path(theme) if theme is not None else configured_default
    try:
        supplied = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(supplied, dict):
            raise ValueError("theme root must be an object")
        return _from_mapping(supplied)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        fallback = _from_mapping({})
        fallback.warnings.append(
            f"Presentation theme could not be loaded from {target}; defaults were used: {error}"
        )
        return fallback


__all__ = ["LoadedTheme", "load_prompt_theme"]
