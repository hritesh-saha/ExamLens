"""
test_metadata.py
================
Tests for metadata.py

Run with:
    cd "c:\\Users\\cherr\\Desktop\\innovative project"
    venv\\Scripts\\pytest backend\\tests\\test_metadata.py -v

Tests cover all contract rules:
    - year extracted from document, propagated to questions
    - marks extracted from inline patterns
    - None returned when uncertain
    - Never fabricated
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exam_parser.metadata import (
    extract_year,
    extract_exam_type,
    extract_marks,
    extract_is_compulsory,
    extract_document_metadata,
    extract_question_metadata,
    enrich_questions_with_metadata,
)


# ═══════════════════════════════════════════════════════════════════
# Tests: extract_year()
# ═══════════════════════════════════════════════════════════════════

class TestExtractYear:

    def test_year_in_header(self):
        """Standard exam header format."""
        text = "END SEMESTER EXAMINATION NOVEMBER 2025"
        assert extract_year(text) == 2025

    def test_year_at_end_of_line(self):
        text = "B.Tech (CSE) — Database Management Systems 2024"
        assert extract_year(text) == 2024

    def test_year_with_month(self):
        text = "April / May 2023 — Mid Semester Test"
        assert extract_year(text) == 2023

    def test_two_years_prefers_exam_keyword_year(self):
        """
        If two years appear, the one near 'examination' wins.
        """
        text = "Copyright 2019. END SEMESTER EXAMINATION 2025."
        result = extract_year(text)
        assert result == 2025

    def test_no_year_returns_none(self):
        """No year anywhere → None. Contract rule."""
        text = "DBMS Question Bank — Unit 1"
        assert extract_year(text) is None

    def test_empty_text_returns_none(self):
        assert extract_year("") is None

    def test_year_out_of_range_ignored(self):
        """1850 is not a valid exam year."""
        text = "Historical paper from 1850. Exam 2025."
        assert extract_year(text) == 2025

    def test_returns_int_not_string(self):
        text = "END SEMESTER 2025"
        result = extract_year(text)
        assert isinstance(result, int)

    def test_recent_year(self):
        text = "UNIVERSITY EXAMINATION 2026"
        assert extract_year(text) == 2026


# ═══════════════════════════════════════════════════════════════════
# Tests: extract_exam_type()
# ═══════════════════════════════════════════════════════════════════

class TestExtractExamType:

    def test_end_semester(self):
        assert extract_exam_type("END SEMESTER EXAMINATION 2025") == "End Semester"

    def test_end_semester_lowercase(self):
        assert extract_exam_type("end semester exam 2025") == "End Semester"

    def test_end_term(self):
        assert extract_exam_type("B.Tech End Term Examination") == "End Semester"

    def test_mid_semester(self):
        assert extract_exam_type("MID SEMESTER TEST") == "Mid Semester"

    def test_mid_term(self):
        assert extract_exam_type("Mid-Term Assessment") == "Mid Semester"

    def test_internal(self):
        assert extract_exam_type("INTERNAL ASSESSMENT — DBMS") == "Internal"

    def test_supplementary(self):
        assert extract_exam_type("SUPPLEMENTARY EXAMINATION 2025") == "Supplementary"

    def test_backlog(self):
        assert extract_exam_type("Back Log Exam — CSE 2024") == "Supplementary"

    def test_unit_test(self):
        assert extract_exam_type("Unit Test 1 — DBMS") == "Unit Test"

    def test_quiz(self):
        assert extract_exam_type("Weekly Quiz — Chapter 3") == "Quiz"

    def test_unknown_returns_none(self):
        """A plain question bank with no exam type keywords."""
        assert extract_exam_type("DBMS Question Bank") is None

    def test_empty_text_returns_none(self):
        assert extract_exam_type("") is None

    def test_returns_string_not_none_type(self):
        result = extract_exam_type("END SEMESTER 2025")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# Tests: extract_marks()
# ═══════════════════════════════════════════════════════════════════

class TestExtractMarks:

    def test_square_brackets_marks(self):
        """[5 marks] format — most common in Indian exam papers."""
        assert extract_marks("Q1. Explain normalization. [5 marks]") == 5

    def test_square_brackets_capital_m(self):
        assert extract_marks("Q1. Explain normalization. [5 Marks]") == 5

    def test_round_brackets_marks(self):
        assert extract_marks("Q2. What is SQL? (3 marks)") == 3

    def test_marks_inline_no_brackets(self):
        assert extract_marks("Q3. Describe ACID. 10 marks") == 10

    def test_marks_colon_format(self):
        assert extract_marks("Marks: 5") == 5

    def test_marks_equals_format(self):
        assert extract_marks("Marks = 7") == 7

    def test_ten_marks(self):
        assert extract_marks("Q1. Long answer question. [10 marks]") == 10

    def test_no_marks_returns_none(self):
        """Contract rule: if no marks found → None."""
        assert extract_marks("Q4. Define a key.") is None

    def test_empty_text_returns_none(self):
        assert extract_marks("") is None

    def test_returns_int(self):
        result = extract_marks("Q1. Test. [5 marks]")
        assert isinstance(result, int)

    def test_marks_value_100_accepted(self):
        """100 marks is a valid total."""
        assert extract_marks("[100 marks]") == 100

    def test_zero_marks_not_returned(self):
        """0 marks doesn't make sense — should not be returned."""
        result = extract_marks("[0 marks]")
        assert result is None   # 0 is out of range 1-100

    def test_marks_not_confused_with_year(self):
        """
        A year like 2025 must not be returned as marks.
        The marks patterns require the word "marks" nearby
        (for the main patterns) or small numbers for bracket pattern.
        """
        result = extract_marks("EXAMINATION 2025")
        # 2025 is > 100, so it's filtered out
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Tests: extract_is_compulsory()
# ═══════════════════════════════════════════════════════════════════

