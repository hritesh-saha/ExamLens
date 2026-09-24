import math

import pandas as pd
import pytest

from examlens_analytics import add_answer_length_hints, answer_length_hint
from examlens_analytics.dummy_data import make_dummy_data
from .conftest import P


def test_anchor_points_are_exact(tiny=None):
    # 2 -> 50, 5 -> 150, 10 -> 300 are the anchors themselves; interpolation must hit them exactly.
    assert answer_length_hint(2, P)["suggested_words"] == 50
    assert answer_length_hint(5, P)["suggested_words"] == 150
    assert answer_length_hint(10, P)["suggested_words"] == 300


def test_interpolation_between_anchors():
    # marks=3 is 1/3 of the way from 2->5 (50->150): 50 + (100/3) = 83.33 -> rounds to 85
    hint = answer_length_hint(3, P)
    assert hint["suggested_words"] == 85


def test_extrapolation_below_and_above_anchors():
    # below the first anchor (2 marks): same slope as the 2->5 segment, extended down
    low = answer_length_hint(1, P)
    high = answer_length_hint(15, P)
    assert 0 < low["suggested_words"] < 50            # less than the 2-mark anchor
    assert high["suggested_words"] > 300               # more than the 10-mark anchor


def test_monotonic_in_marks():
    # more marks should never suggest fewer words
    words = [answer_length_hint(m, P)["suggested_words"] for m in range(1, 21)]
    assert words == sorted(words)


def test_minutes_scale_with_words():
    hint = answer_length_hint(10, P)
    assert hint["suggested_minutes"] == round(hint["suggested_words"] / P.writing_words_per_minute)


@pytest.mark.parametrize("marks", [None, float("nan"), 0, -5])
def test_missing_or_invalid_marks_returns_none(marks):
    assert answer_length_hint(marks, P) is None


def test_bulk_add_to_questions_table():
    questions = pd.DataFrame({
        "id": [1, 2, 3], "year": [2024, 2024, 2024],
        "marks": [2, None, 10], "text": ["q1", "q2", "q3"], "topic_id": [1, 1, 1],
    })
    out = add_answer_length_hints(questions, P)
    assert out.loc[0, "suggested_words"] == 50
    assert pd.isna(out.loc[1, "suggested_words"])       # null marks -> null hint, not crashed
    assert out.loc[2, "suggested_words"] == 300
    assert list(questions.columns) == ["id", "year", "marks", "text", "topic_id"]  # original untouched


def test_runs_on_dummy_data_including_null_marks_rows():
    _, questions, _, _ = make_dummy_data()
    out = add_answer_length_hints(questions)
    assert out["suggested_words"].isna().sum() == questions["marks"].isna().sum()
