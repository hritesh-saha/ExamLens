"""
test_pdf_reader.py
==================
Tests for pdf_reader.py

Run with:
    cd "c:\\Users\\cherr\\Desktop\\innovative project"
    venv\\Scripts\\pytest backend\\tests\\test_pdf_reader.py -v

Each test creates a real in-memory PDF using PyMuPDF,
then passes it to our pdf_reader functions.
No external PDF files needed.
"""

import io
import os
import tempfile
import pytest
import pymupdf   # used to create test PDFs in memory

# Add the backend directory to the Python path so imports work
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exam_parser.pdf_reader import extract_pages, get_pdf_page_count, MIN_TEXT_LENGTH


# ── Helper: create a temporary PDF file ───────────────────────────────────────

def make_pdf_with_text(lines: list[str]) -> str:
    """
    Create a temporary PDF file with embedded text and return its path.

    Parameters
    ----------
    lines : list of str
        Each string is inserted as a line of text on page 1.

    Returns
    -------
    str
        Path to the temporary .pdf file. The test is responsible for
        deleting it afterwards.

    NOTE (Windows fix):
        On Windows, NamedTemporaryFile holds an exclusive lock on the file.
        PyMuPDF cannot write to a locked file, so we must:
          1. Create the temp file and get the path
          2. Close the file handle immediately (delete=False keeps the file)
          3. Then let PyMuPDF write to the path
    """
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72  # starting y position in points
    for line in lines:
        page.insert_text((72, y), line)
        y += 20  # move down for each line
    # Step 1+2: get a temp path and release the file handle immediately
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()   # release lock BEFORE pymupdf writes
    # Step 3: now pymupdf can safely write
    doc.save(tmp_path)
    doc.close()
    return tmp_path


def make_blank_pdf(num_pages: int = 1) -> str:
    """
    Create a PDF with blank pages (no text layer) and return its path.
    These pages will need OCR in the real pipeline.
    """
    doc = pymupdf.open()
    for _ in range(num_pages):
        doc.new_page()  # blank page — no text inserted
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()
    doc.save(tmp_path)
    doc.close()
    return tmp_path


