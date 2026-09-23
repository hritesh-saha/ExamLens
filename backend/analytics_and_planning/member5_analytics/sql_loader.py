"""Reference queries for Member 6's FastAPI layer.

Member 6's plan: query with SQLAlchemy/raw SQL, pd.read_sql into a DataFrame,
pass straight to these functions, return the resulting dict to the frontend.
These are the exact queries against the confirmed schema:

    Document: id, type, source_pages, timestamp, file_path, created_at
    Topic:    id, name, syllabus_unit
    Note:     id, document_id, page, lecture_date, text, latex, confidence
              (NOTE: drop topic_ids from Note -- see FORMULAS.md section 4;
               topics come from note_topics instead)
    Question: id, document_id, page, year, marks, text, topic_id, repeat_group_id
    note_topics (new, per Member 4): note_id, topic_id

Nothing here runs at import time -- it's reference SQL plus one optional
convenience loader for local testing against a real SQLite file.
"""

TOPICS_SQL = "SELECT id, name, syllabus_unit FROM topic"

QUESTIONS_SQL = """
    SELECT id, document_id, page, year, marks, text, topic_id, repeat_group_id
    FROM question
"""

NOTES_SQL = "SELECT id, document_id, page, lecture_date, text, latex, confidence FROM note"

NOTE_TOPICS_SQL = "SELECT note_id, topic_id FROM note_topics"


def load_from_sqlite(db_path: str):
    """Optional helper for local testing once a real SQLite file exists.
    Not used in production -- Member 6's FastAPI layer does its own pd.read_sql."""
    import sqlite3
    import pandas as pd

    with sqlite3.connect(db_path) as conn:
        topics = pd.read_sql(TOPICS_SQL, conn)
        questions = pd.read_sql(QUESTIONS_SQL, conn)
        notes = pd.read_sql(NOTES_SQL, conn)
        note_topics = pd.read_sql(NOTE_TOPICS_SQL, conn)
    return topics, questions, notes, note_topics
