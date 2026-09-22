"""
test_segmenter.py
=================
Tests for segmenter.py

Run with:
    cd "c:\\Users\\cherr\\Desktop\\innovative project"
    venv\\Scripts\\pytest backend\\tests\\test_segmenter.py -v

We test every question numbering pattern from the project spec:
    Q1 / Q2 / Q3
    1. / 2. / 3.
    (a) / (b) / (c)
    SECTION A / SECTION B
    PART A / PART B
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exam_parser.segmenter import (
    segment_questions,
    segment_all_pages,
    is_question_start,
    detect_section,
    _extract_label,
)


# ═══════════════════════════════════════════════════════════════════
# Tests: is_question_start() — line-level checks
# ═══════════════════════════════════════════════════════════════════

class TestIsQuestionStart:

    # ── Q-prefix style ────────────────────────────────────────────────────

    def test_q1_is_question_start(self):
        assert is_question_start("Q1. Explain normalization.") is True

    def test_q2_lowercase(self):
        """q2 (lowercase) must also be detected."""
        assert is_question_start("q2. What is SQL?") is True

    def test_q_with_dot_prefix(self):
        """Q.1 style."""
        assert is_question_start("Q.1 Explain DBMS.") is True

    def test_q_with_paren(self):
        """Q1) style."""
        assert is_question_start("Q1) Explain ACID.") is True

    def test_q10_two_digit(self):
        assert is_question_start("Q10. Last question.") is True

    # ── Numbered style ────────────────────────────────────────────────────

    def test_numbered_dot(self):
        assert is_question_start("1. What is a primary key?") is True

    def test_numbered_paren(self):
        assert is_question_start("2) Explain joins.") is True

    def test_numbered_two_digit(self):
        assert is_question_start("10. Describe transactions.") is True

    def test_numbered_with_leading_space(self):
        """Leading spaces before "1." should still be detected."""
        assert is_question_start("   1. What is SQL?") is True

    def test_three_digit_number_not_question(self):
        """
        100. would be unusual — we limit to 2 digits to avoid false positives
        like years ("2025. This paper..."). Currently NOT matched.
        """
        # We limit to \d{1,2} so 100 is NOT matched — document this
        result = is_question_start("100. This is not a question.")
        assert result is False

    def test_year_like_number_not_question(self):
        """'2025.' must NOT be treated as a question number."""
        assert is_question_start("2025. This paper was set.") is False

    def test_lone_number_dot_not_question(self):
        """A bare '1.' with nothing after is not a real question."""
        assert is_question_start("1.") is False

    # ── Sub-question style ────────────────────────────────────────────────

    def test_sub_a(self):
        assert is_question_start("(a) Define normalization.") is True

    def test_sub_b(self):
        assert is_question_start("(b) What is a foreign key?") is True

    def test_sub_i(self):
        assert is_question_start("(i) Explain 1NF.") is True

    def test_sub_ii(self):
        assert is_question_start("(ii) Explain 2NF.") is True

    def test_sub_iii(self):
        assert is_question_start("(iii) Explain 3NF.") is True

    # ── Non-question lines ────────────────────────────────────────────────

    def test_blank_line_not_question(self):
        assert is_question_start("") is False
        assert is_question_start("   ") is False

    def test_instruction_line_not_question(self):
        assert is_question_start("Answer all questions.") is False
        assert is_question_start("Time: 3 hours") is False

    def test_section_heading_not_question(self):
        """SECTION A is a heading, not a question."""
        assert is_question_start("SECTION A") is False

    def test_marks_line_not_question(self):
        assert is_question_start("[5 marks]") is False


# ═══════════════════════════════════════════════════════════════════
# Tests: detect_section()
# ═══════════════════════════════════════════════════════════════════

class TestDetectSection:

    def test_section_a(self):
        assert detect_section("SECTION A") == "A"

    def test_section_b(self):
        assert detect_section("SECTION B") == "B"

    def test_section_lowercase(self):
        assert detect_section("section a") == "A"

    def test_part_a(self):
        assert detect_section("PART A") == "A"

    def test_part_b(self):
        assert detect_section("PART B") == "B"

    def test_part_i(self):
        assert detect_section("PART I") == "I"

    def test_part_ii(self):
        assert detect_section("PART II") == "II"

    def test_section_with_colon(self):
        assert detect_section("SECTION A:") == "A"

    def test_section_with_content(self):
        """'SECTION A: Answer all questions' should still return 'A'."""
        result = detect_section("SECTION A: Answer all questions")
        assert result == "A"

    def test_question_line_returns_none(self):
        assert detect_section("Q1. Explain normalization.") is None

    def test_random_text_returns_none(self):
        assert detect_section("Answer any 3 questions.") is None


# ═══════════════════════════════════════════════════════════════════
# Tests: segment_questions() — core segmentation
# ═══════════════════════════════════════════════════════════════════

class TestSegmentQuestions:

    # ── Q-prefix numbering ────────────────────────────────────────────────

    def test_q_prefix_three_questions(self):
        """
        The basic case: Q1/Q2/Q3 → 3 question dicts.
        """
        text = (
            "Q1. Explain normalization in DBMS. [5 marks]\n"
            "Q2. What is a primary key? [3 marks]\n"
            "Q3. Describe ACID properties. [5 marks]"
        )
        questions, _ = segment_questions(text, page_number=1)
        assert len(questions) == 3

    def test_q_prefix_labels_correct(self):
        text = (
            "Q1. First question.\n"
            "Q2. Second question.\n"
            "Q3. Third question."
        )
        questions, _ = segment_questions(text, page_number=1)
        labels = [q["question_label"] for q in questions]
        assert "Q1" in labels
        assert "Q2" in labels
        assert "Q3" in labels

    def test_q_prefix_text_preserved(self):
        """The full question text (including the label) must be in raw_text."""
        text = "Q1. Explain normalization in DBMS. [5 marks]\nQ2. What is SQL?"
        questions, _ = segment_questions(text, page_number=1)
        assert "normalization" in questions[0]["raw_text"]

    def test_multiline_question_body_captured(self):
        """
        A question body that spans multiple lines must be captured fully.
        The text between Q1 and Q2 all belongs to Q1.
        """
        text = (
            "Q1. Explain the concept of normalization in DBMS.\n"
            "Include examples of 1NF, 2NF, and 3NF in your answer.\n"
            "[10 marks]\n"
            "Q2. What is a primary key?"
        )
        questions, _ = segment_questions(text, page_number=1)
        assert len(questions) == 2
        # Q1 should contain all three lines
        assert "1NF" in questions[0]["raw_text"]
        assert "10 marks" in questions[0]["raw_text"]

    # ── Numbered style (1./2./3.) ─────────────────────────────────────────

    def test_numbered_style_three_questions(self):
        text = (
            "1. What is a relational database? [5 marks]\n"
            "2. Explain the concept of a foreign key. [5 marks]\n"
            "3. Define a transaction. [5 marks]"
        )
        questions, _ = segment_questions(text, page_number=1)
        assert len(questions) == 3

    def test_numbered_style_labels(self):
        text = (
            "1. First question.\n"
            "2. Second question.\n"
        )
        questions, _ = segment_questions(text, page_number=1)
        labels = [q["question_label"] for q in questions]
        assert "1" in labels
        assert "2" in labels

    # ── Sub-question style ((a)/(b)/(c)) ──────────────────────────────────

    def test_sub_question_style(self):
        text = (
            "Q1. Explain normalization.\n"
            "(a) Define 1NF.\n"
            "(b) Define 2NF.\n"
            "(c) Define 3NF."
        )
        questions, _ = segment_questions(text, page_number=1)
        # Q1 + 3 sub-questions = 4
        assert len(questions) == 4

    def test_sub_question_type_is_sub(self):
        text = "(a) Define 1NF.\n(b) Define 2NF."
        questions, _ = segment_questions(text, page_number=1)
        types = [q["question_type"] for q in questions]
        assert all(t == "sub" for t in types)

    def test_main_question_type_is_main(self):
        text = "Q1. First.\nQ2. Second."
        questions, _ = segment_questions(text, page_number=1)
        types = [q["question_type"] for q in questions]
        assert all(t == "main" for t in types)

    # ── Section tracking ──────────────────────────────────────────────────

    def test_section_a_assigned_to_questions(self):
        text = (
            "SECTION A\n"
            "Q1. Explain normalization. [5 marks]\n"
            "Q2. What is SQL? [5 marks]"
        )
        questions, _ = segment_questions(text, page_number=1)
        assert all(q["section"] == "A" for q in questions)

    def test_section_changes_mid_page(self):
        text = (
            "SECTION A\n"
            "Q1. First section question.\n"
            "SECTION B\n"
            "Q2. Second section question."
        )
        questions, _ = segment_questions(text, page_number=1)
        assert len(questions) == 2
        assert questions[0]["section"] == "A"
        assert questions[1]["section"] == "B"

    def test_section_carried_from_previous_page(self):
        """
        If SECTION A ends page 1, questions on page 2 without a new
        section heading should still be in SECTION A.
        """
        text_p2 = "Q3. Continue from section A.\nQ4. Another question."
        questions, ending_section = segment_questions(
            text_p2, page_number=2, current_section="A"
        )
        assert all(q["section"] == "A" for q in questions)

    def test_returns_ending_section(self):
        """The second return value must be the active section at end of page."""
        text = "SECTION B\nQ1. Only question."
        _, ending_section = segment_questions(text, page_number=1)
        assert ending_section == "B"

    def test_no_section_heading_returns_none_section(self):
        """If there's no section heading, section should be None."""
        text = "Q1. Just a question.\nQ2. Another question."
        questions, _ = segment_questions(text, page_number=1)
        assert all(q["section"] is None for q in questions)

    # ── Page number tracking ──────────────────────────────────────────────

    def test_page_number_in_output(self):
        """Each question dict must have the correct page_number."""
        text = "Q1. Test question."
        questions, _ = segment_questions(text, page_number=3)
        assert questions[0]["page_number"] == 3

    # ── Edge cases ────────────────────────────────────────────────────────

    def test_empty_text_returns_empty(self):
        questions, section = segment_questions("", page_number=1)
        assert questions == []
        assert section is None

    def test_whitespace_only_returns_empty(self):
        questions, section = segment_questions("   \n\n  ", page_number=1)
        assert questions == []

    def test_instruction_text_no_questions(self):
        """A page with only instructions, no question patterns."""
        text = (
            "Answer any THREE questions.\n"
            "All questions carry equal marks.\n"
            "Time allowed: 3 hours."
        )
        questions, _ = segment_questions(text, page_number=1)
        assert len(questions) == 0

    def test_return_type_is_list_of_dicts(self):
        text = "Q1. Question one.\nQ2. Question two."
        questions, section = segment_questions(text, page_number=1)
        assert isinstance(questions, list)
        for q in questions:
            assert isinstance(q, dict)
            assert "raw_text"       in q
            assert "question_label" in q
            assert "question_type"  in q
            assert "section"        in q
            assert "page_number"    in q

    def test_raw_text_is_string(self):
        """raw_text must be a string, never None."""
        text = "Q1. Test.\nQ2. Test."
        questions, _ = segment_questions(text, page_number=1)
        for q in questions:
            assert isinstance(q["raw_text"], str)


