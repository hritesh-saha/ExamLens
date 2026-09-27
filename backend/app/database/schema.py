"""
schema.py
=========
SQL table definitions for the ExamLens database.

Three tables — each maps exactly to the agreed data contract:

  Document   — one row per PDF that was parsed
  Question   — one row per extracted question (Member 3 fills these)
  Topic      — one row per syllabus topic (Member 4 reads these)

Design rules:
  - SQLite types: TEXT, INTEGER, REAL, BLOB, NULL
  - All columns that can be NULL use DEFAULT NULL explicitly
  - Columns filled by Member 4 are nullable (cleaned_text, topic_id, repeat_group_id)
  - Foreign keys are enabled at connection time (see db.py)
  - Table names are capitalized to match Member 6's SQLAlchemy models.py

Schema overview:
                 ┌──────────────┐
                 │   Document   │
                 │──────────────│
                 │ id           │◄──────────────────┐
                 │ type         │                   │
                 │ file_name    │                   │
                 │ file_path    │                   │
                 │ source_pages │                   │
                 │ timestamp    │                   │
                 │ year         │                   │
                 │ exam_type    │                   │
                 │ created_at   │                   │
                 └──────────────┘                   │
                                                    │
  ┌──────────────┐              ┌───────────────────┤
  │    Topic     │              │     Question      │
  │──────────────│              │───────────────────│
  │ id           │◄─────────── │ topic_id (FK)     │
  │ topic_code   │             │ document_id (FK)  ├──┘
  │ name         │             │ question_id       │
  │ syllabus_unit│             │ id                │
  └──────────────┘             │ page              │
                               │ text              │
                               │ cleaned_text      │ ← Member 4
                               │ year              │
                               │ exam_type         │
                               │ section           │
                               │ marks             │
                               │ is_compulsory     │
                               │ repeat_group_id   │ ← Member 4
                               └───────────────────┘
"""

# ── Document table ──────────────────────────────────────────────────────────────
# Matches Member 6's capitalized table name and column conventions.
# Extra columns (file_name, year, exam_type) are Member 3 additions — nullable.
CREATE_DOCUMENT_TABLE = """
CREATE TABLE IF NOT EXISTS Document (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    type          TEXT     DEFAULT NULL,              -- "lecture_board" or "question_paper"
    file_name     TEXT     NOT NULL,
    file_path     TEXT     DEFAULT NULL,
    source_pages  INTEGER  DEFAULT 0,
    timestamp     TEXT     DEFAULT NULL,              -- stores lecture date (matches Member 6)
    year          INTEGER  DEFAULT NULL,
    exam_type     TEXT     DEFAULT NULL,
    created_at    TEXT     NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Topic table ─────────────────────────────────────────────────────────────────
# Loaded once from the syllabus CSV by syllabus/loader.py.
# Member 4 reads this table to assign topic_id to each question.
# topic_code is kept as a UNIQUE identifier used by the loader and upsert logic.
CREATE_TOPIC_TABLE = """
CREATE TABLE IF NOT EXISTS Topic (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    topic_code    TEXT     NOT NULL UNIQUE,
    name          TEXT     NOT NULL,
    syllabus_unit TEXT     NOT NULL
);
"""

# ── Question table ──────────────────────────────────────────────────────────────
# One row per extracted question. Member 3 fills all columns except:
#   cleaned_text    → Member 4
#   topic_id        → Member 4
#   repeat_group_id → Member 4
# FK targets now match Member 6's capitalized table names and id PKs.
CREATE_QUESTION_TABLE = """
CREATE TABLE IF NOT EXISTS Question (
    -- ── Primary key ───────────────────────────────────────────────────────
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,

    -- ── Member 3 fills these ──────────────────────────────────────────────
    question_id      TEXT     NOT NULL UNIQUE,  -- UUID string from parser.py
    document_id      INTEGER  NOT NULL
                              REFERENCES Document(id)
                              ON DELETE CASCADE,
    page             INTEGER  NOT NULL CHECK(page >= 1),
    text             TEXT     NOT NULL,          -- raw OCR text (renamed from raw_text)
    year             INTEGER  DEFAULT NULL,
    exam_type        TEXT     DEFAULT NULL,
    section          TEXT     DEFAULT NULL,
    marks            INTEGER  DEFAULT NULL CHECK(marks IS NULL OR (marks >= 1 AND marks <= 100)),
    is_compulsory    INTEGER  DEFAULT NULL,       -- 0=False, 1=True, NULL=unknown

    -- ── Member 4 fills these (NULL at creation) ───────────────────────────
    cleaned_text     TEXT     DEFAULT NULL,
    topic_id         INTEGER  DEFAULT NULL
                              REFERENCES Topic(id)
                              ON DELETE SET NULL,
    repeat_group_id  INTEGER  DEFAULT NULL,

    -- ── Audit ─────────────────────────────────────────────────────────────
    created_at       TEXT     NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Indexes for common query patterns ─────────────────────────────────────────
# Member 5 will query by document_id, year, topic_id frequently.
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_questions_document_id ON Question(document_id);",
    "CREATE INDEX IF NOT EXISTS idx_questions_year        ON Question(year);",
    "CREATE INDEX IF NOT EXISTS idx_questions_topic_id    ON Question(topic_id);",
    "CREATE INDEX IF NOT EXISTS idx_questions_section     ON Question(section);",
    "CREATE INDEX IF NOT EXISTS idx_topics_code           ON Topic(topic_code);",
]

# ── All DDL in order ───────────────────────────────────────────────────────────
# Call schema.get_all_ddl() to get everything needed to initialise the DB.
def get_all_ddl() -> list[str]:
    """
    Return all CREATE TABLE and CREATE INDEX statements in dependency order.
    Safe to run on an already-initialised database (uses IF NOT EXISTS).
    """
    return [
        CREATE_DOCUMENT_TABLE,
        CREATE_TOPIC_TABLE,
        CREATE_QUESTION_TABLE,
        *CREATE_INDEXES,
    ]