class TestExtractIsCompulsory:

    def test_compulsory_keyword(self):
        assert extract_is_compulsory("Q1. (Compulsory) Explain SQL.") is True

    def test_mandatory_keyword(self):
        assert extract_is_compulsory("This question is mandatory.") is True

    def test_answer_all(self):
        assert extract_is_compulsory("Answer all questions.") is True

    def test_attempt_all(self):
        assert extract_is_compulsory("Attempt all questions in this section.") is True

    def test_all_questions_compulsory(self):
        assert extract_is_compulsory("All questions are compulsory.") is True

    def test_optional_keyword(self):
        assert extract_is_compulsory("Q5. (Optional) Describe indexing.") is False

    def test_answer_any_three(self):
        assert extract_is_compulsory("Answer any THREE of the following.") is False

    def test_answer_any_number(self):
        assert extract_is_compulsory("Answer any 3 questions.") is False

    def test_neutral_question_returns_none(self):
        """No compulsory/optional signal → None. Contract rule."""
        assert extract_is_compulsory("Q2. What is a primary key? [5 marks]") is None

    def test_empty_text_returns_none(self):
        assert extract_is_compulsory("") is None

    def test_returns_bool_or_none(self):
        result = extract_is_compulsory("Answer all questions.")
        assert result is True or result is False or result is None


# ═══════════════════════════════════════════════════════════════════
# Tests: extract_document_metadata()
# ═══════════════════════════════════════════════════════════════════

class TestExtractDocumentMetadata:

    def test_full_header_extraction(self):
        header = (
            "XYZ University\n"
            "B.Tech CSE — Semester 7\n"
            "END SEMESTER EXAMINATION NOVEMBER 2025\n"
            "Subject: Database Management Systems"
        )
        result = extract_document_metadata(header)
        assert result["year"] == 2025
        assert result["exam_type"] == "End Semester"

    def test_missing_year_returns_none(self):
        header = "END SEMESTER EXAMINATION\nSubject: DBMS"
        result = extract_document_metadata(header)
        assert result["year"] is None

    def test_missing_exam_type_returns_none(self):
        header = "DBMS Question Bank 2025"
        result = extract_document_metadata(header)
        assert result["exam_type"] is None

    def test_returns_dict_with_correct_keys(self):
        result = extract_document_metadata("END SEMESTER 2025")
        assert "year" in result
        assert "exam_type" in result


# ═══════════════════════════════════════════════════════════════════
# Tests: extract_question_metadata()
# ═══════════════════════════════════════════════════════════════════

