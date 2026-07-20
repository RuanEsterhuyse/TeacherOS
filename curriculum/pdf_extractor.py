"""Page-preserving PDF text extraction using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from schemas.curriculum_schema import PdfPage


class PDFTextExtractor:
    """Extract usable text without OCR or content rewriting."""

    def __init__(self, low_text_threshold: int = 40) -> None:
        self.low_text_threshold = low_text_threshold

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize inline whitespace while preserving line boundaries/headings."""
        lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        output: list[str] = []
        for line in lines:
            if line or (output and output[-1]):
                output.append(line)
        return "\n".join(output).strip()

    @staticmethod
    def _printed_page(text: str) -> int | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[-4:] + lines[:2]:
            match = re.fullmatch(r"(?:page\s+)?(\d{1,4})", line, re.IGNORECASE)
            if match and int(match.group(1)) > 0:
                return int(match.group(1))
            # CKLA merges its running footer into one extracted line. Odd and
            # even pages place the printed number at opposite ends.
            match = re.search(r"^(\d{1,4})\s+Unit\s+\d+\b|\bUnit\s+\d+\s+(\d{1,4})$", line)
            if match:
                return int(match.group(1) or match.group(2))
        return None

    def extract_pages(self, pdf_path: str | Path) -> list[PdfPage]:
        path = Path(pdf_path)
        if not path.is_file():
            raise FileNotFoundError(f"Teacher Guide PDF not found: {path}")
        pages: list[PdfPage] = []
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    raise ValueError(f"Teacher Guide PDF is password protected: {path}")
                for number, page in enumerate(document):
                    raw = page.get_text("text", sort=True)
                    normalized = self.normalize_text(raw)
                    count = len(normalized)
                    warnings: list[str] = []
                    if count == 0:
                        warnings.append("No extractable text; page may be scanned or blank (OCR not attempted).")
                    elif count < self.low_text_threshold:
                        warnings.append("Very little extractable text; page may be scanned, graphical, or blank.")
                    blocks = [
                        {"x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3], "text": self.normalize_text(b[4])}
                        for b in page.get_text("blocks", sort=True) if len(b) >= 5 and str(b[4]).strip()
                    ]
                    pages.append(PdfPage(
                        pdf_page_number=number, display_page_number=number + 1,
                        printed_page_number=self._printed_page(normalized), raw_text=raw,
                        normalized_text=normalized, character_count=count, warnings=warnings,
                        metadata={"width": page.rect.width, "height": page.rect.height, "blocks": blocks},
                    ))
        except fitz.FileDataError as error:
            raise ValueError(f"Unable to read PDF {path}: {error}") from error
        return pages

    def extract(self, pdf_path: str | Path) -> list[PdfPage]:
        """Compatibility alias for page-structured extraction."""
        return self.extract_pages(pdf_path)