# ═══════════════════════════════════════════════════════════════════
# Tests: segment_all_pages() — multi-page
# ═══════════════════════════════════════════════════════════════════

class TestSegmentAllPages:

    def test_two_pages_combined(self):
        pages = [
            {
                "page_number": 1,
                "normalized_text": "SECTION A\nQ1. First question.\nQ2. Second question."
            },
            {
                "page_number": 2,
                "normalized_text": "Q3. Third question.\nQ4. Fourth question."
            },
        ]
        all_questions = segment_all_pages(pages)
        assert len(all_questions) == 4

    def test_section_carries_across_pages(self):
        """
        SECTION A on page 1 must propagate to page 2's questions
        if no new SECTION heading appears on page 2.
        """
        pages = [
            {
                "page_number": 1,
                "normalized_text": "SECTION A\nQ1. First."
            },
            {
                "page_number": 2,
                "normalized_text": "Q2. Second.\nQ3. Third."
            },
        ]
        all_questions = segment_all_pages(pages)
        # Q2 and Q3 (page 2) should inherit SECTION A
        page2_qs = [q for q in all_questions if q["page_number"] == 2]
        assert all(q["section"] == "A" for q in page2_qs)

    def test_empty_pages_list(self):
        assert segment_all_pages([]) == []

    def test_page_numbers_correct_across_pages(self):
        pages = [
            {"page_number": 1, "normalized_text": "Q1. Page one question."},
            {"page_number": 2, "normalized_text": "Q2. Page two question."},
        ]
        all_questions = segment_all_pages(pages)
        assert all_questions[0]["page_number"] == 1
        assert all_questions[1]["page_number"] == 2


# ═══════════════════════════════════════════════════════════════════
# Tests: _extract_label() helper
# ═══════════════════════════════════════════════════════════════════

class TestExtractLabel:

    def test_q_prefix_label(self):
        assert _extract_label("Q1. Explain normalization.") == "Q1"

    def test_q_dot_label(self):
        assert _extract_label("Q.2 What is SQL?") == "Q2"

    def test_numbered_label(self):
        assert _extract_label("1. What is a key?") == "1"

    def test_sub_label(self):
        assert _extract_label("(a) Define 1NF.") == "(a)"

    def test_sub_roman_label(self):
        assert _extract_label("(iii) Explain BCNF.") == "(iii)"
