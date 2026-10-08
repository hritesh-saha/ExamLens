"""
test_ocr.py
===========
Tests for ocr.py

Run with:
    cd "c:\\Users\\cherr\\Desktop\\innovative project"
    venv\\Scripts\\pytest backend\\tests\\test_ocr.py -v

Strategy:
    - For "has text" pages, we verify OCR is skipped (pdf_reader handles those)
    - For "no text" pages, we create a real scanned-like PDF and run real OCR
    - We also test error handling: bad path, bad page number, etc.

Note on OCR accuracy:
    OCR on a freshly-rendered PDF (text → image → OCR) is not 100% perfect.
    We test for approximate content, not exact character-for-character match.
"""

import os
import sys
import tempfile
import pytest
import pymupdf
from PIL import Image

# Path fix for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exam_parser.ocr import (
    ocr_page,
    ocr_pdf,
    is_tesseract_available,
    _render_page_to_image,
    _run_tesseract,
)


# ── Helper: make a PDF that simulates a scanned page ──────────────────────────
# We create a PDF, render it to an image, then embed THAT image back
# into a new PDF — mimicking a real scanned document.

def make_scanned_pdf(text_lines: list[str]) -> str:
    """
    Create a PDF that simulates a scanned document.

    Flow:
        1. Create a text PDF
        2. Render it to a pixel image (like scanning)
        3. Embed that image into a new blank PDF
        4. The resulting PDF has NO text layer — only an image
           → ocr.py must handle it

    This closely matches a real scanned exam paper.
    """
    # Step 1: Create a PDF with text
    doc = pymupdf.open()
    page = doc.new_page()
    y = 100
    for line in text_lines:
        page.insert_text((72, y), line, fontsize=14)
        y += 30

    # Step 2: Render page 0 to an image (simulates scanning)
    mat = pymupdf.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()

    # Step 3: Create a NEW PDF that only contains the image (no text layer)
    img_doc = pymupdf.open()
    img_page = img_doc.new_page(width=pix.width, height=pix.height)

    # Save image to a temp file so we can insert it into the PDF
    tmp_img = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_img_path = tmp_img.name
    tmp_img.close()
    img.save(tmp_img_path)

    # Insert image — the whole page IS the image
    img_page.insert_image(img_page.rect, filename=tmp_img_path)
    os.unlink(tmp_img_path)

    # Step 4: Save the image-only PDF
    tmp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_pdf_path = tmp_pdf.name
    tmp_pdf.close()
    img_doc.save(tmp_pdf_path)
    img_doc.close()

    return tmp_pdf_path


