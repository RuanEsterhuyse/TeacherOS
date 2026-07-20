"""Deterministic extraction of CKLA lesson front matter and references."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from schemas.curriculum_schema import PdfPage


TITLE_PATTERNS = (
    r"(?:Read-Aloud|Whole Group|Small Group|Partners|Independent|Close Reading):\s*(?:“[^”]+”(?:\s+and\s+“[^”]+”)?|\"[^\"]+\"(?:\s+and\s+\"[^\"]+\")?)",
    r"Write a Short Story:\s*(?:Plan|Draft|Share, Evaluate, Revise|Edit and Polish|Publish)",
)
STANDARD_RE = re.compile(r"\b(?:RL|RI|W|SL|L)\.\d+\.\d+(?:\.[a-z])?\b", re.IGNORECASE)
ACTIVITY_ID_RE = re.compile(r"\b(?:SR\.\d+|\d+\.\d+)\b", re.IGNORECASE)
PAGE_TOKEN_RE = re.compile(r"\b(?:pages?|pp?\.)\s+((?:[ivxlcdm]+|\d+)(?:\s*[–—-]\s*(?:[ivxlcdm]+|\d+))?)", re.IGNORECASE)
SECTION_NAMES = {
    "Core Connections", "Reading", "Writing", "Grammar", "Morphology", "Speaking and Listening",
    "Language", "Spelling",
}


@dataclass
class CKLALessonMetadata:
    title: str | None = None
    objectives: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    homework: list[str] = field(default_factory=list)
    reader_pages: list[str] = field(default_factory=list)
    activity_book_pages: list[str] = field(default_factory=list)
    assessment_references: list[str] = field(default_factory=list)
    duration_minutes: int | None = None
    source_page_numbers: list[int] = field(default_factory=list)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _paragraphs(pages: list[PdfPage]) -> list[str]:
    values: list[str] = []
    for page in pages:
        blocks = page.metadata.get("blocks", [])
        if blocks:
            values.extend(re.sub(r"\s+", " ", str(block.get("text", "")).replace("\x08", " ")).strip() for block in blocks)
        else:
            values.extend(line.strip() for line in page.normalized_text.splitlines())
    return [value for value in values if value]


def _at_a_glance(page: PdfPage) -> str:
    text = page.normalized_text
    match = re.search(r"(?is)AT A GLANCE CHART\s*(.*?)(?:Primary Focus Objectives|ADVANCE PREPARATION)", text)
    return match.group(1).strip() if match else ""


def _title(chart: str, paragraphs: list[str]) -> str | None:
    for value in paragraphs:
        for pattern in TITLE_PATTERNS:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                return re.sub(r"\s+", " ", match.group(0)).strip(" \t.,")
    for pattern in TITLE_PATTERNS:
        match = re.search(pattern, chart, re.IGNORECASE)
        if match:
            title = re.sub(r"\s+", " ", match.group(0)).strip(" \t.,")
            return title.replace('"', '“', 1).replace('””', '”')
    return None


def _objectives(paragraphs: list[str]) -> list[str]:
    try:
        start = next(i for i, value in enumerate(paragraphs) if value.casefold() == "primary focus objectives") + 1
    except StopIteration:
        return []
    result: list[str] = []
    for value in paragraphs[start:]:
        if value.casefold() in {"academic vocabulary", "advance preparation"} or re.match(r"^DAY\s+\d+\b", value, re.IGNORECASE):
            break
        if value.startswith("By the end of this lesson") or value in SECTION_NAMES:
            continue
        # Objectives are paragraph blocks in CKLA, while page furniture is not instructional metadata.
        if re.search(r"\bUnit \d+\b.*\bLesson \d+\b", value):
            continue
        result.append(value)
    return _unique(result)


def _materials(chart: str, paragraphs: list[str]) -> list[str]:
    # CKLA uses a fixed materials column. Normalize its recurring named resources
    # and page identifiers without inventing supplies from lesson prose.
    values: list[str] = []
    if "Us, in Progress" in chart:
        values.append("Us, in Progress: Short Stories About Young Latinos")
    if "Online Resources" in chart:
        regions = [name for name in ("North", "Central", "South") if re.search(rf"\b{name}\b", chart)]
        values.append(f"Online Resources: Maps of {', '.join(regions)} America" if regions else "Online Resources")
    if re.search(r"(?m)^Map of North America$", chart):
        values.append("Map of North America")
    activity_ids = _activity_pages(chart.splitlines())
    if activity_ids:
        values.append(f"Activity Pages {', '.join(activity_ids)}")
    return _unique(values)


def _homework(text: str, paragraphs: list[str]) -> list[str]:
    positions = [i for i, value in enumerate(paragraphs) if value.casefold().startswith("take-home material")]
    if not positions:
        match = re.search(r"(?is)Take-Home Material\s*(.*?)(?:UNIT ASSESSMENT|Lesson \d+|\Z)", text)
        if not match:
            return []
        return _unique([
            line.strip() for line in match.group(1).splitlines()
            if re.search(r"\b(?:assign|take home|distribute|homework|at home)\b", line, re.IGNORECASE)
        ])
    items: list[str] = []
    current = ""
    for value in paragraphs[positions[-1] + 1:]:
        if re.search(r"\bUnit \d+\b.*\bLesson \d+\b", value):
            break
        if value in SECTION_NAMES:
            continue
        if re.match(r"^(?:Lesson \d+|DAY \d+|UNIT ASSESSMENT)$", value, re.IGNORECASE):
            break
        if value.startswith("•"):
            if current:
                items.append(current)
            current = value
        elif current:
            current = f"{current} {value}"
    if current:
        items.append(current)
    return _unique([
        value for value in items
        if re.search(r"\b(?:assign|take home|distribute|homework|at home)\b", value, re.IGNORECASE)
    ])


def _activity_pages(paragraphs: list[str]) -> list[str]:
    found: list[str] = []
    for value in paragraphs:
        if re.search(r"Activity Pages?", value, re.IGNORECASE):
            found.extend(match.upper() for match in ACTIVITY_ID_RE.findall(value))
    return _unique(found)


def _reader_pages(paragraphs: list[str]) -> list[str]:
    found: list[str] = []
    for value in paragraphs:
        lower = value.casefold()
        reader_context = any(term in lower for term in (
            "read-aloud:", "whole group:", "small group:", "partners:", "independent:",
            "close reading:", "story", "book us, in progress", "in us, in progress",
            "author’s introduction", "author's introduction", "translations", "refranes",
        ))
        if reader_context and "teacher" not in lower:
            without_activity_pages = re.sub(r"Activity Pages?\s+[^.;]+", "", value, flags=re.IGNORECASE)
            found.extend(re.sub(r"\s+", "", token) for token in PAGE_TOKEN_RE.findall(without_activity_pages))
        if re.match(r"^\[pages?\s+", value, re.IGNORECASE):
            found.extend(re.sub(r"\s+", "", token) for token in PAGE_TOKEN_RE.findall(value))
    return _unique(found)


def _assessments(paragraphs: list[str]) -> list[str]:
    values: list[str] = []
    for value in paragraphs:
        clean = re.sub(r"\s+", " ", value).strip()
        if len(clean) <= 180 and re.search(
            r"^(?:DAY \d+:?\s+)?(?:UNIT ASSESSMENT|ASSESSMENT|UNIT ASSESSMENT ANALYSIS|Check (?:for|Your) Understanding)\b",
            clean, re.IGNORECASE,
        ):
            if re.match(r"^(?:DAY \d+:?\s+)?UNIT ASSESSMENT ANALYSIS\b", clean, re.IGNORECASE):
                values.append("Unit Assessment Analysis")
            elif re.match(r"^(?:DAY \d+:?\s+)?UNIT ASSESSMENT\b", clean, re.IGNORECASE):
                activity = re.search(r"Activity Page\s+(\d+\.\d+)", clean, re.IGNORECASE)
                values.append(f"Unit Assessment (Activity Page {activity.group(1)})" if activity else "Unit Assessment")
            else:
                values.append(clean)
    return _unique(values)


def extract_ckla_lesson_metadata(pages: list[PdfPage]) -> CKLALessonMetadata:
    """Extract only metadata explicitly represented by CKLA's repeated lesson structure."""
    if not pages:
        return CKLALessonMetadata()
    chart = _at_a_glance(pages[0])
    paragraphs = _paragraphs(pages)
    front_paragraphs = _paragraphs([pages[0]])
    objectives = _objectives(paragraphs)
    objective_text_match = re.search(
        r"(?is)Primary Focus Objectives\s*(.*?)(?:Academic Vocabulary|ADVANCE PREPARATION|\nDAY\s+\d+\b)",
        "\n".join(page.normalized_text for page in pages),
    )
    objective_text = objective_text_match.group(1) if objective_text_match else ""
    durations = [int(value) for value in re.findall(r"\b(\d{1,3})\s*min\b", chart, re.IGNORECASE)]
    printed = [page.printed_page_number for page in pages if page.printed_page_number is not None]
    if not printed:
        # CKLA footers put the printed page first; PDF extraction may merge the whole footer.
        for page in pages:
            match = re.search(r"(?m)^\s*(\d{1,4})\s+Unit\s+\d+\b", page.normalized_text)
            if match:
                printed.append(int(match.group(1)))
    return CKLALessonMetadata(
        title=_title(chart, paragraphs), objectives=objectives,
        standards=_unique(STANDARD_RE.findall(objective_text)),
        materials=_materials(chart, front_paragraphs), homework=_homework("\n".join(p.normalized_text for p in pages), paragraphs),
        reader_pages=_reader_pages([line for page in pages for line in page.normalized_text.splitlines()]),
        activity_book_pages=_activity_pages([line for page in pages for line in page.normalized_text.splitlines()]),
        assessment_references=_assessments([line for page in pages for line in page.normalized_text.splitlines()]),
        duration_minutes=sum(durations) if durations else None, source_page_numbers=_unique_ints(printed),
    )


def _unique_ints(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))
