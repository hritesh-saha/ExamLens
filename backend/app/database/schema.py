"""
schema.py
=========
SQL table definitions for the ExamLens database.

Three tables — each maps exactly to the agreed data contract:

  documents  — one row per PDF that was parsed
  questions  — one row per extracted question (Member 3 fills these)
  topics     — one row per syllabus topic (Member 4 reads these)

Design rules:
  - SQLite types: TEXT, INTEGER, REAL, BLOB, NULL
  - All columns that can be NULL use DEFAULT NULL explicitly
  - columns filled by Member 4 are nullable (cleaned_text, topic_id, repeat_group_id)
  - Foreign keys are enabled at connection time (see db.py)

Schema overview:
                 ┌──────────────┐
                 │  documents   │
                 │──────────────│
                 │ document_id  │◄──────────────────┐
                 │ file_name    │                   │
                 │ parsed_at    │                   │
                 │ total_pages  │                   │
                 │ year         │                   │
                 │ exam_type    │                   │
                 └──────────────┘                   │
                                                    │
  ┌──────────────┐              ┌───────────────────┤
  │    topics    │              │     questions     │
  │──────────────│              │───────────────────│
  │ topic_id     │◄─────────── │ topic_id (FK)     │
  │ topic_code   │             │ document_id (FK)  ├──┘
  │ name         │             │ question_id       │
  │ syllabus_unit│             │ page              │
  └──────────────┘             │ raw_text          │
                               │ cleaned_text      │ ← Member 4
                               │ year              │
                               │ exam_type         │
                               │ section           │
                               │ marks             │
                               │ is_compulsory     │
                               │ repeat_group_id   │ ← Member 4
                               └───────────────────┘
"""

# ── documents table ────────────────────────────────────────────────────────────
CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    document_id   INTEGER  PRIMARY KEY AUTOINCREMENT,
    file_name     TEXT     NOT NULL,
    file_path     TEXT     DEFAULT NULL,
    parsed_at     TEXT     NOT NULL DEFAULT (datetime('now')),
    total_pages   INTEGER  DEFAULT 0,
    year          INTEGER  DEFAULT NULL,
    exam_type     TEXT     DEFAULT NULL
);
"""

# ── topics table ───────────────────────────────────────────────────────────────
# Loaded once from the syllabus CSV by syllabus/loader.py.
# Member 4 reads this table to assign topic_id to each question.
CREATE_TOPICS_TABLE = """
CREATE TABLE IF NOT EXISTS topics (
    topic_id      INTEGER  PRIMARY KEY AUTOINCREMENT,
    topic_code    TEXT     NOT NULL UNIQUE,
    name          TEXT     NOT NULL,
    syllabus_unit TEXT     NOT NULL
);
"""

# ── questions table ────────────────────────────────────────────────────────────
# One row per extracted question. Member 3 fills all columns except:
#   cleaned_text    → Member 4
#   topic_id        → Member 4
#   repeat_group_id → Member 4
CREATE_QUESTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS questions (
    -- ── Primary key ───────────────────────────────────────────────────────
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,

    -- ── Member 3 fills these ──────────────────────────────────────────────
    question_id      TEXT     NOT NULL UNIQUE,  -- UUID string from parser.py
    document_id      INTEGER  NOT NULL
                              REFERENCES documents(document_id)
                              ON DELETE CASCADE,
    page             INTEGER  NOT NULL CHECK(page >= 1),
    raw_text         TEXT     NOT NULL,
    year             INTEGER  DEFAULT NULL,
    exam_type        TEXT     DEFAULT NULL,
    section          TEXT     DEFAULT NULL,
    marks            INTEGER  DEFAULT NULL CHECK(marks IS NULL OR (marks >= 1 AND marks <= 100)),
    is_compulsory    INTEGER  DEFAULT NULL,  -- 0=False, 1=True, NULL=unknown

    -- ── Member 4 fills these (NULL at creation) ───────────────────────────
    cleaned_text     TEXT     DEFAULT NULL,
    topic_id         INTEGER  DEFAULT NULL
                              REFERENCES topics(topic_id)
                              ON DELETE SET NULL,
    repeat_group_id  INTEGER  DEFAULT NULL,

    -- ── Audit ─────────────────────────────────────────────────────────────
    created_at       TEXT     NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Indexes for common query patterns ─────────────────────────────────────────
# Member 5 will query by document_id, year, topic_id frequently.
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_questions_document_id ON questions(document_id);",
    "CREATE INDEX IF NOT EXISTS idx_questions_year        ON questions(year);",
    "CREATE INDEX IF NOT EXISTS idx_questions_topic_id    ON questions(topic_id);",
    "CREATE INDEX IF NOT EXISTS idx_questions_section     ON questions(section);",
    "CREATE INDEX IF NOT EXISTS idx_topics_code           ON topics(topic_code);",
]

# ── All DDL in order ───────────────────────────────────────────────────────────
# Call schema.get_all_ddl() to get everything needed to initialise the DB.
def get_all_ddl() -> list[str]:
    """
    Return all CREATE TABLE and CREATE INDEX statements in dependency order.
    Safe to run on an already-initialised database (uses IF NOT EXISTS).
    """
    return [
        CREATE_DOCUMENTS_TABLE,
        CREATE_TOPICS_TABLE,
        CREATE_QUESTIONS_TABLE,
        *CREATE_INDEXES,
    ]
