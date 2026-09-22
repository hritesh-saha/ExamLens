"""
normalizer.py
=============
Stage 3 of the exam parser pipeline.

This module handles ONE job:
    Take raw text (from pdf_reader or ocr) and apply
    SAFE, MECHANICAL formatting cleanup only.

IMPORTANT — what this module does NOT do:
    - Does NOT correct spelling  ("Explaln" stays "Explaln")
    - Does NOT rewrite sentences
    - Does NOT change words
    - Does NOT remove question numbers
    - Does NOT classify anything

Why keep it this way?
    The agreed contract says:
        raw_text  = preserved exactly as extracted
        cleaned_text = NULL (Member 4 fills this later)

    The normalizer sits between raw extraction and segmentation.
    It only makes the text easier to SPLIT into questions.
    It does NOT make the text "correct".

What it DOES do (safe operations only):
    1. Collapse multiple blank lines into a single blank line
    2. Strip trailing whitespace from each line
    3. Remove common page artifacts (page numbers, headers, footers)
    4. Normalise whitespace within lines (multiple spaces → one)
    5. Standardise line endings (CRLF → LF)

The output of normalize() is what gets passed to segmenter.py.
The raw_text stored in the database is NEVER touched by this module.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────

def normalize(text: str, source: str = "embedded") -> str:
    """
    Apply safe, mechanical formatting cleanup to raw page text.

    This is the only function you need to call from outside this module.
    It runs a sequence of small cleanup steps in a defined order.

    Parameters
    ----------
    text : str
        Raw text from pdf_reader or ocr. May be empty.
    source : str, optional
        Where the text came from: "embedded" or "ocr".
        OCR text gets one extra step: fixing broken hyphenated lines.
        Default is "embedded".

    Returns
    -------
    str
        Cleaned text, safe to pass to segmenter.py.
        If input is empty, returns empty string (never None).

    Examples
    --------
    Input (from OCR):
        "Q1.   Explain   normalization\\n\\n\\n\\nQ2. What is SQL?  \\n"

    Output:
        "Q1. Explain normalization\\n\\nQ2. What is SQL?"

    Note: "Explaln" would stay "Explaln" — we never fix spelling.
    """
    if not text:
        return ""

    logger.debug(f"Normalizing {len(text)} chars (source={source})")

    # Run each step in order.
    # Each step is a small, focused function you can read separately below.
    text = _standardize_line_endings(text)
    text = _strip_trailing_whitespace_per_line(text)
    text = _remove_page_artifacts(text)
    text = _collapse_multiple_spaces(text)
    text = _collapse_multiple_blank_lines(text)

    # OCR-specific: fix words broken across lines by hyphens
    if source == "ocr":
        text = _fix_ocr_hyphen_breaks(text)

    text = text.strip()   # remove leading/trailing whitespace from whole text

    logger.debug(f"Normalization complete: {len(text)} chars after cleanup")
    return text


# ── Step functions ─────────────────────────────────────────────────────────────
# Each step does exactly one thing. Keeping them separate makes them
# easy to test individually and easy to enable/disable.

def _standardize_line_endings(text: str) -> str:
    """
    Convert Windows-style line endings (CRLF) to Unix-style (LF).

    Why: PDF text on Windows sometimes has \\r\\n instead of \\n.
    Mixed line endings break regex patterns in segmenter.py.

    Example:
        "Q1. What is SQL?\\r\\nQ2. Explain joins." 
        → "Q1. What is SQL?\\nQ2. Explain joins."
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strip_trailing_whitespace_per_line(text: str) -> str:
    """
    Remove spaces and tabs from the END of each line.

    Why: PDFs often have trailing spaces after the last word on a line.
    These don't affect reading but clutter the text unnecessarily.

    Example:
        "Q1. Explain SQL.   \\nQ2. What is a key?  "
        → "Q1. Explain SQL.\\nQ2. What is a key?"
    """
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    return "\n".join(lines)


def _collapse_multiple_spaces(text: str) -> str:
    """
    Replace runs of 2+ spaces within a line with a single space.

    Why: OCR and PDF extraction often insert extra spaces between words,
    especially in columnar layouts or when reading table cells.

    IMPORTANT: This only collapses spaces, NOT newlines.
    We must not destroy the line structure — segmenter.py needs it.

    Example:
        "Q1.   Explain   the   concept   of   normalization."
        → "Q1. Explain the concept of normalization."
    """
    # re.sub replaces any run of 2+ spaces (not newlines) with one space
    # The regex [ ]{2,} matches "two or more space characters"
    return re.sub(r"[ ]{2,}", " ", text)


def _collapse_multiple_blank_lines(text: str) -> str:
    """
    Replace runs of 3+ consecutive blank lines with exactly 2 blank lines.

    Why: Question papers sometimes have large gaps between sections or
    questions. We allow up to 2 blank lines (which helps segmentation)
    but not more (which just wastes space).

    Example:
        "Q1. ...\\n\\n\\n\\n\\nQ2. ..."
        → "Q1. ...\\n\\nQ2. ..."

    The regex \\n{3,} matches "3 or more consecutive newlines".
    We replace with exactly 2 newlines (one blank line between content).
    """
    return re.sub(r"\n{3,}", "\n\n", text)


