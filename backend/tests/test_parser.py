"""
test_parser.py (models section)
================================
Tests for models.py — Question, ParsedDocument, Topic, make_question()

Run with:
    cd "c:\\Users\\cherr\\Desktop\\innovative project"
    venv\\Scripts\\pytest backend\\tests\\test_parser.py -v

These tests verify the exact agreed contract between Member 3 and
Members 4, 5, and 6.
"""

import os
import sys
import json
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.exam_parser.models import (
    Question,
    ParsedDocument,
    Topic,
    make_question,
)


# ═══════════════════════════════════════════════════════════════════
# Tests: Question model — field contract
# ═══════════════════════════════════════════════════════════════════

class TestQuestionModel:

    def _valid_question(self, **overrides):
        """Return a minimal valid Question dict, with optional overrides."""
        base = {
            "question_id":     "q-001",
            "document_id":     101,
            "page":            1,
            "raw_text":        "Q1. Explain normalization in DBMS.",
        }
        base.update(overrides)
        return Question(**base)

    # ── Required fields ────────────────────────────────────────────────────

    def test_minimal_valid_question(self):
        """A Question with only required fields must be valid."""
        q = self._valid_question()
        assert q.question_id == "q-001"
        assert q.document_id == 101
        assert q.page == 1
        assert q.raw_text == "Q1. Explain normalization in DBMS."

    def test_all_optional_fields_default_to_none(self):
        """
        Contract: when Member 3 creates a question, optional fields are None.
        Member 4 fills cleaned_text, topic_id, repeat_group_id later.
        """
        q = self._valid_question()
        assert q.cleaned_text     is None
        assert q.year             is None
        assert q.exam_type        is None
        assert q.section          is None
        assert q.marks            is None
        assert q.is_compulsory    is None
        assert q.topic_id         is None
        assert q.repeat_group_id  is None

    # ── topic_id and repeat_group_id must start NULL ───────────────────────

    def test_topic_id_defaults_null(self):
        """CRITICAL: topic_id must be NULL at creation. Member 4 fills it."""
        q = self._valid_question()
        assert q.topic_id is None

    def test_repeat_group_id_defaults_null(self):
        """CRITICAL: repeat_group_id must be NULL at creation."""
        q = self._valid_question()
        assert q.repeat_group_id is None

    def test_cleaned_text_defaults_null(self):
        """CRITICAL: cleaned_text must be NULL at creation. Member 4 fills it."""
        q = self._valid_question()
        assert q.cleaned_text is None

    # ── Full question with all fields ──────────────────────────────────────

    def test_full_question_with_all_fields(self):
        """Build the exact example from the project spec."""
        q = Question(
            question_id="q-001",
            document_id=101,
            page=1,
            raw_text="Q1. Explain normalization in DBMS.",
            cleaned_text=None,
            year=2025,
            exam_type="End Semester",
            section="A",
            marks=5,
            is_compulsory=True,
            topic_id=None,
            repeat_group_id=None,
        )
        assert q.year == 2025
        assert q.exam_type == "End Semester"
        assert q.section == "A"
        assert q.marks == 5
        assert q.is_compulsory is True

    # ── JSON output matches expected contract ──────────────────────────────

    def test_json_output_has_all_contract_fields(self):
        """
        The JSON output must contain exactly the fields agreed in the contract.
        Members 4, 5, 6 depend on this structure.
        """
        q = self._valid_question(year=2025, exam_type="End Semester", marks=5)
        data = json.loads(q.model_dump_json())

        required_keys = [
            "question_id", "document_id", "page", "raw_text",
            "cleaned_text", "year", "exam_type", "section",
            "marks", "is_compulsory", "topic_id", "repeat_group_id"
        ]
        for key in required_keys:
            assert key in data, f"Missing key in JSON output: {key}"

    def test_json_output_null_for_none_fields(self):
        """Optional fields not set must appear as null in JSON."""
        q = self._valid_question()
        data = json.loads(q.model_dump_json())
        assert data["cleaned_text"]     is None
        assert data["topic_id"]         is None
        assert data["repeat_group_id"]  is None
        assert data["year"]             is None

    # ── Field validators ───────────────────────────────────────────────────

    def test_empty_raw_text_raises_error(self):
        """raw_text cannot be empty — a question with no text is invalid."""
        with pytest.raises(ValidationError) as exc_info:
            Question(question_id="q-001", document_id=101, page=1, raw_text="")
        assert "raw_text" in str(exc_info.value)

    def test_whitespace_only_raw_text_raises_error(self):
        with pytest.raises(ValidationError):
            Question(question_id="q-001", document_id=101, page=1, raw_text="   ")

    def test_page_must_be_positive(self):
        """Page 0 is invalid — pages are 1-indexed."""
        with pytest.raises(ValidationError):
            Question(question_id="q-001", document_id=101, page=0,
                     raw_text="Q1. Test.")

    def test_year_too_old_raises_error(self):
        """Year 1899 is outside valid range."""
        with pytest.raises(ValidationError):
            Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", year=1899)

    def test_year_too_future_raises_error(self):
        """Year 2200 is outside valid range."""
        with pytest.raises(ValidationError):
            Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", year=2200)

    def test_marks_must_be_positive(self):
        """marks=0 is invalid."""
        with pytest.raises(ValidationError):
            Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", marks=0)

    def test_marks_max_100(self):
        """marks=101 is invalid."""
        with pytest.raises(ValidationError):
            Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", marks=101)

    def test_marks_100_is_valid(self):
        """marks=100 is the maximum allowed."""
        q = Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", marks=100)
        assert q.marks == 100

    def test_empty_question_id_raises_error(self):
        with pytest.raises(ValidationError):
            Question(question_id="", document_id=101, page=1,
                     raw_text="Q1. Test.")

    # ── Type coercion ──────────────────────────────────────────────────────

    def test_marks_as_string_coerced_to_int(self):
        """Pydantic should coerce '5' → 5 for int fields."""
        q = Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", marks=5)
        assert isinstance(q.marks, int)

    def test_is_compulsory_accepts_bool(self):
        q = Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", is_compulsory=True)
        assert q.is_compulsory is True

    def test_is_compulsory_none(self):
        q = Question(question_id="q-001", document_id=101, page=1,
                     raw_text="Q1. Test.", is_compulsory=None)
        assert q.is_compulsory is None


