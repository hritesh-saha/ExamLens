import json

import pandas as pd
import pytest

from .. import backtest_single_year, run_backtest, compare_due_score_contribution
from ..dummy_data import make_dummy_data
from .conftest import P


@pytest.fixture
def predictable():
    """T1 is asked every year worth 10 marks -> should always rank #1 and be
    fully captured. T2 is never asked -> should capture 0. Clean enough to
    hand-verify the backtest's own arithmetic, not just that it runs."""
    topics = pd.DataFrame({"id": [1, 2], "name": ["T1", "T2"], "syllabus_unit": ["U1", "U1"]})
    rows = [{"id": i + 1, "year": y, "marks": 10, "text": "q", "topic_id": 1}
            for i, y in enumerate(range(2018, 2026))]
    questions = pd.DataFrame(rows)
    return topics, questions


def test_single_year_perfect_prediction(predictable):
    topics, questions = predictable
    r = backtest_single_year(topics, questions, held_out_year=2022, params=P, top_k=1)
    assert r["top_k_marks_captured_pct"] == 100.0          # T1 is the only topic ever asked
    assert r["total_held_out_marks"] == 10.0
    assert r["n_prior_years"] == 4                          # 2018-2021


def test_single_year_returns_none_with_no_prior_data(predictable):
    topics, questions = predictable
    assert backtest_single_year(topics, questions, held_out_year=2018, params=P) is None


def test_run_backtest_skips_years_without_enough_history(predictable):
    topics, questions = predictable
    r = run_backtest(topics, questions, params=P, top_k=1, min_prior_years=3)
    assert all(y >= 2021 for y in r["years_tested"])        # first 3 years (2018-2020) excluded


def test_run_backtest_perfect_capture_rate(predictable):
    topics, questions = predictable
    r = run_backtest(topics, questions, params=P, top_k=1, min_prior_years=2)
    assert r["mean_top_k_marks_captured_pct"] == 100.0       # T1 always captures all the marks


def test_never_asked_topic_never_hurts_the_always_asked_one(predictable):
    topics, questions = predictable
    r = run_backtest(topics, questions, params=P, top_k=2, min_prior_years=2)  # top_k=2 includes T2 too
    assert r["mean_top_k_marks_captured_pct"] == 100.0       # T2 contributes 0 marks either way


def test_json_serialisable_on_dummy_data():
    topics, questions, notes, note_topics = make_dummy_data()
    r = run_backtest(topics, questions, top_k=5)
    assert len(r["years_tested"]) > 0
    json.dumps(r)


def test_compare_due_score_structure_and_json_safe():
    topics, questions, notes, note_topics = make_dummy_data()
    r = compare_due_score_contribution(topics, questions, top_k=5)
    assert set(r.keys()) == {"with_due_score", "without_due_score",
                             "top_k_marks_captured_pct_delta", "spearman_delta", "verdict"}
    assert isinstance(r["verdict"], str) and len(r["verdict"]) > 0
    json.dumps(r)


def test_compare_due_score_without_due_actually_uses_due_weight_zero():
    """Sanity check the comparison isn't accidentally running the same config twice:
    due_weight=0 must actually change the priority RANKING on real dummy data (even if
    that particular reshuffle doesn't happen to move the top-5 capture % every year)."""
    from dataclasses import replace
    import pandas as pd
    from .. import compute_topic_stats, DEFAULT_PARAMS
    topics, questions, notes, note_topics = make_dummy_data()
    empty_notes = pd.DataFrame(columns=["id", "lecture_date"])
    with_due = compute_topic_stats(topics, questions, empty_notes, None, DEFAULT_PARAMS, ref_year=2024)
    without_due = compute_topic_stats(topics, questions, empty_notes, None,
                                      replace(DEFAULT_PARAMS, due_weight=0.0), ref_year=2024)
    rank_with = with_due.set_index("topic_id")["priority"].rank(ascending=False)
    rank_without = without_due.set_index("topic_id")["priority"].rank(ascending=False)
    assert (rank_with != rank_without).any()


def test_not_enough_years_gives_graceful_empty_result():
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    questions = pd.DataFrame({"id": [1, 2], "year": [2023, 2024], "marks": [5, 5],
                              "text": ["q1", "q2"], "topic_id": [1, 1]})
    r = run_backtest(topics, questions, min_prior_years=5)   # impossible to satisfy with 2 years of data
    assert r["years_tested"] == [] and r["mean_top_k_marks_captured_pct"] is None
