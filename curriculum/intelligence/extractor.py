"""Resource-versioned wrapper around the existing PDF extractor."""

from __future__ import annotations

import re
from pathlib import Path

from curriculum.intelligence.ids import file_checksum, stable_id
from curriculum.pdf_extractor import PDFTextExtractor
from schemas.curriculum_intelligence_schema import (
    ExtractionStatus,
    IndexingStatus,
    InstructionalResource,
    ResourcePage,
    SourceCoordinate,
)


EXTRACTION_VERSION = "pymupdf-page-text-v1"


def _headings(text: str) -> list[str]:
    values: list[str] = []
    for line in (item.strip() for item in text.splitlines()):
        if not line or len(line) > 140:
            continue
        words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", line)
        if not words:
            continue
        if (
            line.isupper()
            or re.fullmatch(r"(?:Lesson|Unit)\s+\d+", line, re.IGNORECASE)
            or len(words) <= 8
            and line.istitle()
        ):
            values.append(line)
        if len(values) == 8:
            break
    return list(dict.fromkeys(values))


class ResourceExtractor:
    def __init__(self, extractor: PDFTextExtractor | None = None) -> None:
        self.extractor = extractor or PDFTextExtractor()

    def extract(
        self,
        *,
        curriculum_id: str,
        resource_type: str,
        title: str,
        source_path: str | Path,
        document_labels: dict[int, str] | None = None,
        metadata: dict | None = None,
    ) -> tuple[InstructionalResource, list[ResourcePage]]:
        path = Path(source_path).expanduser().resolve()
        resource_id = stable_id(
            "resource", curriculum_id, resource_type, title
        )
        if not path.is_file():
            resource = InstructionalResource(
                id=resource_id,
                curriculum_id=curriculum_id,
                resource_type=resource_type,
                title=title,
                source_identity=str(path),
                checksum="unavailable",
                file_size=0,
                page_count=0,
                resource_version="unavailable",
                extraction_version=EXTRACTION_VERSION,
                extraction_status=ExtractionStatus.UNAVAILABLE,
                indexing_status=IndexingStatus.FAILED,
                warnings=[f"Source file is unavailable: {path}"],
                metadata=metadata or {},
            )
            return resource, []

        checksum = file_checksum(path)
        version = checksum[:16]
        pages = self.extractor.extract_pages(path)
        output: list[ResourcePage] = []
        for page in pages:
            confidence = (
                0.0
                if not page.normalized_text
                else 0.55
                if page.character_count < self.extractor.low_text_threshold
                else 1.0
            )
            output.append(ResourcePage(
                id=stable_id(
                    "page",
                    resource_id,
                    version,
                    page.pdf_page_number,
                ),
                resource_id=resource_id,
                source_version=version,
                pdf_page_number=page.pdf_page_number,
                display_page_number=page.display_page_number,
                printed_page_label=(
                    str(page.printed_page_number)
                    if page.printed_page_number is not None
                    else None
                ),
                document_page_label=(
                    (document_labels or {}).get(page.pdf_page_number)
                ),
                raw_text=page.raw_text,
                normalized_text=page.normalized_text,
                headings=_headings(page.normalized_text),
                text_blocks=[
                    SourceCoordinate(
                        x0=float(block["x0"]),
                        y0=float(block["y0"]),
                        x1=float(block["x1"]),
                        y1=float(block["y1"]),
                        text=str(block["text"]),
                    )
                    for block in page.metadata.get("blocks", [])
                ],
                extraction_method="pymupdf_text",
                extraction_version=EXTRACTION_VERSION,
                extraction_confidence=confidence,
                warnings=list(page.warnings),
            ))
        warnings = [
            f"PDF display page {page.display_page_number}: {warning}"
            for page in output
            for warning in page.warnings
        ]
        resource = InstructionalResource(
            id=resource_id,
            curriculum_id=curriculum_id,
            resource_type=resource_type,
            title=title,
            source_identity=str(path),
            checksum=checksum,
            file_size=path.stat().st_size,
            page_count=len(output),
            resource_version=version,
            extraction_version=EXTRACTION_VERSION,
            extraction_status=(
                ExtractionStatus.COMPLETED_WITH_WARNINGS
                if warnings
                else ExtractionStatus.COMPLETED
            ),
            indexing_status=IndexingStatus.INDEXED,
            warnings=warnings,
            metadata=metadata or {},
        )
        return resource, output


__all__ = ["EXTRACTION_VERSION", "ResourceExtractor"]
