"""Back-test: the one tool that actually tells you whether the 'due score'
heuristic in topic_stats.py is worth keeping (see FORMULAS.md section 1).

Method -- leave-one-year-out: for each exam year Y with at least
`min_prior_years` years of papers before it, compute topic priority using
ONLY data from before Y (exactly as if Y hadn't happened yet), then check
against what was ACTUALLY asked in Y. Two metrics per year:

  top_k_marks_captured_pct  -- of all marks actually awarded in year Y,
      what share came from the top-K topics the model would have told you
      to prioritise? Higher is better; this is the number that matters for
      "would following the planner's advice have paid off."

  priority_vs_actual_marks_spearman -- rank correlation between predicted
      priority (before Y) and actual marks earned per topic (in Y), across
      ALL topics, not just the top K. Captures whether the ranking is
      sensible throughout, not just at the very top.

Running this with due_weight=0 vs the configured due_weight and comparing
the aggregate metrics is the honest test of the due-score heuristic: if the
boost doesn't improve (or actively hurts) these numbers, FORMULAS.md says to
report that plainly rather than keep a heuristic that doesn't earn its
complexity.
"""
from dataclasses import replace

import pandas as pd

from .config import DEFAULT_PARAMS, Params
from .topic_stats import compute_topic_stats
from .utils import validate_inputs

_EMPTY_NOTES = pd.DataFrame(columns=["id", "lecture_date"])


def backtest_single_year(
    topics: pd.DataFrame,
    questions: pd.DataFrame,
    held_out_year: int,
    params: Params = DEFAULT_PARAMS,
    top_k: int = 5,
) -> dict | None:
    """One fold: train on years before `held_out_year`, score against what
    was actually asked that year. Returns None if there's no prior data to
    train on (can't backtest the very first year in the dataset)."""
    dated = questions.dropna(subset=["year"]).copy()
    dated["year"] = dated["year"].astype(int)

    prior = dated[dated["year"] < held_out_year]
    held = dated[dated["year"] == held_out_year]
    if prior["year"].nunique() == 0 or held.empty:
        return None

    stats = compute_topic_stats(topics, prior, _EMPTY_NOTES, None, params, ref_year=held_out_year)
    stats = stats.set_index("topic_id")

    held_marks = (held.dropna(subset=["marks", "topic_id"])
                  .assign(topic_id=lambda d: d["topic_id"].astype(int))
                  .groupby("topic_id")["marks"].sum())
    held_marks = held_marks.reindex(stats.index).fillna(0)
    total_held_marks = float(held_marks.sum())

    ranked = stats.sort_values("priority", ascending=False)
    top_k_ids = ranked.head(top_k).index
    top_k_marks = float(held_marks.reindex(top_k_ids).sum())
    top_k_pct = round(100 * top_k_marks / total_held_marks, 1) if total_held_marks > 0 else None

    if stats["priority"].nunique() > 1 and held_marks.nunique() > 1:
        corr = stats["priority"].corr(held_marks, method="spearman")
        corr = round(float(corr), 3) if pd.notna(corr) else None
    else:
        corr = None

    return {
        "held_out_year": held_out_year,
        "n_prior_years": int(prior["year"].nunique()),
        "top_k": top_k,
        "top_k_marks_captured_pct": top_k_pct,
        "priority_vs_actual_marks_spearman": corr,
        "total_held_out_marks": total_held_marks,
    }


def run_backtest(
    topics: pd.DataFrame,
    questions: pd.DataFrame,
    params: Params = DEFAULT_PARAMS,
    top_k: int = 5,
    min_prior_years: int = 2,
) -> dict:
    """Leave-one-year-out backtest across every eligible year in the data."""
    validate_inputs(topics, questions, _EMPTY_NOTES)
    dated = questions.dropna(subset=["year"])
    years = sorted(int(y) for y in dated["year"].dropna().astype(int).unique())

    per_year = []
    for y in years:
        if sum(1 for yy in years if yy < y) < min_prior_years:
            continue
        result = backtest_single_year(topics, questions, y, params, top_k)
        if result is not None:
            per_year.append(result)

    pct_values = [r["top_k_marks_captured_pct"] for r in per_year if r["top_k_marks_captured_pct"] is not None]
    corr_values = [r["priority_vs_actual_marks_spearman"] for r in per_year
                   if r["priority_vs_actual_marks_spearman"] is not None]

    return {
        "years_tested": [r["held_out_year"] for r in per_year],
        "top_k": top_k,
        "mean_top_k_marks_captured_pct": round(sum(pct_values) / len(pct_values), 1) if pct_values else None,
        "mean_priority_vs_actual_marks_spearman": round(sum(corr_values) / len(corr_values), 3) if corr_values else None,
        "per_year": per_year,
    }


def compare_due_score_contribution(
    topics: pd.DataFrame,
    questions: pd.DataFrame,
    params: Params = DEFAULT_PARAMS,
    top_k: int = 5,
    min_prior_years: int = 2,
) -> dict:
    """Runs the backtest twice -- once with the due-score boost, once with
    due_weight=0 (pure marks-per-hour ranking) -- and reports whether the
    boost actually helps. This is the evidence for or against the heuristic
    described in FORMULAS.md section 1."""
    with_due = run_backtest(topics, questions, params, top_k, min_prior_years)
    without_due = run_backtest(topics, questions, replace(params, due_weight=0.0), top_k, min_prior_years)

    def _delta(a, b):
        return round(a - b, 3) if a is not None and b is not None else None

    pct_delta = _delta(with_due["mean_top_k_marks_captured_pct"], without_due["mean_top_k_marks_captured_pct"])
    corr_delta = _delta(with_due["mean_priority_vs_actual_marks_spearman"],
                        without_due["mean_priority_vs_actual_marks_spearman"])

    if pct_delta is None and corr_delta is None:
        verdict = "Not enough data to compare (need more exam years)."
    elif (pct_delta or 0) > 0.5 or (corr_delta or 0) > 0.02:
        verdict = "The due-score boost helps: it captures more marks and/or ranks topics better than without it."
    elif (pct_delta or 0) < -0.5 or (corr_delta or 0) < -0.02:
        verdict = "The due-score boost HURTS here: plain marks-per-hour ranking performs better on this data."
    else:
        verdict = "The due-score boost makes little difference either way on this data."

    return {
        "with_due_score": with_due,
        "without_due_score": without_due,
        "top_k_marks_captured_pct_delta": pct_delta,
        "spearman_delta": corr_delta,
        "verdict": verdict,
    }
