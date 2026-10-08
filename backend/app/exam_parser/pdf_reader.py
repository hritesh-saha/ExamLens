"""
pdf_reader.py
=============
Stage 1 of the exam parser pipeline.

This module handles ONE job:
    Open a PDF file and extract the embedded text from each page.

It does NOT do OCR.
It does NOT parse questions.
It does NOT assign metadata.

It simply answers:
    "Does this page have text we can use? If yes, what is it?"

Output per page:
    {
        "page_number": 1,          <- 1-indexed (human-friendly)
        "embedded_text": "...",    <- raw text from pdfplumber (may be empty)
        "has_text": True/False     <- True if text is usable
    }

If has_text is False, the OCR module (ocr.py) will handle that page.
"""

import logging
import os
from typing import Optional

import pdfplumber

# ── Logger setup ──────────────────────────────────────────────────────────────
# Each module gets its own named logger.
# The root logger in main.py controls the log level and format.
logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

# Minimum number of non-whitespace characters we require before we consider
# a page to "have usable text".
#
# Why 20? A page with just a header like "Page 1" or a watermark
# like "CONFIDENTIAL" technically has text but isn't useful for parsing.
# 20 characters is a reasonable threshold to filter out near-empty pages.
# You can raise this if you get too many near-empty pages slipping through.
MIN_TEXT_LENGTH = 20


# ── Main function ─────────────────────────────────────────────────────────────

def extract_pages(pdf_path: str) -> list[dict]:
    """
    Open a PDF and extract text from every page using pdfplumber.

    Parameters
    ----------
    pdf_path : str
        Absolute or relative path to the PDF file.

    Returns
    -------
    list[dict]
        A list with one dictionary per page. Each dict contains:
            - page_number  (int)  : 1-indexed page number
            - embedded_text (str) : Raw text extracted from the page.
                                    Empty string if the page has no text layer.
            - has_text     (bool) : True if the text is long enough to be useful.

    Raises
    ------
    FileNotFoundError
        If the PDF file does not exist at the given path.
    Exception
        If pdfplumber cannot open the file (e.g. corrupted PDF).

    Example
    -------
    pages = extract_pages("data/papers/dbms_2025.pdf")
    for page in pages:
        print(page["page_number"], page["has_text"])
    """

    # ── Validate file exists ───────────────────────────────────────────────
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    logger.info(f"Opening PDF: {pdf_path}")

    pages_data = []   # This list will hold one dict per page

    # ── Open the PDF with pdfplumber ──────────────────────────────────────
    # pdfplumber.open() returns a context manager (like open() for files).
    # It automatically closes the file when the 'with' block ends.
    try:
        with pdfplumber.open(pdf_path) as pdf:

            total_pages = len(pdf.pages)
            logger.info(f"PDF has {total_pages} page(s)")

            # Iterate over each page — pdfplumber gives us 0-indexed pages,
            # but we store them as 1-indexed for human readability.
            for i, page in enumerate(pdf.pages):
                page_number = i + 1   # Convert 0-index → 1-index

                # extract_text() pulls out all the text from the PDF's
                # embedded text layer. Returns None if there's no text layer.
                raw_text = page.extract_text()

                # Normalise: if pdfplumber returns None, treat it as ""
                # so we always work with strings, never None.
                if raw_text is None:
                    raw_text = ""

                # Strip leading/trailing whitespace from the whole page text
                raw_text = raw_text.strip()

                # Decide whether this page has enough text to be "usable"
                has_text = _is_usable_text(raw_text)

                page_dict = {
                    "page_number":   page_number,
                    "embedded_text": raw_text,
                    "has_text":      has_text,
                }
                pages_data.append(page_dict)

                # Log a summary for each page (useful when debugging)
                status = "text layer OK" if has_text else "needs OCR"
                preview = raw_text[:60].replace("\n", " ") if raw_text else "(empty)"
                logger.debug(
                    f"  Page {page_number}/{total_pages} — {status} "
                    f"| chars={len(raw_text)} | preview: '{preview}'"
                )

    except Exception as e:
        # If pdfplumber fails (e.g. password-protected or corrupt PDF),
        # log the error and re-raise so the caller (parser.py) can handle it.
        logger.error(f"Failed to read PDF '{pdf_path}': {e}")
        raise

    logger.info(
        f"Extraction complete: {len(pages_data)} pages, "
        f"{sum(1 for p in pages_data if p['has_text'])} with usable text, "
        f"{sum(1 for p in pages_data if not p['has_text'])} needing OCR"
    )

    return pages_data


# ── Helper function ───────────────────────────────────────────────────────────

def _is_usable_text(text: str) -> bool:
    """
    Decide whether the extracted text from a page is long enough to be useful.

    A page might technically have text (e.g. a watermark, a page number,
    or a header) but not enough for us to parse questions from it.

    Rule: strip all whitespace and count remaining characters.
    If fewer than MIN_TEXT_LENGTH characters remain → not usable → needs OCR.

    Parameters
    ----------
    text : str
        The raw text extracted from a PDF page.

    Returns
    -------
    bool
        True  → text is usable (skip OCR for this page)
        False → text is too short (OCR fallback needed)

    Examples
    --------
    _is_usable_text("")                     → False
    _is_usable_text("   \\n\\n  ")          → False
    _is_usable_text("Page 1")              → False  (only 6 non-space chars)
    _is_usable_text("Q1. Explain norms.")  → True   (19+ chars)
    """
    # Count non-whitespace characters only.
    # "  Q1.  \n  Explain " → "Q1.Explain" → 10 chars
    non_whitespace_count = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
    return non_whitespace_count >= MIN_TEXT_LENGTH


# ── Convenience helper ────────────────────────────────────────────────────────

def get_pdf_page_count(pdf_path: str) -> Optional[int]:
    """
    Quickly get how many pages a PDF has, without extracting text.

    Useful for logging or sanity checks before running the full pipeline.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    int or None
        Number of pages, or None if the file cannot be opened.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception as e:
        logger.warning(f"Could not get page count for '{pdf_path}': {e}")
        return None