def _remove_page_artifacts(text: str) -> str:
    """
    Remove common page-level artifacts that appear in PDF extraction.

    These are lines that are NOT part of any question but appear because
    of the PDF's page structure. Keeping them confuses the segmenter.

    What we remove:
        - Standalone page numbers: "1", "- 2 -", "Page 3", "Page 3 of 10"
        - Form feed characters (\\f) — sometimes appear between PDF pages
        - Lines that are ONLY dashes/underscores (decorative separators)

    What we do NOT remove:
        - Headers with actual content ("UNIVERSITY EXAMINATION 2025")
        - Section labels ("SECTION A", "PART B")
        - Any line that contains words we might need

    Approach: line-by-line filtering. If a line matches a known artifact
    pattern, drop it. Otherwise, keep it.
    """
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip form feed characters (PDF page separators)
        if stripped == "\f" or stripped == "":
            cleaned_lines.append("")  # preserve blank line structure
            continue

        # Skip lines that are ONLY a page number
        # Patterns: "1", "- 2 -", "Page 3", "Page 3 of 10", "3 of 10"
        if _is_page_number_line(stripped):
            logger.debug(f"Removed page artifact: '{stripped}'")
            continue   # drop this line entirely

        # Skip lines that are ONLY decorative dashes/underscores/equals
        # Example: "─────────────────────" or "=============="
        if _is_decorative_line(stripped):
            logger.debug(f"Removed decorative line: '{stripped}'")
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _is_page_number_line(line: str) -> bool:
    """
    Return True if a line looks like ONLY a page number.

    We check against these patterns:
        "1"              → bare number
        "- 2 -"          → dashed page number
        "Page 3"         → word + number
        "Page 3 of 10"   → word + number + "of" + number
        "3 of 10"        → number + "of" + number

    We only match lines that contain NOTHING else — no question text.
    If the line has other words, it's not just a page number.
    """
    patterns = [
        r"^\d+$",                        # "1", "42"
        r"^-\s*\d+\s*-$",               # "- 2 -", "-2-"
        r"^[Pp]age\s+\d+$",             # "Page 3", "page 3"
        r"^[Pp]age\s+\d+\s+of\s+\d+$", # "Page 3 of 10"
        r"^\d+\s+of\s+\d+$",            # "3 of 10"
        r"^\[\d+\]$",                    # "[3]"
    ]
    for pattern in patterns:
        if re.match(pattern, line.strip()):
            return True
    return False


def _is_decorative_line(line: str) -> bool:
    """
    Return True if a line consists entirely of decorative characters.

    Examples of decorative lines to remove:
        "─────────────────"
        "================="
        "___________________"
        "- - - - - - - - -"

    We require at least 4 characters to avoid accidentally removing
    short legitimate content.
    """
    if len(line) < 4:
        return False
    # Check if all non-space characters are decorative symbols
    non_space = line.replace(" ", "")
    decorative_chars = set("─━═—–-_=~.*")
    return len(non_space) > 0 and all(c in decorative_chars for c in non_space)


def _fix_ocr_hyphen_breaks(text: str) -> str:
    """
    Join words that were broken across lines by a hyphen during OCR.

    OCR of printed text often breaks long words at the end of a line
    with a hyphen, like this:

        "The concept of normal-
        ization is important."

    This should become:
        "The concept of normalization is important."

    Why only for OCR (source="ocr")?
        Embedded PDF text doesn't have this issue because pdfplumber
        handles line merging internally. Applying this to embedded text
        could accidentally join legitimate hyphenated words.

    The regex:
        (\\w+)   → a word ending
        -        → followed by a hyphen
        \\n      → followed by a newline
        (\\w+)   → followed by the continuation word

    We join them WITHOUT the hyphen and WITHOUT the newline.
    """
    # Loop until no more hyphen-breaks remain.
    # A single re.sub pass only fixes one break at a time.
    # "nor-\nmal-\nization" needs two passes to become "normalization".
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
    return text


# ── Utility: normalize a list of page texts ────────────────────────────────────

def normalize_pages(pages: list[dict]) -> list[dict]:
    """
    Normalize text in a list of page dicts (as returned by pdf_reader/ocr).

    This is a convenience wrapper so parser.py can process all pages
    in one call instead of looping manually.

    Parameters
    ----------
    pages : list[dict]
        Each dict has at least one of: "embedded_text" or "ocr_text".
        The "source" field ("embedded" or "ocr") is used to select
        the correct normalization mode.

    Returns
    -------
    list[dict]
        Same list with a new "normalized_text" key added to each page.
        Original fields are preserved unchanged.

    Example input:
        [
            {"page_number": 1, "embedded_text": "Q1.   Explain...\\n\\n\\n",
             "has_text": True, "source": "embedded"},
            {"page_number": 2, "ocr_text": "Q2. What  is SQL?",
             "source": "ocr"}
        ]

    Example output:
        [
            {"page_number": 1, ..., "normalized_text": "Q1. Explain..."},
            {"page_number": 2, ..., "normalized_text": "Q2. What is SQL?"}
        ]
    """
    result = []
    for page in pages:
        page = dict(page)   # copy so we don't mutate the original

        # Figure out which text field this page has
        source = page.get("source", "embedded")

        if source == "ocr":
            raw = page.get("ocr_text", "")
        else:
            raw = page.get("embedded_text", "")

        page["normalized_text"] = normalize(raw, source=source)
        result.append(page)

    return result