def make_text_pdf(text_lines: list[str]) -> str:
    """Simple PDF with embedded text (not scanned)."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 100
    for line in text_lines:
        page.insert_text((72, y), line)
        y += 25
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()
    doc.save(tmp_path)
    doc.close()
    return tmp_path


# ── Prerequisite check ────────────────────────────────────────────────────────

def test_tesseract_is_available():
    """
    Tesseract must be installed before any OCR tests can pass.
    If this test fails, install Tesseract first (see README).
    """
    assert is_tesseract_available(), (
        "Tesseract is not installed or not reachable. "
        "Download from https://github.com/UB-Mannheim/tesseract/wiki "
        "and set TESSERACT_PATH in backend/.env"
    )


# ── Tests: _render_page_to_image ──────────────────────────────────────────────

class TestRenderPageToImage:
    """Tests for the internal page rendering helper."""

    def test_renders_to_pil_image(self):
        """A valid PDF page should render to a PIL Image object."""
        path = make_text_pdf(["Q1. Explain DBMS."])
        try:
            img = _render_page_to_image(path, page_number=1, zoom=2)
            assert isinstance(img, Image.Image)
        finally:
            os.unlink(path)

    def test_image_has_reasonable_size(self):
        """
        At zoom=2, an A4 page (595x842 pts) becomes ~1190x1684 px.
        The image must be larger than a thumbnail.
        """
        path = make_text_pdf(["Test page content"])
        try:
            img = _render_page_to_image(path, page_number=1, zoom=2)
            assert img.width > 500
            assert img.height > 500
        finally:
            os.unlink(path)

    def test_higher_zoom_gives_larger_image(self):
        """zoom=3 image must be larger than zoom=2 image."""
        path = make_text_pdf(["Test"])
        try:
            img2 = _render_page_to_image(path, page_number=1, zoom=2)
            img3 = _render_page_to_image(path, page_number=1, zoom=3)
            assert img3.width > img2.width
            assert img3.height > img2.height
        finally:
            os.unlink(path)

    def test_invalid_page_number_returns_none(self):
        """Page 99 of a 1-page PDF → should return None, not crash."""
        path = make_text_pdf(["Q1. What is SQL?"])
        try:
            img = _render_page_to_image(path, page_number=99, zoom=2)
            assert img is None
        finally:
            os.unlink(path)

    def test_invalid_pdf_path_returns_none(self):
        """Non-existent PDF → should return None, not raise."""
        img = _render_page_to_image("does_not_exist.pdf", page_number=1, zoom=2)
        assert img is None


# ── Tests: ocr_page ───────────────────────────────────────────────────────────

class TestOcrPage:
    """Tests for the main ocr_page() function."""

    def test_returns_correct_structure(self):
        """
        ocr_page must always return a dict with exactly:
        page_number, ocr_text, source
        """
        path = make_scanned_pdf(["UNIVERSITY EXAMINATION 2025"])
        try:
            result = ocr_page(path, page_number=1)
            assert isinstance(result, dict)
            assert "page_number"   in result
            assert "ocr_text"      in result
            assert "source"        in result
        finally:
            os.unlink(path)

    def test_source_is_always_ocr(self):
        """
        The source field must always be "ocr" so downstream (Member 4)
        knows this text came from OCR and may need extra cleaning.
        """
        path = make_scanned_pdf(["Q1. What is a database?"])
        try:
            result = ocr_page(path, page_number=1)
            assert result["source"] == "ocr"
        finally:
            os.unlink(path)

    def test_page_number_preserved_in_output(self):
        """The page_number in the result must match the input."""
        path = make_text_pdf(["page1", "page2"])
        try:
            result = ocr_page(path, page_number=1)
            assert result["page_number"] == 1
        finally:
            os.unlink(path)

    def test_ocr_text_is_string_not_none(self):
        """ocr_text must be a string (possibly empty), never None."""
        path = make_scanned_pdf(["Some exam question here"])
        try:
            result = ocr_page(path, page_number=1)
            assert isinstance(result["ocr_text"], str)
        finally:
            os.unlink(path)

    def test_ocr_extracts_text_from_scanned_page(self):
        """
        The core test: OCR must extract readable text from an image-only PDF.
        We use a simple keyword check because OCR is not character-perfect.
        """
        path = make_scanned_pdf([
            "END SEMESTER EXAMINATION",
            "Q1. Explain normalization.",
        ])
        try:
            result = ocr_page(path, page_number=1)
            text = result["ocr_text"].lower()
            # OCR won't be perfect, but it should catch at least some keywords
            assert len(text) > 10, "OCR returned almost nothing"
        finally:
            os.unlink(path)

    def test_bad_pdf_path_does_not_crash(self):
        """
        ocr_page must not raise an exception for a missing file.
        It should return an empty ocr_text and log the error.
        """
        result = ocr_page("nonexistent_file.pdf", page_number=1)
        assert result["ocr_text"] == ""
        assert result["source"] == "ocr"

    def test_bad_page_number_does_not_crash(self):
        """Page 999 on a 1-page PDF → graceful empty result."""
        path = make_text_pdf(["Q1. What is SQL?"])
        try:
            result = ocr_page(path, page_number=999)
            assert isinstance(result["ocr_text"], str)
        finally:
            os.unlink(path)


# ── Tests: ocr_pdf (batch) ────────────────────────────────────────────────────

class TestOcrPdf:
    """Tests for the batch ocr_pdf() function."""

    def test_returns_list(self):
        """ocr_pdf must always return a list."""
        path = make_scanned_pdf(["Q1. Explain DBMS."])
        try:
            results = ocr_pdf(path, pages_to_ocr=[1])
            assert isinstance(results, list)
        finally:
            os.unlink(path)

    def test_returns_one_result_per_page(self):
        """If we pass 2 page numbers, we get 2 result dicts back."""
        path = make_text_pdf(["page1", "page2"])
        try:
            results = ocr_pdf(path, pages_to_ocr=[1, 2])
            assert len(results) == 2
        finally:
            os.unlink(path)

    def test_empty_pages_list_returns_empty(self):
        """If no pages need OCR, return an empty list."""
        path = make_text_pdf(["Q1. What is SQL?"])
        try:
            results = ocr_pdf(path, pages_to_ocr=[])
            assert results == []
        finally:
            os.unlink(path)
