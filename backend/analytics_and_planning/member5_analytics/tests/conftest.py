import pandas as pd
import pytest

from examlens_analytics.config import Params

# No recency decay + round numbers so every expected value can be checked by hand.
P = Params(base_effort_hours=2.0, no_notes_penalty=1.25, recency_half_life_years=None,
           due_cap=2.0, due_weight=0.3, frequent_year_share=0.4)


@pytest.fixture
def tiny():
    """4 exam years (2021-2024), upcoming exam = 2025.
    T1: 5 marks every year, has notes.       T2: 10 marks in 2021 and 2022, no notes.
    T3: never asked.                         T4: one 2-mark question in 2024, no notes.
    Plus 2 stray questions: topic null and topic id 99 (not in syllabus).
    Plus 1 question with null marks and 1 with null year, to exercise data-quality handling."""
    topics = pd.DataFrame({"id": [1, 2, 3, 4], "name": ["T1", "T2", "T3", "T4"],
                           "syllabus_unit": ["U1", "U1", "U2", "U2"]})
    rows = [(y, 1, 5) for y in (2021, 2022, 2023, 2024)]
    rows += [(2021, 2, 10), (2022, 2, 10), (2024, 4, 2), (2023, None, 5), (2023, 99, 5)]
    questions = pd.DataFrame(rows, columns=["year", "topic_id", "marks"])
    questions.insert(0, "id", range(1, len(questions) + 1))
    questions["text"] = "q"
    questions["topic_id"] = questions["topic_id"].astype("Int64")
    # extra edge-case rows: null marks (alt-question sharing marks elsewhere), null year (bad upload)
    questions = pd.concat([questions, pd.DataFrame([
        {"id": 10, "year": 2024, "topic_id": 1, "marks": None, "text": "q"},
        {"id": 11, "year": None, "topic_id": 1, "marks": 5, "text": "q"},
    ])], ignore_index=True)
    questions["marks"] = questions["marks"].astype("Int64")
    questions["year"] = questions["year"].astype("Int64")

    notes = pd.DataFrame({"id": [1], "lecture_date": ["2026-08-03"]})
    note_topics = pd.DataFrame({"note_id": [1], "topic_id": [1]})
    return topics, questions, notes, note_topics
