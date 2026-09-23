"""Small helpers: input validation and joining the shared-contract tables.

Schema note (confirmed Week 1, from Members 3/4/6):
  - Question.year and Question.marks are BOTH nullable. year is set once per
    document (missing only if upload metadata is missing); marks can be null
    when a paper shares one mark value across alternative/optional sub-questions,
    or if parsing missed it.
  - Question.topic_id is null until topic classification runs (Member 4), and
    stays null if no confident topic is found. Same convention for
    Question.repeat_group_id: null unless the question belongs to a 2+ group.
  - Notes link to topics through a separate `note_topics` table
    (note_id, topic_id) -- NOT a topic_ids column on Note. This differs from
    Member 6's draft schema, which still lists topic_ids on Note; that needs
    to be resolved with the team (see FORMULAS.md section 4).
"""
import json
import math
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "topics": {"id", "name", "syllabus_unit"},
    "questions": {"id", "year", "marks", "text", "topic_id"},
    "notes": {"id", "lecture_date"},
    "note_topics": {"note_id", "topic_id"},
}


def validate_inputs(topics: pd.DataFrame, questions: pd.DataFrame, notes: pd.DataFrame,
                     note_topics: pd.DataFrame | None = None) -> None:
    """Fail early with a clear message if a teammate's table is missing a column."""
    tables = {"topics": topics, "questions": questions, "notes": notes}
    if note_topics is not None:
        tables["note_topics"] = note_topics
    for name, df in tables.items():
        missing = REQUIRED_COLUMNS[name] - set(df.columns)
        if missing:
            raise ValueError(f"'{name}' table is missing columns: {sorted(missing)}")


def note_topic_counts(notes: pd.DataFrame, note_topics: pd.DataFrame | None) -> pd.Series:
    """Number of notes tagged with each topic_id, via the note_topics link table.
    Falls back to a legacy `topic_ids` column on `notes` (list/JSON/CSV string)
    if no link table is supplied, so older data or quick tests still work."""
    if note_topics is not None:
        return note_topics.drop_duplicates(["note_id", "topic_id"])["topic_id"].value_counts()

    if "topic_ids" in notes.columns:
        counts: dict[int, int] = {}
        for value in notes["topic_ids"]:
            for tid in _parse_legacy_topic_ids(value):
                counts[tid] = counts.get(tid, 0) + 1
        return pd.Series(counts, dtype="int64")

    return pd.Series(dtype="int64")


def _parse_legacy_topic_ids(value: Any) -> list[int]:
    """Legacy fallback only: Note.topic_ids as a list, JSON string '[1, 2]',
    CSV string '1,2', a single int, or empty/NaN."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        return [int(v) for v in value]
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return [int(value)]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        return [int(v) for v in json.loads(text)]
    return [int(v) for v in text.split(",") if v.strip()]


def data_quality_report(questions: pd.DataFrame) -> dict:
    """Counts of missing year/marks, so gaps in Member 3's parsing are visible
    rather than silently zeroed out in the stats."""
    n = len(questions)
    return {
        "n_questions": n,
        "missing_year": int(questions["year"].isna().sum()),
        "missing_marks": int(questions["marks"].isna().sum()),
        "missing_topic_id": int(questions["topic_id"].isna().sum()),
        "note": ("Questions with missing year are excluded from year-based stats "
                 "(coverage, planner). Questions with missing marks are treated as "
                 "0 marks in sums, which understates expected_marks -- get these "
                 "backfilled where possible."),
    }


def to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN -> None, numpy types -> python)."""
    clean = df.astype(object).where(df.notna(), None)
    return json.loads(clean.to_json(orient="records"))
