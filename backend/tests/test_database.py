"""
test_database.py
================
Unit tests for database layer: schema.py and db.py.

Verifies:
  - Database table creation & index creation
  - Document insertion and retrieval
  - Question insertion (single & batch, model & dict)
  - Full ParsedDocument atomic save
  - Topic insertion and retrieval (syllabus)
  - Foreign key constraints (CASCADE delete)
  - Nullable contract fields (topic_id, repeat_group_id, cleaned_text)
"""

import sqlite3
import pytest
from app.database.schema import get_all_ddl
from app.database.db import (
    get_connection,
    init_db,
    insert_document,
    get_document_by_id,
    get_all_documents,
    insert_question,
    insert_questions_batch,
    save_parsed_document,
    get_questions_by_document,
    get_all_questions,
    get_questions_by_year,
    insert_topics_batch,
    get_all_topics,
)
from app.exam_parser.models import Question, ParsedDocument, Topic, make_question


@pytest.fixture
def db():
    """Create an isolated in-memory database initialized with schema."""
    conn = get_connection(":memory:")
    for stmt in get_all_ddl():
        conn.execute(stmt)
    conn.commit()
    return conn


@pytest.fixture
def mem_db(monkeypatch):
    """Fixture providing a fresh in-memory database for db functions."""
    # We use a named in-memory URI or a unique temp file for testing
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


# ── Schema Tests ─────────────────────────────────────────────────────────────

def test_schema_ddl_list():
    ddl = get_all_ddl()
    assert len(ddl) >= 4  # documents, topics, questions + indexes
    assert any("CREATE TABLE IF NOT EXISTS documents" in s for s in ddl)
    assert any("CREATE TABLE IF NOT EXISTS topics" in s for s in ddl)
    assert any("CREATE TABLE IF NOT EXISTS questions" in s for s in ddl)


def test_init_db_creates_tables(mem_db):
    conn = get_connection(mem_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row["name"] for row in cursor.fetchall()}
    assert "documents" in tables
    assert "topics" in tables
    assert "questions" in tables
    conn.close()


def test_init_db_idempotent(mem_db):
    # Running init_db again should not raise any errors
    init_db(mem_db)
    init_db(mem_db)


# ── Document Operations ──────────────────────────────────────────────────────

def test_insert_and_get_document(mem_db):
    doc_id = insert_document(
        file_name="DBMS_2025_EndSem.pdf",
        file_path="/path/to/DBMS_2025_EndSem.pdf",
        total_pages=3,
        year=2025,
        exam_type="End Semester",
        db_path=mem_db,
    )
    assert doc_id == 1

    doc = get_document_by_id(doc_id, db_path=mem_db)
    assert doc is not None
    assert doc["document_id"] == 1
    assert doc["file_name"] == "DBMS_2025_EndSem.pdf"
    assert doc["total_pages"] == 3
    assert doc["year"] == 2025
    assert doc["exam_type"] == "End Semester"


def test_get_all_documents(mem_db):
    insert_document("doc1.pdf", year=2024, db_path=mem_db)
    insert_document("doc2.pdf", year=2025, db_path=mem_db)

    docs = get_all_documents(db_path=mem_db)
    assert len(docs) == 2
    # Ordered descending by document_id
    assert docs[0]["file_name"] == "doc2.pdf"
    assert docs[1]["file_name"] == "doc1.pdf"


# ── Question Operations ──────────────────────────────────────────────────────

def test_insert_single_question_model(mem_db):
    doc_id = insert_document("test.pdf", year=2025, db_path=mem_db)
    q = make_question(
        document_id=doc_id,
        page=1,
        raw_text="Explain ACID properties in DBMS.",
        year=2025,
        exam_type="End Semester",
        section="A",
        marks=5,
        is_compulsory=True,
    )

    q_row_id = insert_question(q, db_path=mem_db)
    assert q_row_id >= 1

    qs = get_questions_by_document(doc_id, db_path=mem_db)
    assert len(qs) == 1
    row = qs[0]
    assert row["question_id"] == q.question_id
    assert row["raw_text"] == "Explain ACID properties in DBMS."
    assert row["marks"] == 5
    assert row["is_compulsory"] == 1
    assert row["cleaned_text"] is None
    assert row["topic_id"] is None
    assert row["repeat_group_id"] is None


def test_insert_questions_batch(mem_db):
    doc_id = insert_document("test.pdf", year=2025, db_path=mem_db)
    q1 = make_question(document_id=doc_id, page=1, raw_text="Q1 text", marks=5)
    q2 = make_question(document_id=doc_id, page=2, raw_text="Q2 text", marks=10)

    count = insert_questions_batch([q1, q2], db_path=mem_db)
    assert count == 2

    qs = get_questions_by_document(doc_id, db_path=mem_db)
    assert len(qs) == 2
    assert qs[0]["page"] == 1
    assert qs[1]["page"] == 2


