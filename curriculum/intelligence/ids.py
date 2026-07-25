"""Stable identifiers and source checksums."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"


def stable_id(prefix: str, *parts: object) -> str:
    normalized = json.dumps(
        [str(part).strip() for part in parts],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    readable = slug(str(parts[-1]))[:36] if parts else "item"
    return f"{slug(prefix)}-{readable}-{digest}"


def file_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = ["content_digest", "file_checksum", "slug", "stable_id"]
