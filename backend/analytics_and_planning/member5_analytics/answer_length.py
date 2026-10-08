"""Answer-length hints: map a question's marks to a suggested word count and
writing time, shown on the practice set and flashcards (project brief section
2, Member 5's ownership).

Design: piecewise-linear interpolation/extrapolation between a small set of
anchor points (marks, words) from the project brief -- 2 marks ~ 50 words,
5 ~ 150, 10 ~ 300 -- rather than a flat "words per mark" ratio, because real
mark schemes are not perfectly linear (a 2-mark "define X" needs relatively
more words per mark than a 10-mark "discuss X in detail" does).
"""
import math

import pandas as pd

from .config import DEFAULT_PARAMS, Params


def _interp_words(marks: float, anchors: tuple[tuple[int, int], ...]) -> float:
    """Piecewise-linear interpolate within the anchors; extrapolate using the
    slope of the nearest segment for marks outside the anchor range."""
    xs = [a[0] for a in anchors]
    ys = [a[1] for a in anchors]

    if marks <= xs[0]:
        slope = (ys[1] - ys[0]) / (xs[1] - xs[0])
        words = ys[0] + slope * (marks - xs[0])
    elif marks >= xs[-1]:
        slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
        words = ys[-1] + slope * (marks - xs[-1])
    else:
        for i in range(len(xs) - 1):
            if xs[i] <= marks <= xs[i + 1]:
                slope = (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])
                words = ys[i] + slope * (marks - xs[i])
                break
    return max(0.0, words)


def answer_length_hint(marks, params: Params = DEFAULT_PARAMS) -> dict | None:
    """One question's marks -> {suggested_words, suggested_minutes}.
    Returns None if marks is missing or not positive (nothing to suggest)."""
    if marks is None or (isinstance(marks, float) and math.isnan(marks)) or marks <= 0:
        return None
    words = _interp_words(float(marks), params.answer_length_anchors)
    words = int(round(words / 5.0) * 5)                          # round to nearest 5 for readability
    minutes = round(words / params.writing_words_per_minute)
    return {"suggested_words": words, "suggested_minutes": minutes}


def add_answer_length_hints(questions: pd.DataFrame, params: Params = DEFAULT_PARAMS) -> pd.DataFrame:
    """Adds suggested_words / suggested_minutes columns to a copy of the
    questions table. Rows with missing/invalid marks get <NA> in both columns."""
    out = questions.copy()
    hints = out["marks"].apply(lambda m: answer_length_hint(m, params))
    out["suggested_words"] = hints.apply(lambda h: h["suggested_words"] if h else None)
    out["suggested_minutes"] = hints.apply(lambda h: h["suggested_minutes"] if h else None)
    out["suggested_words"] = out["suggested_words"].astype("Int64")
    out["suggested_minutes"] = out["suggested_minutes"].astype("Int64")
    return out
