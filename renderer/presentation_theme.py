"""Defensive loader for the deterministic presentation theme."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_THEME: dict[str, Any] = {
    "name": "grade_8_modern",
    "dimensions": {"aspect_ratio": "16:9", "width_inches": 13.333, "height_inches": 7.5},
    "typography": {"title_font": "Arial", "body_font": "Arial", "fallback_fonts": ["Roboto", "Verdana", "sans-serif"],
                   "title_size": 30, "subtitle_size": 22, "body_size": 20, "caption_size": 12, "minimum_body_size": 18},
    "colors": {"background": "#F7F5F0", "background_alternate": "#EAF1F5", "primary": "#17324D",
               "secondary": "#2D6A6A", "accent": "#D9822B", "text": "#18212B", "muted_text": "#5D6873"},
    "layout": {"margin_inches": .6, "spacing_inches": .25, "card_corner_radius_points": 10, "image_border_radius_points": 8},
    "content_limits": {"maximum_bullets": 3, "maximum_words_per_slide": 45, "minimum_font_size": 18},
    "attribution_footer": {"enabled": True, "font_size": 9, "position": "bottom", "style": "muted"},
}


def _merge(base: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    for key, value in supplied.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        elif value is not None:
            base[key] = value
    return base


def load_presentation_theme(path: str | Path | None = None) -> dict[str, Any]:
    """Load a partial theme over safe defaults; malformed files fall back fully."""
    target = Path(path) if path else Path(__file__).parents[1] / "config" / "presentation_theme.json"
    try:
        supplied = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(supplied, dict):
            raise ValueError("theme root must be an object")
        return _merge(deepcopy(DEFAULT_THEME), supplied)
    except (OSError, ValueError, json.JSONDecodeError):
        return deepcopy(DEFAULT_THEME)


def load_visual_theme(name: str = "warm_humanities", path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else Path(__file__).parents[1] / "config" / "presentation_themes.json"
    try:
        themes = json.loads(target.read_text(encoding="utf-8"))
        return themes.get(name, themes["modern_middle_school"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"primary":"#17324D","secondary":"#2D6A6A","accent":"#F2A65A","background":"#F7F9FC",
                "surface":"#FFFFFF","heading_font":"Arial","body_font":"Arial","radius":12}