class TestExtractQuestionMetadata:

    def test_year_propagated_from_document(self):
        """
        The year must come from the document level, not from the question.
        All questions in a 2025 paper get year=2025.
        """
        meta = extract_question_metadata(
            question_text="Q1. Explain normalization. [5 marks]",
            document_year=2025,
        )
        assert meta["year"] == 2025

    def test_exam_type_propagated_from_document(self):
        meta = extract_question_metadata(
            question_text="Q1. What is SQL?",
            document_exam_type="End Semester",
        )
        assert meta["exam_type"] == "End Semester"

    def test_section_from_segmenter(self):
        meta = extract_question_metadata(
            question_text="Q1. Test.",
            section="A",
        )
        assert meta["section"] == "A"

    def test_inline_marks_override_global(self):
        """
        If the question has [5 marks] inline, that wins over global_marks=10.
        """
        meta = extract_question_metadata(
            question_text="Q1. Explain SQL. [5 marks]",
            global_marks=10,
        )
        assert meta["marks"] == 5

    def test_global_marks_used_when_no_inline(self):
        """
        If no inline marks, global_marks (from section instruction) is used.
        """
        meta = extract_question_metadata(
            question_text="Q1. Explain normalization.",
            global_marks=10,
        )
        assert meta["marks"] == 10

    def test_topic_id_not_set(self):
        """topic_id must NOT appear in metadata — Member 4 sets it."""
        meta = extract_question_metadata("Q1. Test.")
        assert "topic_id" not in meta

    def test_repeat_group_not_set(self):
        """repeat_group_id must NOT appear — Member 4 sets it."""
        meta = extract_question_metadata("Q1. Test.")
        assert "repeat_group_id" not in meta

    def test_cleaned_text_not_set(self):
        """cleaned_text must NOT appear — Member 4 sets it."""
        meta = extract_question_metadata("Q1. Test.")
        assert "cleaned_text" not in meta

    def test_all_none_when_no_signals(self):
        """When nothing can be determined, all fields are None."""
        meta = extract_question_metadata("Q1. Define a key.")
        assert meta["year"] is None
        assert meta["exam_type"] is None
        assert meta["marks"] is None
        assert meta["is_compulsory"] is None


# ═══════════════════════════════════════════════════════════════════
# Tests: enrich_questions_with_metadata()
# ═══════════════════════════════════════════════════════════════════

class TestEnrichQuestionsWithMetadata:

    def _make_questions(self):
        return [
            {
                "raw_text": "Q1. Explain normalization. [5 marks]",
                "section": "A",
                "page_number": 1,
                "question_label": "Q1",
                "question_type": "main",
            },
            {
                "raw_text": "Q2. What is SQL? [3 marks]",
                "section": "A",
                "page_number": 1,
                "question_label": "Q2",
                "question_type": "main",
            },
        ]

    def test_adds_year_to_all_questions(self):
        questions = self._make_questions()
        doc_meta = {"year": 2025, "exam_type": "End Semester"}
        result = enrich_questions_with_metadata(questions, doc_meta)
        assert all(q["year"] == 2025 for q in result)

    def test_adds_exam_type_to_all_questions(self):
        questions = self._make_questions()
        doc_meta = {"year": 2025, "exam_type": "End Semester"}
        result = enrich_questions_with_metadata(questions, doc_meta)
        assert all(q["exam_type"] == "End Semester" for q in result)

    def test_marks_extracted_per_question(self):
        questions = self._make_questions()
        doc_meta = {"year": 2025, "exam_type": "End Semester"}
        result = enrich_questions_with_metadata(questions, doc_meta)
        assert result[0]["marks"] == 5
        assert result[1]["marks"] == 3

    def test_original_fields_preserved(self):
        """raw_text, section, page_number must all survive enrichment."""
        questions = self._make_questions()
        doc_meta = {"year": 2025, "exam_type": "End Semester"}
        result = enrich_questions_with_metadata(questions, doc_meta)
        assert result[0]["raw_text"] == "Q1. Explain normalization. [5 marks]"
        assert result[0]["page_number"] == 1
        assert result[0]["section"] == "A"

    def test_does_not_mutate_original_list(self):
        questions = self._make_questions()
        original_raw = questions[0]["raw_text"]
        doc_meta = {"year": 2025, "exam_type": "End Semester"}
        enrich_questions_with_metadata(questions, doc_meta)
        assert questions[0]["raw_text"] == original_raw

    def test_empty_questions_returns_empty(self):
        result = enrich_questions_with_metadata([], {"year": 2025, "exam_type": "End Semester"})
        assert result == []