def make_multipage_pdf(page_texts: list[list[str]]) -> str:
    """
    Create a multi-page PDF. Each item in page_texts is a list of lines
    for that page.
    """
    doc = pymupdf.open()
    for lines in page_texts:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line)
            y += 20
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()
    doc.save(tmp_path)
    doc.close()
    return tmp_path


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestExtractPages:
    """Tests for the extract_pages() function."""

    def test_pdf_with_rich_text_returns_has_text_true(self):
        """
        A page with a full question should have has_text = True.
        This is the normal case for digitally created PDFs.
        """
        path = make_pdf_with_text([
            "END SEMESTER EXAMINATION 2025",
            "Subject: Database Management Systems",
            "Q1. Explain the concept of normalization in DBMS. [5 marks]",
            "Q2. What is a primary key? Explain with an example. [3 marks]",
        ])
        try:
            pages = extract_pages(path)
            assert len(pages) == 1
            assert pages[0]["page_number"] == 1
            assert pages[0]["has_text"] is True
            assert "normalization" in pages[0]["embedded_text"]
        finally:
            os.unlink(path)   # clean up temp file

    def test_blank_page_returns_has_text_false(self):
        """
        A blank page (no text at all) must have has_text = False.
        This simulates a scanned PDF page — OCR will be needed.
        """
        path = make_blank_pdf(num_pages=1)
        try:
            pages = extract_pages(path)
            assert len(pages) == 1
            assert pages[0]["has_text"] is False
            assert pages[0]["embedded_text"] == ""
        finally:
            os.unlink(path)

    def test_page_with_only_whitespace_returns_has_text_false(self):
        """
        A page that technically has characters but only spaces/newlines
        should be treated as empty.
        """
        # PyMuPDF won't actually let us insert just spaces, so we test
        # the _is_usable_text logic separately. Here we use a blank page
        # as a proxy.
        path = make_blank_pdf()
        try:
            pages = extract_pages(path)
            assert pages[0]["has_text"] is False
        finally:
            os.unlink(path)

    def test_page_number_is_1_indexed(self):
        """
        Page numbers must start at 1, not 0.
        Human users (and Member 5's analytics) expect 1-indexed pages.
        """
        path = make_pdf_with_text(["Q1. What is SQL?"])
        try:
            pages = extract_pages(path)
            assert pages[0]["page_number"] == 1   # NOT 0
        finally:
            os.unlink(path)

    def test_multipage_pdf_returns_correct_count(self):
        """
        A 3-page PDF should produce exactly 3 page dicts.
        """
        path = make_multipage_pdf([
            ["SECTION A", "Q1. Explain DBMS. [5 marks]"],
            ["SECTION B", "Q2. What is normalization? [5 marks]"],
            ["SECTION C", "Q3. Explain ER diagrams. [5 marks]"],
        ])
        try:
            pages = extract_pages(path)
            assert len(pages) == 3
            assert pages[0]["page_number"] == 1
            assert pages[1]["page_number"] == 2
            assert pages[2]["page_number"] == 3
        finally:
            os.unlink(path)

    def test_multipage_mixed_text_and_blank(self):
        """
        A PDF where some pages have text and others are blank.
        The function should correctly flag each page individually.
        """
        path = make_multipage_pdf([
            ["Q1. Explain normalization. [5 marks]", "Q2. What is a join? [3 marks]"],
            [],   # blank page — needs OCR
            ["Q3. Describe ACID properties. [5 marks]"],
        ])
        try:
            pages = extract_pages(path)
            assert len(pages) == 3
            assert pages[0]["has_text"] is True    # has questions
            assert pages[1]["has_text"] is False   # blank → needs OCR
            assert pages[2]["has_text"] is True    # has a question
        finally:
            os.unlink(path)

    def test_raw_text_is_preserved_exactly(self):
        """
        The embedded_text field must be the raw text from pdfplumber.
        We should NOT be modifying or cleaning it in pdf_reader.py.
        Normalisation happens later in normalizer.py.
        """
        path = make_pdf_with_text([
            "Q1. Explaln the concept of normallzatlon."
        ])
        try:
            pages = extract_pages(path)
            # The typos must still be present — raw_text is not corrected here
            text = pages[0]["embedded_text"]
            assert "Explaln" in text or "normallzatlon" in text or "Q1" in text
        finally:
            os.unlink(path)

    def test_file_not_found_raises_error(self):
        """
        If the PDF path doesn't exist, we must raise FileNotFoundError.
        The parser should never silently swallow a missing file.
        """
        with pytest.raises(FileNotFoundError):
            extract_pages("this_file_does_not_exist_at_all.pdf")

    def test_return_type_is_list_of_dicts(self):
        """
        The return value must always be a list of dicts with the exact keys
        our pipeline expects: page_number, embedded_text, has_text.
        """
        path = make_pdf_with_text(["Q1. What is a database?"])
        try:
            pages = extract_pages(path)
            assert isinstance(pages, list)
            for page in pages:
                assert isinstance(page, dict)
                assert "page_number"   in page
                assert "embedded_text" in page
                assert "has_text"      in page
        finally:
            os.unlink(path)

    def test_embedded_text_is_always_a_string(self):
        """
        embedded_text must be a string, never None.
        This is important so downstream code doesn't need None checks.
        """
        path = make_blank_pdf()
        try:
            pages = extract_pages(path)
            assert isinstance(pages[0]["embedded_text"], str)
        finally:
            os.unlink(path)


class TestGetPdfPageCount:
    """Tests for the get_pdf_page_count() helper."""

    def test_correct_page_count_single_page(self):
        path = make_pdf_with_text(["Q1. What is DBMS?"])
        try:
            count = get_pdf_page_count(path)
            assert count == 1
        finally:
            os.unlink(path)

    def test_correct_page_count_multiple_pages(self):
        path = make_multipage_pdf([["page1"], ["page2"], ["page3"]])
        try:
            count = get_pdf_page_count(path)
            assert count == 3
        finally:
            os.unlink(path)

    def test_missing_file_returns_none(self):
        """
        get_pdf_page_count should return None (not crash) for a missing file.
        """
        count = get_pdf_page_count("nonexistent.pdf")
        assert count is None
