import pytest

from examlens_analytics import compute_topic_stats
from examlens_analytics.dummy_data import make_dummy_data
from examlens_analytics.utils import data_quality_report
from .conftest import P


def row(stats, tid):
    return stats.set_index("topic_id").loc[tid]


def test_formulas_by_hand(tiny):
    topics, questions, notes, note_topics = tiny
    s = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    t1, t2, t3, t4 = (row(s, i) for i in (1, 2, 3, 4))

    # T1: 4 dated questions worth 5 marks each, + 1 more dated question (null marks -> 0)
    # -> expected 20/4 = 5 (the null-marks row adds a question but 0 marks, so the average is unchanged)
    assert t1.n_questions == 5 and t1.expected_marks == 5.0 and t1.due_score == 0.5
    assert t1.effort_hours == 2.0                      # has notes
    assert t1.marks_per_hour == 2.5
    assert t1.priority == pytest.approx(2.5 * (1 + 0.3 * 0.5))          # 2.875

    # T2: 20 marks over 4 papers -> 5; usual gap 2y, last asked 3y ago -> ratio 1.5 -> due 0.75
    assert t2.expected_marks == 5.0 and t2.due_score == 0.75
    assert t2.effort_hours == 2.5                      # no notes -> x1.25
    assert t2.priority == pytest.approx(2.0 * (1 + 0.3 * 0.75))         # 2.45

    # T3: never asked -> everything zero, never scheduled
    assert t3.n_questions == 0 and t3.expected_marks == 0 and t3.priority == 0

    # T4: 1 year of 4 -> 2/4 = 0.5 expected; usual gap 4y, last 1y ago -> ratio .25 -> due .125
    assert t4.expected_marks == 0.5 and t4.due_score == pytest.approx(0.125)


def test_null_year_question_excluded_null_marks_question_counted_as_zero(tiny):
    topics, questions, notes, note_topics = tiny
    s = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    # 11 questions total; 2 are out-of-syllabus (null/unknown topic), 1 has null year -> excluded entirely.
    # 8 dated, in-syllabus questions should be visible in the per-topic stats.
    assert s["n_questions"].sum() == 8


def test_data_quality_report_counts_nulls(tiny):
    _, questions, _, _ = tiny
    dq = data_quality_report(questions)
    assert dq["n_questions"] == 11
    assert dq["missing_year"] == 1
    assert dq["missing_marks"] == 1
    assert dq["missing_topic_id"] == 1          # the stray null-topic question


def test_recency_weighting_favours_recent_years(tiny):
    from dataclasses import replace
    topics, questions, notes, note_topics = tiny
    decayed = compute_topic_stats(topics, questions, notes, note_topics, params=replace(P, recency_half_life_years=1.0))
    flat = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    # T2 was only asked in 2021-22 (old), so decay must lower its expected marks
    assert row(decayed, 2).expected_marks < row(flat, 2).expected_marks
    # T4 was asked in the latest year, so decay must raise it
    assert row(decayed, 4).expected_marks > row(flat, 4).expected_marks


def test_missing_column_gives_clear_error(tiny):
    topics, questions, notes, note_topics = tiny
    with pytest.raises(ValueError, match="questions"):
        compute_topic_stats(topics, questions.drop(columns="marks"), notes, note_topics, params=P)


def test_runs_on_dummy_data():
    topics, questions, notes, note_topics = make_dummy_data()
    s = compute_topic_stats(topics, questions, notes, note_topics)
    assert len(s) == 20 and (s["priority"] >= 0).all()


def test_legacy_topic_ids_column_still_works_as_fallback():
    """If a teammate still ships notes.topic_ids instead of a link table, we don't crash."""
    import pandas as pd
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    questions = pd.DataFrame({"id": [1], "year": [2024], "marks": [5], "text": ["q"], "topic_id": [1]})
    notes = pd.DataFrame({"id": [1], "lecture_date": ["2026-01-01"], "topic_ids": ["[1]"]})
    s = compute_topic_stats(topics, questions, notes, note_topics=None, params=P)
    assert row(s, 1).has_notes
