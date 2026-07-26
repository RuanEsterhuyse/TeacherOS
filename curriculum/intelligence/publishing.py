"""Safe metadata helpers for optional Google publishing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_publishing_metadata(
    output_directory: str | Path,
    *,
    google_doc: dict[str, Any] | None = None,
    google_slides: dict[str, Any] | None = None,
) -> Path:
    """Persist only public document identities and URLs, never credentials."""
    path = Path(output_directory) / "publishing_metadata.json"
    payload: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                for key in ("google_doc", "google_slides"):
                    value = existing.get(key)
                    if isinstance(value, dict):
                        payload[key] = {
                            item: value[item]
                            for item in (
                                "documentId", "presentationId", "url"
                            )
                            if item in value
                        }
        except (OSError, ValueError):
            payload = {}
    if google_doc:
        payload["google_doc"] = {
            key: google_doc[key]
            for key in ("documentId", "url")
            if key in google_doc
        }
    if google_slides:
        payload["google_slides"] = {
            key: google_slides[key]
            for key in ("presentationId", "url")
            if key in google_slides
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = ["write_publishing_metadata"]
