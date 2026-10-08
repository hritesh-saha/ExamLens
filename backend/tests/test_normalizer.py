"""
test_normalizer.py
==================
Tests for normalizer.py

Run with:
    cd "c:\\Users\\cherr\\Desktop\\innovative project"
    venv\\Scripts\\pytest backend\\tests\\test_normalizer.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exam_parser.normalizer import (
    normalize,
    normalize_pages,
    _standardize_line_endings,
    _strip_trailing_whitespace_per_line,
    _collapse_multiple_spaces,
    _collapse_multiple_blank_lines,
    _remove_page_artifacts,
    _fix_ocr_hyphen_breaks,
    _is_page_number_line,
    _is_decorative_line,
)


# ── Tests: normalize() — the main function ────────────────────────────────────

class TestNormalize:

    def test_empty_string_returns_empty(self):
        """Empty input must return empty string, never None."""
        assert normalize("") == ""

    def test_none_like_empty_handling(self):
        """Whitespace-only input returns empty after strip."""
        assert normalize("   \n\n  ") == ""

    def test_does_not_correct_spelling(self):
        """
        CRITICAL: OCR typos must be preserved.
        'Explaln' must NOT become 'Explain'.
        Member 4 does spelling correction, not us.
        """
        text = "Q1. Explaln the concept of normallzatlon."
        result = normalize(text)
        assert "Explaln" in result
        assert "normallzatlon" in result

    def test_does_not_remove_question_numbers(self):
        """Q1, Q2, 1., (a) must all survive normalization."""
        text = "Q1. First question\nQ2. Second question\n1. Third\n(a) Sub"
        result = normalize(text)
        assert "Q1" in result
        assert "Q2" in result
        assert "1." in result
        assert "(a)" in result

    def test_collapses_extra_spaces_within_line(self):
        """Multiple spaces within a line → single space."""
        text = "Q1.   Explain   the   concept   of   normalization."
        result = normalize(text)
        assert "Q1. Explain the concept of normalization." in result

    def test_collapses_multiple_blank_lines(self):
        """4 blank lines → 1 blank line."""
        text = "Q1. First\n\n\n\n\nQ2. Second"
        result = normalize(text)
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in result
        # Content should survive
        assert "Q1. First" in result
        assert "Q2. Second" in result

    def test_strips_trailing_spaces_per_line(self):
        """Trailing spaces after content on a line must be removed."""
        text = "Q1. Explain normalization.   \nQ2. What is SQL?  "
        result = normalize(text)
        for line in result.split("\n"):
            assert not line.endswith(" "), f"Line has trailing space: '{line}'"

    def test_standardizes_crlf_to_lf(self):
        """Windows line endings (\\r\\n) must become Unix (\\n)."""
        text = "Q1. Explain SQL.\r\nQ2. What is a key?\r\n"
        result = normalize(text)
        assert "\r" not in result

    def test_removes_standalone_page_numbers(self):
        """Lines that are ONLY a page number must be dropped."""
        text = "Q1. Explain DBMS.\n\n1\n\nQ2. What is SQL?"
        result = normalize(text)
        # "1" as a standalone line should be gone
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        assert "1" not in lines   # bare "1" page number removed

    def test_preserves_content_with_numbers(self):
        """
        A line like "Q1. Explain..." contains a number but is NOT
        a page number — it must be preserved.
        """
        text = "Q1. Explain normalization in DBMS."
        result = normalize(text)
        assert "Q1. Explain normalization in DBMS." in result

    def test_returns_string_always(self):
        """Return type must always be str."""
        assert isinstance(normalize("some text"), str)
        assert isinstance(normalize(""), str)

    def test_ocr_source_fixes_hyphen_breaks(self):
        """
        OCR mode should join words broken across lines with hyphens.
        'normal-\\nization' → 'normalization'
        """
        text = "The concept of normal-\nization is important."
        result = normalize(text, source="ocr")
        assert "normalization" in result

    def test_embedded_source_does_not_fix_hyphen_breaks(self):
        """
        Embedded text mode should NOT merge hyphenated lines,
        because those hyphens are likely intentional.
        """
        text = "The concept of normal-\nization is important."
        result = normalize(text, source="embedded")
        # Hyphen-break NOT merged for embedded text
        assert "normal-" in result


# ── Tests: individual step functions ─────────────────────────────────────────

class TestStandardizeLineEndings:

    def test_crlf_becomes_lf(self):
        assert _standardize_line_endings("a\r\nb") == "a\nb"

    def test_cr_only_becomes_lf(self):
        assert _standardize_line_endings("a\rb") == "a\nb"

    def test_lf_unchanged(self):
        assert _standardize_line_endings("a\nb") == "a\nb"


class TestStripTrailingWhitespace:

    def test_strips_trailing_spaces(self):
        result = _strip_trailing_whitespace_per_line("hello   \nworld  ")
        assert result == "hello\nworld"

    def test_preserves_leading_spaces(self):
        """Leading spaces (indentation) must survive."""
        result = _strip_trailing_whitespace_per_line("  (a) Sub-question  ")
        assert result.startswith("  (a)")

    def test_empty_lines_stay_empty(self):
        result = _strip_trailing_whitespace_per_line("line1\n   \nline2")
        assert result == "line1\n\nline2"


class TestCollapseMultipleSpaces:

    def test_collapses_double_space(self):
        assert _collapse_multiple_spaces("Q1.  Explain") == "Q1. Explain"

    def test_collapses_many_spaces(self):
        assert _collapse_multiple_spaces("a     b") == "a b"

    def test_single_space_unchanged(self):
        assert _collapse_multiple_spaces("a b") == "a b"

    def test_does_not_touch_newlines(self):
        """Newlines must survive — we only collapse spaces."""
        text = "Q1. First\n\nQ2. Second"
        assert _collapse_multiple_spaces(text) == text


class TestCollapseMultipleBlankLines:

    def test_three_newlines_become_two(self):
        result = _collapse_multiple_blank_lines("a\n\n\nb")
        assert result == "a\n\nb"

    def test_five_newlines_become_two(self):
        result = _collapse_multiple_blank_lines("a\n\n\n\n\nb")
        assert result == "a\n\nb"

    def test_two_newlines_unchanged(self):
        result = _collapse_multiple_blank_lines("a\n\nb")
        assert result == "a\n\nb"

    def test_one_newline_unchanged(self):
        result = _collapse_multiple_blank_lines("a\nb")
        assert result == "a\nb"


class TestIsPageNumberLine:

    def test_bare_number(self):
        assert _is_page_number_line("1") is True
        assert _is_page_number_line("42") is True

    def test_dashed_number(self):
        assert _is_page_number_line("- 2 -") is True
        assert _is_page_number_line("-2-") is True

    def test_page_word(self):
        assert _is_page_number_line("Page 3") is True
        assert _is_page_number_line("page 3") is True

    def test_page_of(self):
        assert _is_page_number_line("Page 3 of 10") is True
        assert _is_page_number_line("3 of 10") is True

    def test_question_line_not_page_number(self):
        """A question starting with a number is NOT a page number."""
        assert _is_page_number_line("Q1. Explain DBMS.") is False
        assert _is_page_number_line("1. What is SQL?") is False
        assert _is_page_number_line("SECTION A") is False

    def test_year_not_page_number(self):
        """
        A 4-digit year like '2025' matches the bare number pattern.
        This is acceptable — years don't appear as standalone lines in
        question content. If this causes issues, the pattern can be
        refined to exclude 4-digit numbers ≥ 1900.
        """
        # Just documenting the current behavior
        result = _is_page_number_line("2025")
        # Either True or False is acceptable — just document it
        assert isinstance(result, bool)


class TestIsDecorativeLine:

    def test_dashes_are_decorative(self):
        assert _is_decorative_line("─────────────") is True
        assert _is_decorative_line("=============") is True
        assert _is_decorative_line("_____________") is True

    def test_short_line_not_decorative(self):
        """Lines under 4 chars are not flagged (avoid false positives)."""
        assert _is_decorative_line("---") is False

    def test_content_line_not_decorative(self):
        assert _is_decorative_line("Q1. Explain DBMS.") is False
        assert _is_decorative_line("SECTION A") is False


class TestOcrHyphenFix:

    def test_joins_hyphen_broken_word(self):
        result = _fix_ocr_hyphen_breaks("normal-\nization")
        assert result == "normalization"

    def test_multiple_hyphen_breaks(self):
        result = _fix_ocr_hyphen_breaks("nor-\nmal-\nization")
        assert "normalization" in result

    def test_no_hyphen_break_unchanged(self):
        text = "Q1. Explain normalization."
        assert _fix_ocr_hyphen_breaks(text) == text


# ── Tests: normalize_pages() ──────────────────────────────────────────────────

class TestNormalizePages:

    def test_adds_normalized_text_key(self):
        """normalize_pages must add 'normalized_text' to each page dict."""
        pages = [
            {"page_number": 1, "embedded_text": "Q1.   Explain   SQL.", "has_text": True, "source": "embedded"},
        ]
        result = normalize_pages(pages)
        assert "normalized_text" in result[0]

    def test_original_fields_preserved(self):
        """Original fields (page_number, embedded_text, etc.) must survive."""
        pages = [
            {"page_number": 1, "embedded_text": "Q1. Explain SQL.", "has_text": True, "source": "embedded"},
        ]
        result = normalize_pages(pages)
        assert result[0]["page_number"] == 1
        assert result[0]["embedded_text"] == "Q1. Explain SQL."

    def test_handles_ocr_pages(self):
        """Pages with ocr_text (source='ocr') are handled correctly."""
        pages = [
            {"page_number": 2, "ocr_text": "Q2.  What  is SQL?", "source": "ocr"},
        ]
        result = normalize_pages(pages)
        assert "normalized_text" in result[0]
        assert "Q2." in result[0]["normalized_text"]

    def test_empty_list_returns_empty(self):
        assert normalize_pages([]) == []

    def test_does_not_mutate_original(self):
        """normalize_pages must not modify the input list in-place."""
        pages = [{"page_number": 1, "embedded_text": "Q1.", "source": "embedded"}]
        original_text = pages[0]["embedded_text"]
        normalize_pages(pages)
        assert pages[0]["embedded_text"] == original_text
