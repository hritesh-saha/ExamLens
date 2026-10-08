"""
segmenter.py
============
Stage 4 of the exam parser pipeline.

This module handles ONE job:
    Take normalized text from a page and split it into
    individual question segments.

It does NOT extract metadata (year, marks, section).
That is metadata.py's job.

It does NOT create Question objects.
That is models.py + parser.py's job.

What it produces per question:
    {
        "raw_text":       "Q1. Explain normalization in DBMS.",
        "question_label": "Q1",      <- the detected label (Q1, 1., (a), etc.)
        "question_type":  "main",    <- "main" or "sub"
        "section":        "A",       <- from nearest SECTION heading, or None
        "page_number":    1          <- passed in from the caller
    }

═══════════════════════════════════════════════════════════════════
HOW THE REGEX WORKS (beginner-friendly explanation)
═══════════════════════════════════════════════════════════════════

The segmenter works by finding "question boundaries" — lines that
START a new question. Once we know where each question STARTS, we
slice the text at those positions to get each question's full body.

We support these question start patterns:

Pattern 1: Q-prefix style
    Matches: Q1, Q2, Q.1, Q.2, Q1., Q1)
    Regex:   Q\\.?\\d+[.)\\s]
    Reads:   "Q" + optional dot + one or more digits + dot/paren/space

Pattern 2: Numbered style
    Matches: 1., 2., 10., 1)
    Regex:   ^\\s*\\d{1,2}[.)]\\s
    Reads:   start of line + optional spaces + 1-2 digits + dot or paren + space
    NOTE: We limit to 1-2 digits to avoid matching "2025." (years)

Pattern 3: Sub-question style
    Matches: (a), (b), (c), (i), (ii), (iii)
    Regex:   ^\\s*\\([a-zA-Z]{1,3}\\)\\s
    Reads:   start of line + ( + 1-3 letters + ) + space

Pattern 4: Section headings
    Matches: SECTION A, SECTION B, PART A, PART B, PART I, PART II
    These are not questions — they tell us which SECTION we're in.

The logic:
    1. Scan the text line by line
    2. For each line, check if it matches a question start pattern
    3. Record the character position of each match
    4. Slice the text at those positions to get individual questions
═══════════════════════════════════════════════════════════════════
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════════
# We compile patterns once at module load — faster than recompiling
# every time we process a page.

# Pattern 1: Q-prefix questions  (Q1, Q2, Q.1, Q1., Q1))
# (?i)     = case insensitive so q1 also matches
# Q\.?     = "Q" + optional literal dot
# \d+      = one or more digits
# [.)?\s]  = followed by dot, paren, or whitespace
PATTERN_Q_PREFIX = re.compile(
    r"(?i)^[\s]*Q\.?\d+[.)?\s]"
)

# Pattern 2: Numbered questions  (1., 2., 10.)
# ^\s*     = optional leading whitespace
# \d{1,2}  = 1 or 2 digit number only (avoids matching "2025.")
# [.)]     = dot or closing paren
# \s       = must be followed by a space (avoids "1.5 GHz" etc.)
PATTERN_NUMBERED = re.compile(
    r"^\s*\d{1,2}[.)]\s"
)

# Pattern 3: Sub-questions  (a), (b), (i), (ii)
# \(       = literal opening paren
# [a-zA-Z]{1,3} = 1-3 letters (handles i, ii, iii, a, b)
# \)       = literal closing paren
# \s       = followed by space
PATTERN_SUB = re.compile(
    r"^\s*\([a-zA-Z]{1,3}\)\s"
)

# Pattern 4: Section headings
# Matches: SECTION A, SECTION B, PART A, PART I, PART II
# (?i)     = case insensitive
PATTERN_SECTION = re.compile(
    r"(?i)^\s*(SECTION|PART)\s+([A-Z]{1,3}|\d{1,2})\s*[:\-]?\s*$"
)

# Broader section pattern that allows content after the heading
# e.g. "SECTION A: Answer all questions (50 marks)"
PATTERN_SECTION_WITH_CONTENT = re.compile(
    r"(?i)^\s*(SECTION|PART)\s+([A-Z]{1,3}|\d{1,2})\s*[:\-]?"
)


# ═══════════════════════════════════════════════════════════════════
# MAIN SEGMENTATION FUNCTION
# ═══════════════════════════════════════════════════════════════════

def segment_questions(
    normalized_text: str,
    page_number: int,
    current_section: Optional[str] = None
) -> tuple[list[dict], Optional[str]]:
    """
    Split normalized page text into individual question segments.

    Parameters
    ----------
    normalized_text : str
        Text that has already passed through normalizer.normalize().
    page_number : int
        The 1-indexed page number (from pdf_reader or ocr).
    current_section : str or None
        The section label active BEFORE this page begins.
        This handles papers where "SECTION A" appears on page 1
        and questions continue onto page 2.

    Returns
    -------
    tuple of:
        list[dict]  — one dict per detected question (see structure above)
        str or None — the section label active at the END of this page
                      (so the caller can pass it to the next page)

    How to call this:
        questions, section = segment_questions(text, page_num, current_section)

    The section is returned so parser.py can track it across pages:
        section = None
        for page in pages:
            new_qs, section = segment_questions(page["text"], page["page_number"], section)
            all_questions.extend(new_qs)
    """
    if not normalized_text or not normalized_text.strip():
        logger.debug(f"Page {page_number}: empty text, no questions to segment")
        return [], current_section

    lines = normalized_text.split("\n")

    # We will collect "spans" — each span is:
    # {"start_line": N, "label": "Q1", "type": "main"/"sub", "section": "A"}
    # Then we'll slice the lines between consecutive spans.
    spans = []
    active_section = current_section

    logger.debug(
        f"Page {page_number}: segmenting {len(lines)} lines, "
        f"starting section={active_section}"
    )

    for line_idx, line in enumerate(lines):

        # ── Check for SECTION heading ──────────────────────────────────────
        section_match = PATTERN_SECTION_WITH_CONTENT.match(line)
        if section_match:
            new_section = section_match.group(2).strip().upper()
            if active_section != new_section:
                active_section = new_section
                logger.debug(f"  Line {line_idx}: SECTION → {active_section}")
            continue   # section headings are not questions

        # ── Check for Q-prefix question  (Q1, Q2, ...) ────────────────────
        q_match = PATTERN_Q_PREFIX.match(line)
        if q_match:
            label = _extract_label(line)
            spans.append({
                "start_line": line_idx,
                "label":      label,
                "type":       "main",
                "section":    active_section,
            })
            logger.debug(f"  Line {line_idx}: Q-prefix question → '{label}'")
            continue

        # ── Check for numbered question  (1., 2., ...) ────────────────────
        n_match = PATTERN_NUMBERED.match(line)
        if n_match:
            # Avoid false positives: skip if the line is very short
            # (e.g. a lone "1." with nothing after it)
            stripped = line.strip()
            if len(stripped) > 3:
                label = _extract_label(line)
                spans.append({
                    "start_line": line_idx,
                    "label":      label,
                    "type":       "main",
                    "section":    active_section,
                })
                logger.debug(f"  Line {line_idx}: Numbered question → '{label}'")
            continue

        # ── Check for sub-question  ((a), (b), ...) ───────────────────────
        s_match = PATTERN_SUB.match(line)
        if s_match:
            label = _extract_label(line)
            spans.append({
                "start_line": line_idx,
                "label":      label,
                "type":       "sub",
                "section":    active_section,
            })
            logger.debug(f"  Line {line_idx}: Sub-question → '{label}'")
            continue

    # ── No questions found ─────────────────────────────────────────────────
    if not spans:
        logger.warning(
            f"Page {page_number}: no question patterns detected. "
            "The page may have an unusual format or only contain instructions."
        )
        return [], active_section

    # ── Slice text into question segments ──────────────────────────────────
    # Now that we know where each question STARTS, we slice the lines
    # between consecutive start positions.
    #
    # Example with 3 spans at lines [2, 8, 15]:
    #   Q1 text = lines[2 : 8]   (from Q1's start to Q2's start)
    #   Q2 text = lines[8 : 15]  (from Q2's start to Q3's start)
    #   Q3 text = lines[15: end] (from Q3's start to end of page)

    questions = []

    for i, span in enumerate(spans):
        start = span["start_line"]

        # End is either the next question's start, or end of the page
        if i + 1 < len(spans):
            end = spans[i + 1]["start_line"]
        else:
            end = len(lines)

        # Join the lines for this question block
        question_lines = lines[start:end]
        raw_text = "\n".join(question_lines).strip()

        if not raw_text:
            continue   # skip empty blocks

        questions.append({
            "raw_text":       raw_text,
            "question_label": span["label"],
            "question_type":  span["type"],
            "section":        span["section"],
            "page_number":    page_number,
        })

    logger.info(
        f"Page {page_number}: detected {len(questions)} question(s), "
        f"ending section={active_section}"
    )

    return questions, active_section


# ═══════════════════════════════════════════════════════════════════
# MULTI-PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def segment_all_pages(pages: list[dict]) -> list[dict]:
    """
    Run segmentation across all pages, tracking section state between pages.

    Parameters
    ----------
    pages : list[dict]
        List of page dicts, each with "normalized_text" and "page_number".
        Produced by normalizer.normalize_pages().

    Returns
    -------
    list[dict]
        Flat list of all question segments across all pages.
        Each dict has: raw_text, question_label, question_type,
                       section, page_number.

    Example usage in parser.py:
        pages = normalize_pages(raw_pages)
        all_questions = segment_all_pages(pages)
    """
    all_questions = []
    current_section = None   # tracks section across pages

    for page in pages:
        page_num = page.get("page_number", 0)
        text = page.get("normalized_text", "")

        page_questions, current_section = segment_questions(
            text, page_num, current_section
        )
        all_questions.extend(page_questions)

    logger.info(f"Total questions segmented across all pages: {len(all_questions)}")
    return all_questions


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def _extract_label(line: str) -> str:
    """
    Extract the question label from the beginning of a line.

    Examples:
        "Q1. Explain normalization."  → "Q1"
        "1. What is SQL?"             → "1"
        "(a) Describe..."             → "(a)"
        "Q2) Define ER model."        → "Q2"

    This is used for human-readable identification of each question.
    It's stored as question_label in the segment dict.

    We take up to the first 10 characters of the stripped line,
    then cut at the first whitespace after the label marker.
    """
    stripped = line.strip()

    # For sub-questions like (a), (b), (iii)
    sub_match = re.match(r"(\([a-zA-Z]{1,3}\))", stripped)
    if sub_match:
        return sub_match.group(1)

    # For Q-prefix like Q1, Q2, Q.1
    q_match = re.match(r"(?i)(Q\.?\d+)", stripped)
    if q_match:
        return q_match.group(1).upper().replace("Q.", "Q")

    # For numbered like 1., 2., 10.
    n_match = re.match(r"(\d{1,2})[.)]", stripped)
    if n_match:
        return n_match.group(1)

    # Fallback: return first "word"
    return stripped.split()[0] if stripped else "?"


def detect_section(line: str) -> Optional[str]:
    """
    Check if a line is a section heading and return the section label.

    Returns None if the line is not a section heading.

    Examples:
        "SECTION A"              → "A"
        "SECTION B: 50 marks"    → "B"
        "PART II"                → "II"
        "Q1. Explain DBMS."      → None
    """
    match = PATTERN_SECTION_WITH_CONTENT.match(line)
    if match:
        return match.group(2).strip().upper()
    return None


def is_question_start(line: str) -> bool:
    """
    Return True if a line looks like it starts a question.

    Checks all three question patterns (Q-prefix, numbered, sub).
    Does NOT check for section headings.

    Useful for unit testing individual line checks.
    """
    stripped = line.strip()
    if not stripped:
        return False

    if PATTERN_Q_PREFIX.match(line):
        return True
    if PATTERN_NUMBERED.match(line) and len(stripped) > 3:
        return True
    if PATTERN_SUB.match(line):
        return True

    return False
