"""Tests for page-structured PDF extraction."""

import fitz

from curriculum.pdf_extractor import PDFTextExtractor


def make_pdf(path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_textbox(fitz.Rect(50, 50, 550, 760), text, fontsize=12)
    document.save(path)
    document.close()


def test_extracts_each_page_and_preserves_numbers(tmp_path) -> None:
    path = tmp_path / "guide.pdf"
    make_pdf(path, ["LESSON 1\nA title\n\nBody   with   spaces\n12", "Second page body\n13"])
    pages = PDFTextExtractor().extract_pages(path)
    assert [page.pdf_page_number for page in pages] == [0, 1]
    assert [page.display_page_number for page in pages] == [1, 2]
    assert pages[0].printed_page_number == 12
    assert "Body with spaces" in pages[0].normalized_text


def test_warns_about_text_poor_pages(tmp_path) -> None:
    path = tmp_path / "scanned.pdf"
    make_pdf(path, [""])
    page = PDFTextExtractor().extract_pages(path)[0]
    assert page.character_count == 0
    assert "OCR not attempted" in page.warnings[0]
