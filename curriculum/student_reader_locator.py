"""Deterministic printed-page mapping for Student Reader PDFs."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from curriculum.pdf_extractor import PDFTextExtractor
from schemas.curriculum_schema import CurriculumUnit, LessonIndexEntry, PdfPage
from schemas.student_reader_source_schema import (
    StudentReaderPageSource,
    StudentReaderSource,
)


PAGE_REFERENCE_RE = re.compile(
    r"^\s*([ivxlcdm]+|\d{1,4})(?:\s*[-–—]\s*([ivxlcdm]+|\d{1,4}))?\s*$",
    re.IGNORECASE,
)
PRINTED_LABEL_RE = re.compile(
    r"^(?:page\s+)?([ivxlcdm]+|\d{1,4})$",
    re.IGNORECASE,
)


def _roman_to_int(value: str) -> int:
    numerals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    previous = 0
    for character in reversed(value.casefold()):
        current = numerals[character]
        total += -current if current < previous else current
        previous = max(previous, current)
    return total


def _is_roman(value: str) -> bool:
    return bool(value) and not value.isdigit()


def _canonical_label(value: str) -> str:
    return value.casefold() if _is_roman(value) else str(int(value))


def _expand_reference(reference: str) -> list[str]:
    match = PAGE_REFERENCE_RE.fullmatch(reference)
    if not match:
        return []
    start, end = match.group(1), match.group(2)
    if end is None:
        return [_canonical_label(start)]
    if _is_roman(start) != _is_roman(end):
        return []
    start_number = _roman_to_int(start) if _is_roman(start) else int(start)
    end_number = _roman_to_int(end) if _is_roman(end) else int(end)
    if end_number < start_number:
        return []
    if _is_roman(start):
        # Preserve explicit Roman labels when they appear in the source PDF.
        values = []
        current = start_number
        source_values = {
            _roman_to_int(item): item.casefold()
            for item in (start, end)
        }
        while current <= end_number:
            values.append(source_values.get(current, _int_to_roman(current)))
            current += 1
        return values
    return [str(value) for value in range(start_number, end_number + 1)]


def _int_to_roman(value: int) -> str:
    parts = (
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
        (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    )
    output = []
    for number, numeral in parts:
        while value >= number:
            output.append(numeral)
            value -= number
    return "".join(output)


def _page_label(page: PdfPage) -> str | None:
    if page.printed_page_number is not None:
        return str(page.printed_page_number)
    lines = [line.strip() for line in page.normalized_text.splitlines() if line.strip()]
    for line in lines[-4:] + lines[:2]:
        match = PRINTED_LABEL_RE.fullmatch(line)
        if match:
            return _canonical_label(match.group(1))
    return None


class StudentReaderLocator:
    """Map explicit Reader references without loading unrelated pages."""

    def __init__(self, extractor: PDFTextExtractor | None = None) -> None:
        self.extractor = extractor or PDFTextExtractor()

    @staticmethod
    def resolve_references(entry: LessonIndexEntry) -> list[str]:
        """Return the exact, ordered references already stored in the index."""
        return list(dict.fromkeys(
            reference.strip()
            for reference in entry.reader_pages
            if reference.strip()
        ))

    @staticmethod
    def _consistent_numeric_offset(
        explicit: dict[str, list[PdfPage]],
    ) -> int | None:
        offsets = {
            pages[0].pdf_page_number - int(label)
            for label, pages in explicit.items()
            if label.isdigit() and len(pages) == 1
        }
        numeric_anchors = sum(
            1 for label, pages in explicit.items()
            if label.isdigit() and len(pages) == 1
        )
        if numeric_anchors >= 2 and len(offsets) == 1:
            return offsets.pop()
        return None

    def retrieve(
        self,
        curriculum: CurriculumUnit,
        entry: LessonIndexEntry,
        reader_path: str | Path | None,
    ) -> StudentReaderSource:
        references = self.resolve_references(entry)
        base = {
            "curriculum_name": curriculum.curriculum_name,
            "grade": curriculum.grade,
            "unit": curriculum.unit,
            "lesson_number": entry.lesson_number,
            "source_document": str(reader_path) if reader_path else None,
            "requested_printed_page_references": references,
        }
        if not reader_path or not Path(reader_path).is_file():
            return StudentReaderSource(
                **base,
                source_available=False,
                extraction_status="unavailable",
                warnings=["Registered Student Reader file is unavailable."],
            )
        if not references:
            return StudentReaderSource(
                **base,
                source_available=True,
                extraction_status="failed",
                warnings=[
                    "Indexed lesson has no usable Student Reader page references."
                ],
            )

        try:
            pages = self.extractor.extract_pages(reader_path)
        except (OSError, ValueError) as error:
            return StudentReaderSource(
                **base,
                source_available=True,
                extraction_status="failed",
                warnings=[f"Registered Student Reader could not be read: {error}"],
            )
        explicit: dict[str, list[PdfPage]] = defaultdict(list)
        for page in pages:
            label = _page_label(page)
            if label:
                explicit[label].append(page)
        numeric_offset = self._consistent_numeric_offset(explicit)

        labels_to_references: dict[str, list[str]] = defaultdict(list)
        warnings: list[str] = []
        for reference in references:
            labels = _expand_reference(reference)
            if not labels:
                warnings.append(
                    f"Unsupported Student Reader page reference: {reference}."
                )
                continue
            for label in labels:
                labels_to_references[label].append(reference)

        matched: list[StudentReaderPageSource] = []
        for label, requested_by in labels_to_references.items():
            candidates = explicit.get(label, [])
            inferred = False
            if not candidates and label.isdigit() and numeric_offset is not None:
                pdf_page = int(label) + numeric_offset
                if 0 <= pdf_page < len(pages):
                    candidates = [pages[pdf_page]]
                    inferred = True
            if len(candidates) > 1:
                locations = ", ".join(
                    str(page.display_page_number) for page in candidates
                )
                warnings.append(
                    f"Printed Reader page {label} is ambiguous; it appears on "
                    f"PDF pages {locations}."
                )
                continue
            if not candidates:
                warnings.append(
                    f"Printed Reader page {label} could not be mapped to a PDF page."
                )
                continue
            page = candidates[0]
            page_warnings = list(page.warnings)
            if inferred:
                page_warnings.append(
                    "PDF page inferred from a consistent printed-page offset."
                )
            matched.append(StudentReaderPageSource(
                printed_page=label,
                pdf_page_number=page.pdf_page_number,
                display_pdf_page_number=page.display_page_number,
                extracted_text=page.normalized_text,
                requested_by=list(dict.fromkeys(requested_by)),
                warnings=page_warnings,
            ))

        matched.sort(key=lambda item: item.pdf_page_number)
        requested_count = len(labels_to_references)
        matched_count = len(matched)
        if matched_count == requested_count and not warnings:
            status = "completed"
        elif matched_count == requested_count:
            status = "completed_with_warnings"
        elif matched_count:
            status = "partial"
        else:
            status = "failed"
        return StudentReaderSource(
            **base,
            source_available=True,
            matched_pdf_page_numbers=[
                page.pdf_page_number for page in matched
            ],
            pages=matched,
            warnings=list(dict.fromkeys(warnings)),
            extraction_status=status,
        )


__all__ = ["StudentReaderLocator"]