# ═══════════════════════════════════════════════════════════════════
# Tests: make_question() factory
# ═══════════════════════════════════════════════════════════════════

class TestMakeQuestion:

    def test_generates_unique_ids(self):
        """Each call to make_question must produce a different question_id."""
        q1 = make_question(document_id=101, page=1, raw_text="Q1. Test.")
        q2 = make_question(document_id=101, page=1, raw_text="Q2. Test.")
        assert q1.question_id != q2.question_id

    def test_question_id_starts_with_q(self):
        q = make_question(document_id=101, page=1, raw_text="Q1. Test.")
        assert q.question_id.startswith("q-")

    def test_cleaned_text_is_none(self):
        """make_question must always set cleaned_text=None."""
        q = make_question(document_id=101, page=1, raw_text="Q1. Test.")
        assert q.cleaned_text is None

    def test_topic_id_is_none(self):
        q = make_question(document_id=101, page=1, raw_text="Q1. Test.")
        assert q.topic_id is None

    def test_repeat_group_id_is_none(self):
        q = make_question(document_id=101, page=1, raw_text="Q1. Test.")
        assert q.repeat_group_id is None

    def test_all_optional_params_passed(self):
        q = make_question(
            document_id=101,
            page=2,
            raw_text="Q3. Describe ACID.",
            year=2025,
            exam_type="End Semester",
            section="B",
            marks=10,
            is_compulsory=False,
        )
        assert q.year          == 2025
        assert q.exam_type     == "End Semester"
        assert q.section       == "B"
        assert q.marks         == 10
        assert q.is_compulsory is False

    def test_returns_question_instance(self):
        q = make_question(document_id=101, page=1, raw_text="Q1. Test.")
        assert isinstance(q, Question)


# ═══════════════════════════════════════════════════════════════════
# Tests: ParsedDocument model
# ═══════════════════════════════════════════════════════════════════

class TestParsedDocument:

    def _make_question(self, label="Q1"):
        return make_question(
            document_id=101,
            page=1,
            raw_text=f"{label}. Explain normalization.",
            year=2025,
            exam_type="End Semester",
            section="A",
            marks=5,
        )

    def test_minimal_parsed_document(self):
        doc = ParsedDocument(document_id=101)
        assert doc.document_id == 101
        assert doc.doc_type == "question_paper"
        assert doc.questions == []

    def test_with_questions(self):
        q = self._make_question()
        doc = ParsedDocument(document_id=101, year=2025, questions=[q])
        assert len(doc.questions) == 1
        assert doc.year == 2025

    def test_json_output(self):
        """ParsedDocument JSON must match the expected contract format."""
        q = self._make_question()
        doc = ParsedDocument(
            document_id=101,
            year=2025,
            exam_type="End Semester",
            questions=[q]
        )
        data = json.loads(doc.model_dump_json())
        assert data["document_id"]  == 101
        assert data["doc_type"]     == "question_paper"
        assert data["year"]         == 2025
        assert len(data["questions"]) == 1
        # First question must have topic_id=null and repeat_group_id=null
        first_q = data["questions"][0]
        assert first_q["topic_id"]        is None
        assert first_q["repeat_group_id"] is None
        assert first_q["cleaned_text"]    is None


# ═══════════════════════════════════════════════════════════════════
# Tests: Topic model
# ═══════════════════════════════════════════════════════════════════

class TestTopicModel:

    def test_valid_topic(self):
        t = Topic(
            topic_code="DBMS-02",
            name="Normalization",
            syllabus_unit="Unit 2"
        )
        assert t.topic_code == "DBMS-02"
        assert t.name == "Normalization"
        assert t.topic_id is None   # None before DB insertion

    def test_topic_id_optional(self):
        """topic_id is None before DB insertion — that's fine."""
        t = Topic(topic_code="DBMS-01", name="Relational Model", syllabus_unit="Unit 1")
        assert t.topic_id is None

    def test_empty_topic_code_raises_error(self):
        with pytest.raises(ValidationError):
            Topic(topic_code="", name="Normalization", syllabus_unit="Unit 2")

    def test_empty_name_raises_error(self):
        with pytest.raises(ValidationError):
            Topic(topic_code="DBMS-01", name="", syllabus_unit="Unit 1")

    def test_strips_whitespace(self):
        t = Topic(topic_code="  DBMS-01  ", name="  Relational Model  ",
                  syllabus_unit="  Unit 1  ")
        assert t.topic_code == "DBMS-01"
        assert t.name == "Relational Model"
