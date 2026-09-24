"""
metadata.py
===========
Stage 5 of the exam parser pipeline.

This module extracts structured metadata from exam paper text.

It works at TWO levels:

  1. DOCUMENT LEVEL
     Scans the full paper text (usually the first page) to find:
       - year        (e.g. 2025 from "END SEMESTER EXAMINATION 2025")
       - exam_type   (e.g. "End Semester", "Mid Semester", "Internal")

  2. QUESTION LEVEL
     Scans each question's raw_text to find:
       - marks        (e.g. 5 from "[5 marks]" or "(5 Marks)")
       - is_compulsory (True/False/None from "Answer all" or "Optional")
       - section       (passed in from segmenter, just forwarded here)

IMPORTANT rules from the project contract:
  - If a value CANNOT be reliably determined → return None
  - Do NOT guess or fabricate metadata
  - year is determined ONCE at document level, then propagated to ALL questions
  - marks at question level override document-level defaults

What this module does NOT do:
  - Does NOT assign topic_id  (Member 4)
  - Does NOT assign repeat_group_id  (Member 4)
  - Does NOT modify cleaned_text  (Member 4)
  - Does NOT calculate analytics  (Member 5)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# DOCUMENT-LEVEL METADATA
# ═══════════════════════════════════════════════════════════════════

def extract_document_metadata(full_text: str) -> dict:
    """
    Extract document-level metadata from the full paper text.

    Call this ONCE per document (on the first 1-2 pages of the paper)
    before processing individual questions.

    The year and exam_type are then propagated to every Question record
    in parser.py.

    Parameters
    ----------
    full_text : str
        The combined text of the first 1-2 pages of the exam paper.
        These pages typically contain the header with all the metadata.

    Returns
    -------
    dict with keys:
        - year       (int or None)  : Four-digit year, e.g. 2025
        - exam_type  (str or None)  : e.g. "End Semester", "Mid Semester"

    Examples
    --------
    Input: "B.Tech END SEMESTER EXAMINATION NOVEMBER 2025\\nSubject: DBMS"
    Output: {"year": 2025, "exam_type": "End Semester"}

    Input: "Question Bank — DBMS"
    Output: {"year": None, "exam_type": None}
    """
    result = {
        "year":      extract_year(full_text),
        "exam_type": extract_exam_type(full_text),
    }

    logger.info(
        f"Document metadata: year={result['year']}, "
        f"exam_type={result['exam_type']}"
    )
    return result


# ═══════════════════════════════════════════════════════════════════
# QUESTION-LEVEL METADATA
# ═══════════════════════════════════════════════════════════════════

def extract_question_metadata(
    question_text: str,
    section: Optional[str] = None,
    document_year: Optional[int] = None,
    document_exam_type: Optional[str] = None,
    global_marks: Optional[int] = None,
) -> dict:
    """
    Extract metadata for a single question.

    Parameters
    ----------
    question_text : str
        The raw_text of one question segment (from segmenter.py).
    section : str or None
        The section label assigned by segmenter.py (e.g. "A", "B").
    document_year : int or None
        The year extracted at document level. Propagated to this question.
    document_exam_type : str or None
        The exam type extracted at document level. Propagated here.
    global_marks : int or None
        If the paper says "each question carries 5 marks" at the section
        level, pass that here as a default for questions that don't
        individually state their marks.

    Returns
    -------
    dict with keys:
        - year          (int or None)
        - exam_type     (str or None)
        - section       (str or None)
        - marks         (int or None)
        - is_compulsory (bool or None)

    All fields default to None if not determinable.
    """
    # Marks: try inline first, fall back to global_marks
    inline_marks = extract_marks(question_text)
    marks = inline_marks if inline_marks is not None else global_marks

    result = {
        "year":          document_year,
        "exam_type":     document_exam_type,
        "section":       section,
        "marks":         marks,
        "is_compulsory": extract_is_compulsory(question_text),
    }

    logger.debug(
        f"Question metadata: marks={result['marks']}, "
        f"is_compulsory={result['is_compulsory']}, section={section}"
    )
    return result


# ═══════════════════════════════════════════════════════════════════
# YEAR EXTRACTION
# ═══════════════════════════════════════════════════════════════════

# Years we consider valid for exam papers.
# We accept 1990–2099 to be future-proof.
_YEAR_MIN = 1990
_YEAR_MAX = 2099

def extract_year(text: str) -> Optional[int]:
    """
    Find the exam year from the document text.

    Strategy:
        Look for 4-digit numbers in the range 1990-2099.
        We scan ALL lines and collect candidate years.
        We prefer years that appear near exam-related keywords.
        If there's exactly one candidate, return it.
        If there are multiple candidates, prefer the most recent one
        that appears near keywords like "examination", "exam", "semester".

    Returns None if no reliable year is found.

    Examples:
        "END SEMESTER EXAMINATION 2025"     → 2025
        "November 2024 / April 2025"        → 2025 (most recent)
        "DBMS Question Bank"                → None
        "Copyright 2019. Exam 2025."        → 2025 (near keyword)

    Contract rule: Do NOT guess. Return None if uncertain.
    """
    if not text:
        return None

    # Find ALL 4-digit numbers that look like years
    all_year_candidates = []
    for match in re.finditer(r"\b((?:19|20)\d{2})\b", text):
        year_val = int(match.group(1))
        if _YEAR_MIN <= year_val <= _YEAR_MAX:
            all_year_candidates.append((year_val, match.start()))

    if not all_year_candidates:
        logger.debug("extract_year: no year candidates found")
        return None

    if len(all_year_candidates) == 1:
        year = all_year_candidates[0][0]
        logger.debug(f"extract_year: single candidate → {year}")
        return year

    # Multiple candidates — prefer year near exam keywords
    exam_keywords = re.compile(
        r"(?i)(examination|exam|semester|assessment|test|paper|annual|"
        r"mid[\s-]?term|end[\s-]?term|supplementary|back[\s-]?log)",
        re.IGNORECASE
    )

    # Score each candidate by proximity to exam keywords
    # Lower distance to a keyword = higher confidence
    scored = []
    for year_val, year_pos in all_year_candidates:
        # Check a window of 100 characters around the year
        window_start = max(0, year_pos - 100)
        window_end   = min(len(text), year_pos + 100)
        window = text[window_start:window_end]

        keyword_found = bool(exam_keywords.search(window))
        scored.append((year_val, keyword_found))

    # Return the most recent year that was near a keyword
    keyword_years = [y for y, near_kw in scored if near_kw]
    if keyword_years:
        return max(keyword_years)

    # No keyword proximity — return the most recent year overall
    # but log a warning so we know confidence is lower
    most_recent = max(y for y, _ in all_year_candidates)
    logger.warning(
        f"extract_year: multiple candidates {[y for y,_ in all_year_candidates]}, "
        f"no keyword proximity — using most recent: {most_recent}"
    )
    return most_recent


# ═══════════════════════════════════════════════════════════════════
# EXAM TYPE EXTRACTION
# ═══════════════════════════════════════════════════════════════════

# Known exam type patterns → canonical names
# Order matters: more specific patterns first
_EXAM_TYPE_PATTERNS = [
    (re.compile(r"(?i)end[\s\-]+semester"), "End Semester"),
    (re.compile(r"(?i)end[\s\-]+term"),     "End Semester"),
    (re.compile(r"(?i)final[\s\-]+exam"),   "End Semester"),
    (re.compile(r"(?i)mid[\s\-]+semester"), "Mid Semester"),
    (re.compile(r"(?i)mid[\s\-]+term"),     "Mid Semester"),
    (re.compile(r"(?i)internal[\s\-]+assessment"), "Internal"),
    (re.compile(r"(?i)\binternal\b"),        "Internal"),
    (re.compile(r"(?i)supplementary"),       "Supplementary"),
    (re.compile(r"(?i)back[\s\-]+log"),      "Supplementary"),
    (re.compile(r"(?i)re[\s\-]+exam"),       "Supplementary"),
    (re.compile(r"(?i)unit[\s\-]+test"),     "Unit Test"),
    (re.compile(r"(?i)class[\s\-]+test"),    "Unit Test"),
    (re.compile(r"(?i)quiz"),                "Quiz"),
    (re.compile(r"(?i)model[\s\-]+exam"),    "Model Exam"),
]

def extract_exam_type(text: str) -> Optional[str]:
    """
    Detect the exam type from the document header text.

    Returns a canonical exam type string, or None if not detected.

    Examples:
        "B.Tech END SEMESTER EXAMINATION 2025"  → "End Semester"
        "MID SEMESTER TEST — DBMS"              → "Mid Semester"
        "INTERNAL ASSESSMENT — Unit 1"          → "Internal"
        "DBMS Question Bank"                    → None

    Contract rule: Return None if not confidently detectable.
    """
    if not text:
        return None

    for pattern, canonical_name in _EXAM_TYPE_PATTERNS:
        if pattern.search(text):
            logger.debug(f"extract_exam_type: matched → '{canonical_name}'")
            return canonical_name

    logger.debug("extract_exam_type: no match found → None")
    return None


# ═══════════════════════════════════════════════════════════════════
# MARKS EXTRACTION
# ═══════════════════════════════════════════════════════════════════

# Patterns to find marks in question text.
# Listed from most specific to least specific.
# We stop at the first match.
_MARKS_PATTERNS = [
    # [5 marks], [5 Marks], [5 MARKS]
    re.compile(r"\[(\d+)\s*[Mm]arks?\]"),

    # (5 marks), (5 Marks)
    re.compile(r"\((\d+)\s*[Mm]arks?\)"),

    # 5 marks  (standalone, with word boundary)
    re.compile(r"\b(\d+)\s+[Mm]arks?\b"),

    # Marks: 5  or  Marks = 5
    re.compile(r"(?i)[Mm]arks?\s*[:=]\s*(\d+)"),

    # (05)  or  [05]  — marks in brackets without the word
    # Only match if it's a small number (1-20), to avoid matching years
    re.compile(r"[\[(](\d{1,2})[\])]"),
]

def extract_marks(text: str) -> Optional[int]:
    """
    Extract the marks value from a question's text.

    Tries multiple patterns in order of confidence. Returns the first
    confident match as an integer.

    Returns None if marks cannot be reliably determined.

    Examples:
        "Q1. Explain normalization. [5 marks]"   → 5
        "Q2. What is SQL? (3 Marks)"              → 3
        "Q3. Describe ACID properties. 10 marks"  → 10
        "Q4. Define a key."                       → None

    Contract rule: Return None if uncertain. Never guess.
    """
    if not text:
        return None

    for pattern in _MARKS_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                marks_val = int(match.group(1))
                # Sanity check: marks should be between 1 and 100
                if 1 <= marks_val <= 100:
                    logger.debug(f"extract_marks: found {marks_val}")
                    return marks_val
                else:
                    logger.debug(
                        f"extract_marks: value {marks_val} out of range 1-100, skipping"
                    )
            except (ValueError, IndexError):
                continue

    logger.debug("extract_marks: no marks found → None")
    return None


def extract_global_marks(section_instruction_text: str) -> Optional[int]:
    """
    Extract a global marks value from a section-level instruction.

    Some papers say:
        "Answer any 3 questions. Each question carries 10 marks."

    In this case, 10 marks applies to ALL questions in that section.
    We extract it here so parser.py can pass it as global_marks.

    Returns None if no clear global marks are stated.

    Examples:
        "Each question carries 5 marks."      → 5
        "All questions carry equal marks (10)" → 10
        "Answer any THREE questions."          → None
    """
    if not text:
        return None

    # Pattern: "each question carries N marks" or similar
    patterns = [
        re.compile(r"(?i)each\s+question\s+carries?\s+(\d+)\s+marks?"),
        re.compile(r"(?i)carries?\s+(\d+)\s+marks?"),
        re.compile(r"(?i)(\d+)\s+marks?\s+each"),
        re.compile(r"(?i)equal\s+marks\s*\((\d+)\)"),
    ]
    for pattern in patterns:
        match = pattern.search(section_instruction_text)
        if match:
            try:
                val = int(match.group(1))
                if 1 <= val <= 100:
                    return val
            except (ValueError, IndexError):
                continue
    return None


# ═══════════════════════════════════════════════════════════════════
# IS_COMPULSORY EXTRACTION
# ═══════════════════════════════════════════════════════════════════

# Patterns that indicate a question IS compulsory
_COMPULSORY_PATTERNS = [
    re.compile(r"(?i)\bcompulsory\b"),
    re.compile(r"(?i)\bmandatory\b"),
    re.compile(r"(?i)answer\s+all\b"),
    re.compile(r"(?i)attempt\s+all\b"),
    re.compile(r"(?i)all\s+questions?\s+are\s+compulsory"),
    re.compile(r"(?i)all\s+questions?\s+must\s+be\s+answered"),
]

# Patterns that indicate a question is OPTIONAL
_OPTIONAL_PATTERNS = [
    re.compile(r"(?i)\boptional\b"),
    re.compile(r"(?i)answer\s+any\s+\w+"),        # "Answer any THREE"
    re.compile(r"(?i)attempt\s+any\s+\w+"),        # "Attempt any 3"
    re.compile(r"(?i)answer\s+any\s+\d+"),         # "Answer any 3"
]

def extract_is_compulsory(text: str) -> Optional[bool]:
    """
    Determine if a question is compulsory or optional.

    Strategy:
        - Search the question text for compulsory/optional keywords.
        - Return True if compulsory signals found.
        - Return False if optional signals found.
        - Return None if neither is clearly indicated.

    NOTE: This is a best-effort extraction. The is_compulsory field
    at the SECTION level (e.g. "SECTION A: Answer all questions") is
    typically more reliable. parser.py applies section-level rules
    before calling this function for question-level overrides.

    Returns
    -------
    bool or None
        True  → question is compulsory
        False → question is optional
        None  → cannot determine

    Examples:
        "Q1. (Compulsory) Explain normalization."  → True
        "Answer any THREE of the following."       → False
        "Q2. What is SQL? [5 marks]"               → None
    """
    if not text:
        return None

    text_lower = text.lower()

    # Check compulsory first
    for pattern in _COMPULSORY_PATTERNS:
        if pattern.search(text):
            logger.debug("extract_is_compulsory: compulsory signal found → True")
            return True

    # Check optional
    for pattern in _OPTIONAL_PATTERNS:
        if pattern.search(text):
            logger.debug("extract_is_compulsory: optional signal found → False")
            return False

    return None


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE: PROCESS ALL QUESTIONS
# ═══════════════════════════════════════════════════════════════════

def enrich_questions_with_metadata(
    questions: list[dict],
    document_metadata: dict,
    global_marks: Optional[int] = None,
) -> list[dict]:
    """
    Add metadata to every question dict in the list.

    This is what parser.py calls after segmentation to attach
    year, exam_type, marks, and is_compulsory to each question.

    Parameters
    ----------
    questions : list[dict]
        Output of segmenter.segment_all_pages() — each dict has
        raw_text, section, page_number, etc.
    document_metadata : dict
        Output of extract_document_metadata() — has year, exam_type.
    global_marks : int or None
        Section-level default marks (from a line like
        "Each question carries 5 marks").

    Returns
    -------
    list[dict]
        Same list with metadata fields added to each question.
        Original fields preserved.

    The returned dicts are ready to be passed to models.py
    to create Question objects.
    """
    enriched = []
    for q in questions:
        q = dict(q)  # copy, don't mutate original

        meta = extract_question_metadata(
            question_text=q.get("raw_text", ""),
            section=q.get("section"),
            document_year=document_metadata.get("year"),
            document_exam_type=document_metadata.get("exam_type"),
            global_marks=global_marks,
        )

        # Merge metadata into the question dict
        q.update(meta)
        enriched.append(q)

    return enriched