def test_save_parsed_document_atomic(mem_db):
    q1 = make_question(document_id=0, page=1, raw_text="Q1: Define 3NF.", marks=5)
    q2 = make_question(document_id=0, page=1, raw_text="Q2: What is BCNF?", marks=5)
    parsed_doc = ParsedDocument(
        document_id=0,
        year=2025,
        exam_type="End Semester",
        total_pages=2,
        questions=[q1, q2],
    )

    doc_id = save_parsed_document(
        parsed_doc=parsed_doc,
        file_name="DBMS_Exam_2025.pdf",
        file_path="/docs/DBMS_Exam_2025.pdf",
        db_path=mem_db,
    )
    assert doc_id == 1

    doc = get_document_by_id(doc_id, db_path=mem_db)
    assert doc["year"] == 2025
    assert doc["total_pages"] == 2

    qs = get_questions_by_document(doc_id, db_path=mem_db)
    assert len(qs) == 2
    assert qs[0]["document_id"] == 1
    assert qs[0]["year"] == 2025
    assert qs[1]["document_id"] == 1


def test_get_questions_by_year(mem_db):
    doc1 = insert_document("2024.pdf", year=2024, db_path=mem_db)
    doc2 = insert_document("2025.pdf", year=2025, db_path=mem_db)

    insert_question(make_question(document_id=doc1, page=1, raw_text="2024 Q1", year=2024), db_path=mem_db)
    insert_question(make_question(document_id=doc2, page=1, raw_text="2025 Q1", year=2025), db_path=mem_db)
    insert_question(make_question(document_id=doc2, page=1, raw_text="2025 Q2", year=2025), db_path=mem_db)

    qs_2024 = get_questions_by_year(2024, db_path=mem_db)
    qs_2025 = get_questions_by_year(2025, db_path=mem_db)

    assert len(qs_2024) == 1
    assert len(qs_2025) == 2


def test_get_all_questions(mem_db):
    doc1 = insert_document("2024.pdf", year=2024, db_path=mem_db)
    insert_question(make_question(document_id=doc1, page=1, raw_text="Q1", year=2024), db_path=mem_db)
    insert_question(make_question(document_id=doc1, page=1, raw_text="Q2", year=2024), db_path=mem_db)

    all_qs = get_all_questions(db_path=mem_db)
    assert len(all_qs) == 2


# ── Topic Operations ─────────────────────────────────────────────────────────

def test_topics_batch_insert_and_get(mem_db):
    topics = [
        Topic(topic_code="DBMS-01", name="Introduction to DBMS", syllabus_unit="Unit 1"),
        Topic(topic_code="DBMS-02", name="Relational Algebra", syllabus_unit="Unit 1"),
        Topic(topic_code="DBMS-03", name="SQL and Normalization", syllabus_unit="Unit 2"),
    ]

    count = insert_topics_batch(topics, db_path=mem_db)
    assert count == 3

    fetched = get_all_topics(db_path=mem_db)
    assert len(fetched) == 3
    assert fetched[0]["topic_code"] == "DBMS-01"
    assert fetched[1]["topic_code"] == "DBMS-02"
    assert fetched[2]["topic_code"] == "DBMS-03"


def test_topics_upsert_on_conflict(mem_db):
    topics = [
        Topic(topic_code="DBMS-01", name="Old Name", syllabus_unit="Unit 1"),
    ]
    insert_topics_batch(topics, db_path=mem_db)

    # Upsert with updated name
    topics_updated = [
        Topic(topic_code="DBMS-01", name="Updated DBMS Intro", syllabus_unit="Unit 1"),
    ]
    insert_topics_batch(topics_updated, db_path=mem_db)

    fetched = get_all_topics(db_path=mem_db)
    assert len(fetched) == 1
    assert fetched[0]["name"] == "Updated DBMS Intro"


# ── Foreign Key & Integrity Tests ───────────────────────────────────────────

def test_foreign_key_cascade_delete(mem_db):
    doc_id = insert_document("test.pdf", year=2025, db_path=mem_db)
    insert_question(make_question(document_id=doc_id, page=1, raw_text="Q1"), db_path=mem_db)
    insert_question(make_question(document_id=doc_id, page=1, raw_text="Q2"), db_path=mem_db)

    # Questions exist
    assert len(get_questions_by_document(doc_id, db_path=mem_db)) == 2

    # Delete document
    conn = get_connection(mem_db)
    conn.execute("DELETE FROM documents WHERE document_id = ?", (doc_id,))
    conn.commit()
    conn.close()

    # Questions should be CASCADE deleted
    assert len(get_questions_by_document(doc_id, db_path=mem_db)) == 0


def test_invalid_foreign_key_fails(mem_db):
    # Inserting question with nonexistent document_id should fail FK check
    q = make_question(document_id=99999, page=1, raw_text="Orphan question")
    with pytest.raises(sqlite3.IntegrityError):
        insert_question(q, db_path=mem_db)
