"""
db.py
=====
Database access layer for ExamLens using Python's built-in sqlite3.

Provides functions to:
  - Initialize the SQLite database schema
  - Insert and retrieve documents
  - Insert and retrieve questions (matching the Question contract)
  - Insert and retrieve topics (syllabus)
  - Save full ParsedDocument objects in a single transaction

Key design points:
  - Uses sqlite3.Row for dict-like row access
  - Enforces foreign key constraints (PRAGMA foreign_keys = ON)
  - Fully compatible with Question, ParsedDocument, and Topic Pydantic models
  - Supports in-memory database (":memory:") for fast testing
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.database.schema import get_all_ddl
from app.exam_parser.models import ParsedDocument, Question, Topic

# Default DB location: backend/examlens.db
DEFAULT_DB_PATH = os.environ.get(
    "DATABASE_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "examlens.db")
)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Create and return an SQLite connection with:
      1. Foreign keys enabled (PRAGMA foreign_keys = ON)
      2. Row factory set to sqlite3.Row (dict-like column access)

    Args:
        db_path: Path to SQLite file, or ':memory:'. Defaults to DEFAULT_DB_PATH.
    """
    target = db_path if db_path is not None else DEFAULT_DB_PATH
    if target != ":memory:":
        parent_dir = Path(target).parent
        if parent_dir:
            parent_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize all database tables and indexes defined in schema.py.
    Safe to run repeatedly (uses IF NOT EXISTS).
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        for statement in get_all_ddl():
            cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# DOCUMENTS
# ═══════════════════════════════════════════════════════════════════

def insert_document(
    file_name: str,
    file_path: Optional[str] = None,
    total_pages: int = 0,
    year: Optional[int] = None,
    exam_type: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """
    Insert a document record into the `documents` table.

    Returns:
        document_id (int): Auto-incremented primary key.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (file_name, file_path, total_pages, year, exam_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_name, file_path, total_pages, year, exam_type),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_document_by_id(document_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single document row by its document_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_documents(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all parsed document records."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents ORDER BY document_id DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# QUESTIONS
# ═══════════════════════════════════════════════════════════════════

def _question_to_tuple(q: Union[Question, Dict[str, Any]]) -> tuple:
    """Convert Question object or dict to SQL parameter tuple."""
    if isinstance(q, Question):
        is_comp = None
        if q.is_compulsory is not None:
            is_comp = 1 if q.is_compulsory else 0
        return (
            q.question_id,
            q.document_id,
            q.page,
            q.raw_text,
            q.year,
            q.exam_type,
            q.section,
            q.marks,
            is_comp,
            q.cleaned_text,
            q.topic_id,
            q.repeat_group_id,
        )
    else:
        is_comp = q.get("is_compulsory")
        if isinstance(is_comp, bool):
            is_comp = 1 if is_comp else 0
        return (
            q["question_id"],
            q["document_id"],
            q["page"],
            q["raw_text"],
            q.get("year"),
            q.get("exam_type"),
            q.get("section"),
            q.get("marks"),
            is_comp,
            q.get("cleaned_text"),
            q.get("topic_id"),
            q.get("repeat_group_id"),
        )


def insert_question(question: Union[Question, Dict[str, Any]], db_path: Optional[str] = None) -> int:
    """
    Insert a single question into the `questions` table.

    Returns:
        id (int): Auto-incremented primary key.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO questions (
                question_id, document_id, page, raw_text,
                year, exam_type, section, marks, is_compulsory,
                cleaned_text, topic_id, repeat_group_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _question_to_tuple(question),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def insert_questions_batch(
    questions: List[Union[Question, Dict[str, Any]]],
    db_path: Optional[str] = None
) -> int:
    """
    Insert multiple questions in a single transaction.

    Returns:
        int: Number of questions inserted.
    """
    if not questions:
        return 0

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        tuples = [_question_to_tuple(q) for q in questions]
        cursor.executemany(
            """
            INSERT INTO questions (
                question_id, document_id, page, raw_text,
                year, exam_type, section, marks, is_compulsory,
                cleaned_text, topic_id, repeat_group_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuples,
        )
        conn.commit()
        return len(tuples)
    finally:
        conn.close()


def save_parsed_document(
    parsed_doc: ParsedDocument,
    file_name: str,
    file_path: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """
    Atomically save a ParsedDocument (document record + all its questions)
    in a single database transaction.

    Returns:
        int: The document_id assigned to the document.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # Insert document header
        cursor.execute(
            """
            INSERT INTO documents (file_name, file_path, total_pages, year, exam_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_name, file_path, parsed_doc.total_pages, parsed_doc.year, parsed_doc.exam_type),
        )
        doc_id = cursor.lastrowid

        # Insert questions linked to doc_id
        if parsed_doc.questions:
            # Update questions to ensure document_id matches the created doc_id
            tuples = []
            for q in parsed_doc.questions:
                is_comp = None
                if q.is_compulsory is not None:
                    is_comp = 1 if q.is_compulsory else 0
                tuples.append((
                    q.question_id,
                    doc_id,  # Link to the newly generated document_id
                    q.page,
                    q.raw_text,
                    q.year if q.year is not None else parsed_doc.year,
                    q.exam_type if q.exam_type is not None else parsed_doc.exam_type,
                    q.section,
                    q.marks,
                    is_comp,
                    q.cleaned_text,
                    q.topic_id,
                    q.repeat_group_id,
                ))

            cursor.executemany(
                """
                INSERT INTO questions (
                    question_id, document_id, page, raw_text,
                    year, exam_type, section, marks, is_compulsory,
                    cleaned_text, topic_id, repeat_group_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples,
            )

        conn.commit()
        return doc_id
    finally:
        conn.close()


def get_questions_by_document(document_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all questions for a specific document_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM questions WHERE document_id = ? ORDER BY page ASC, id ASC",
            (document_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_questions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all questions across all documents."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions ORDER BY year DESC, document_id ASC, id ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_questions_by_year(year: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve questions filtered by exam year."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE year = ? ORDER BY id ASC", (year,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# TOPICS (SYLLABUS)
# ═══════════════════════════════════════════════════════════════════

def insert_topics_batch(
    topics: List[Union[Topic, Dict[str, Any]]],
    db_path: Optional[str] = None
) -> int:
    """
    Insert syllabus topics, replacing any with identical topic_code.

    Returns:
        int: Number of topics inserted.
    """
    if not topics:
        return 0

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        tuples = []
        for t in topics:
            if isinstance(t, Topic):
                tuples.append((t.topic_code, t.name, t.syllabus_unit))
            else:
                tuples.append((t["topic_code"], t["name"], t["syllabus_unit"]))

        cursor.executemany(
            """
            INSERT INTO topics (topic_code, name, syllabus_unit)
            VALUES (?, ?, ?)
            ON CONFLICT(topic_code) DO UPDATE SET
                name = excluded.name,
                syllabus_unit = excluded.syllabus_unit
            """,
            tuples,
        )
        conn.commit()
        return len(tuples)
    finally:
        conn.close()


def get_all_topics(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all topics from the syllabus table."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topics ORDER BY topic_code ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
