"""Deterministic CKLA lesson boundary detection and index storage."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from curriculum.pdf_extractor import PDFTextExtractor
from curriculum.ckla_lesson_metadata import extract_ckla_lesson_metadata
from schemas.curriculum_schema import (
    CurriculumIndex, CurriculumUnit, LessonIndexEntry, LessonSource, PdfPage,
)


# A PDF font may map an en/em dash to a replacement question mark during
# extraction, so that character is accepted only in the separator position.
HEADING_RE = re.compile(r"^\s*LESSON\s+(\d{1,3})(?:\s*[:\-–—?]\s*(.+?))?\s*$", re.IGNORECASE)


@dataclass
class _Candidate:
    number: int
    page: PdfPage
    heading: str
    title: str | None
    offset: int
    score: float
    warnings: list[str]


class CKLALessonLocator:
    """Locate real lesson starts using heading, placement, context, and order signals."""

    def __init__(self, extractor: PDFTextExtractor | None = None, index_directory: str | Path = "data/indexes") -> None:
        self.extractor = extractor or PDFTextExtractor()
        self.index_directory = Path(index_directory)

    @staticmethod
    def _is_contents_page(page: PdfPage) -> bool:
        text = page.normalized_text
        first = "\n".join(text.splitlines()[:8])
        lesson_lines = len(re.findall(r"(?im)^\s*lesson\s+\d+", text))
        page_references = len(re.findall(r"(?im)^\s*lesson\s+\d+.*(?:\.{2,}|\s\d+\s*$)", text))
        has_contents_heading = bool(re.search(r"(?i)\b(table of )?contents\b", first))
        return (has_contents_heading and lesson_lines >= 2) or page_references >= 4

    @staticmethod
    def _position_signal(page: PdfPage, heading: str) -> bool:
        height = float(page.metadata.get("height", 0) or 0)
        for block in page.metadata.get("blocks", []):
            block_text = str(block.get("text", "")).strip()
            # A heading buried in a large body-text block is not a top-of-page
            # formatting signal even when that block itself begins near the top.
            if block_text.casefold().startswith(heading.casefold()):
                return height == 0 or float(block.get("y0", height)) <= height * 0.4
        return False

    def _candidates(self, pages: list[PdfPage]) -> list[_Candidate]:
        found: list[_Candidate] = []
        for page in pages:
            if self._is_contents_page(page):
                continue
            lines = page.normalized_text.splitlines()
            nonempty = [line for line in lines if line.strip()]
            for line_index, line in enumerate(lines):
                match = HEADING_RE.fullmatch(line)
                if not match:
                    continue
                number = int(match.group(1))
                offset = page.normalized_text.find(line)
                early = line in nonempty[:2]
                positioned = self._position_signal(page, line)
                title = match.group(2).strip() if match.group(2) else None
                if title is None:
                    following = [item.strip() for item in lines[line_index + 1:line_index + 4] if item.strip()]
                    if following and not HEADING_RE.fullmatch(following[0]) and len(following[0]) <= 160:
                        title = following[0]
                score = 0.48 + (0.18 if early else 0) + (0.14 if positioned else 0) + (0.1 if title else 0)
                warnings = []
                if not early and not positioned:
                    warnings.append("Lesson heading is not near the top of the page.")
                found.append(_Candidate(number, page, line.strip(), title, max(offset, 0), min(score, 0.9), warnings))
        return found

    @staticmethod
    def _read_overrides(override_file: str | Path | None) -> dict[int, dict[str, Any]]:
        if override_file is None:
            return {}
        path = Path(override_file)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Unable to read manual override file {path}: {error}") from error
        values = payload.get("lessons", payload)
        if isinstance(values, list):
            return {int(item["lesson_number"]): item for item in values}
        if isinstance(values, dict):
            return {int(number): value for number, value in values.items()}
        raise ValueError("Override JSON must contain a 'lessons' object or list.")

    def build_index(self, curriculum: CurriculumUnit, teacher_guide_path: str | Path | None = None,
                    override_file: str | Path | None = None) -> CurriculumIndex:
        source = Path(teacher_guide_path or curriculum.teacher_guide_path)
        pages = self.extractor.extract_pages(source)
        candidates = self._candidates(pages)
        selected: list[_Candidate] = []
        rejected: list[str] = []
        for candidate in sorted(candidates, key=lambda item: (item.page.pdf_page_number, -item.score)):
            if candidate.score < 0.6:
                rejected.append(
                    f"Ignored low-confidence Lesson {candidate.number} heading on PDF page "
                    f"{candidate.page.display_page_number}; it lacked supporting placement or title signals."
                )
                continue
            duplicate = next((item for item in selected if item.number == candidate.number), None)
            if duplicate:
                rejected.append(f"Ignored duplicate, out-of-order Lesson {candidate.number} heading on PDF page {candidate.page.display_page_number}.")
                continue
            if selected and candidate.number <= selected[-1].number:
                rejected.append(f"Ignored out-of-order Lesson {candidate.number} heading on PDF page {candidate.page.display_page_number}.")
                continue
            selected.append(candidate)

        overrides = self._read_overrides(override_file)
        by_number = {candidate.number: candidate for candidate in selected}
        for number, change in overrides.items():
            start = int(change["start_pdf_page"])
            if not 0 <= start < len(pages):
                raise ValueError(f"Override for Lesson {number} has invalid start_pdf_page {start}.")
            existing = by_number.get(number)
            by_number[number] = _Candidate(
                number, pages[start], str(change.get("detected_heading", f"Lesson {number} (manual override)")),
                change.get("lesson_title", existing.title if existing else None),
                int(change.get("text_start_offset", 0)), 1.0, ["Boundary supplied by manual override."],
            )
        ordered = sorted(by_number.values(), key=lambda item: item.page.pdf_page_number)
        if any(a.number >= b.number for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Manual overrides produce duplicate or out-of-order lesson numbers.")

        entries: list[LessonIndexEntry] = []
        for index, item in enumerate(ordered):
            next_start = ordered[index + 1].page.pdf_page_number if index + 1 < len(ordered) else len(pages)
            for page in pages[item.page.pdf_page_number + 1:next_start]:
                first_line = next((line.strip() for line in page.normalized_text.splitlines() if line.strip()), "")
                if first_line.casefold() in {"pausing point", "teacher resources"}:
                    next_start = page.pdf_page_number
                    break
            end = next_start - 1
            warnings = list(item.warnings)
            if index and item.number != ordered[index - 1].number + 1:
                warnings.append(f"Lesson numbering gap follows Lesson {ordered[index - 1].number}.")
            metadata = extract_ckla_lesson_metadata(pages[item.page.pdf_page_number:end + 1])
            entries.append(LessonIndexEntry(
                lesson_number=item.number, lesson_title=metadata.title or item.title,
                lesson_objective=metadata.objectives, standards=metadata.standards,
                materials=metadata.materials, homework=metadata.homework,
                reader_pages=metadata.reader_pages, activity_book_pages=metadata.activity_book_pages,
                assessment_references=metadata.assessment_references,
                lesson_duration=metadata.duration_minutes, source_page_numbers=metadata.source_page_numbers,
                start_pdf_page=item.page.pdf_page_number, end_pdf_page=end,
                start_printed_page=item.page.printed_page_number,
                end_printed_page=pages[end].printed_page_number if pages and end >= 0 else None,
                text_start_offset=item.offset, detected_heading=item.heading,
                confidence=item.score, warnings=warnings, source_file=str(source),
            ))
        extraction_warnings = [
            f"PDF page {page.display_page_number}: {warning}" for page in pages for warning in page.warnings
        ] + rejected
        if not entries:
            extraction_warnings.append("No reliable lesson headings were detected; use a manual override file.")
        return CurriculumIndex(curriculum=curriculum, total_pdf_pages=len(pages), lessons=entries,
                               extraction_warnings=extraction_warnings)

    def default_index_path(self, curriculum: CurriculumUnit) -> Path:
        slug = re.sub(r"[^a-z0-9]+", "_", curriculum.curriculum_name.lower()).strip("_")
        return self.index_directory / f"{slug}_grade_{curriculum.grade}_unit_{curriculum.unit}_index.json"

    def save_index(self, index: CurriculumIndex, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self.default_index_path(index.curriculum)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(index.model_dump_json(indent=2), encoding="utf-8")
        return target

    def load_index(self, path: str | Path) -> CurriculumIndex:
        try:
            return CurriculumIndex.model_validate_json(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"Unable to load curriculum index {path}: {error}") from error

    @staticmethod
    def get_lesson_entry(index: CurriculumIndex, lesson_number: int) -> LessonIndexEntry:
        entry = next((item for item in index.lessons if item.lesson_number == lesson_number), None)
        if entry is None:
            raise KeyError(f"Lesson {lesson_number} is not present in the curriculum index.")
        return entry

    def extract_lesson_source(self, index: CurriculumIndex, lesson_number: int,
                              teacher_guide_path: str | Path | None = None) -> LessonSource:
        entry = self.get_lesson_entry(index, lesson_number)
        path = Path(teacher_guide_path or entry.source_file)
        pages = self.extractor.extract_pages(path)
        if entry.end_pdf_page >= len(pages):
            raise ValueError("Saved lesson index exceeds the current Teacher Guide page count; rebuild the index.")
        text_parts = [page.normalized_text for page in pages[entry.start_pdf_page:entry.end_pdf_page + 1]]
        if text_parts and entry.text_start_offset:
            text_parts[0] = text_parts[0][entry.text_start_offset:]
        if text_parts and entry.text_end_offset is not None:
            text_parts[-1] = text_parts[-1][:entry.text_end_offset]
        warnings = list(entry.warnings)
        warnings.extend(w for page in pages[entry.start_pdf_page:entry.end_pdf_page + 1] for w in page.warnings)
        references = [f"{path}, PDF pages {entry.start_pdf_page + 1}-{entry.end_pdf_page + 1}"]
        return LessonSource(
            curriculum=index.curriculum, lesson_number=entry.lesson_number, lesson_title=entry.lesson_title,
            start_page=entry.start_pdf_page, end_page=entry.end_pdf_page,
            extracted_text="\n\n".join(text_parts), source_references=references, warnings=warnings,
        )
