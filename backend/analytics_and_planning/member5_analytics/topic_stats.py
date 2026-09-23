"""Per-topic features shared by coverage, planner and (later) the practice set.
This is the single place where the formulas in FORMULAS.md are implemented."""
import numpy as np
import pandas as pd

from .config import DEFAULT_PARAMS, Params
from .utils import note_topic_counts, validate_inputs


def compute_topic_stats(
    topics: pd.DataFrame,
    questions: pd.DataFrame,
    notes: pd.DataFrame,
    note_topics: pd.DataFrame | None = None,
    params: Params = DEFAULT_PARAMS,
    ref_year: int | None = None,
) -> pd.DataFrame:
    """One row per syllabus topic with frequency, expected marks, due score,
    effort and priority. `ref_year` is the year of the upcoming exam
    (default: latest paper year + 1).

    `note_topics` is the (note_id, topic_id) link table from Member 6's schema.
    If omitted, falls back to a legacy `topic_ids` column on `notes`.

    Questions with a null `year` are excluded from year-based stats (they
    cannot be placed in the topic-by-year matrix). Questions with a null
    `marks` are treated as 0 in sums. Use `utils.data_quality_report` to see
    how many rows that affects.
    """
    validate_inputs(topics, questions, notes, note_topics)

    dated = questions.dropna(subset=["year"]).copy()
    dated["year"] = dated["year"].astype(int)
    dated["marks"] = dated["marks"].fillna(0)

    all_years = sorted(dated["year"].unique())
    n_years = len(all_years)
    if n_years == 0:
        raise ValueError("No questions with a year found; cannot compute statistics.")
    ref_year = ref_year or (max(all_years) + 1)

    topic_ids = topics["id"].tolist()
    in_syllabus = dated[dated["topic_id"].isin(topic_ids)].copy()

    # topic x year matrices (rows = every syllabus topic, columns = every exam year)
    marks_m = (in_syllabus.groupby(["topic_id", "year"])["marks"].sum()
               .unstack(fill_value=0).reindex(index=topic_ids, columns=all_years, fill_value=0))
    count_m = (in_syllabus.groupby(["topic_id", "year"]).size()
               .unstack(fill_value=0).reindex(index=topic_ids, columns=all_years, fill_value=0))

    # recency weights: latest paper = 1, older papers decay by half-life
    ages = np.array([ref_year - 1 - y for y in all_years], dtype=float)
    if params.recency_half_life_years:
        weights = 0.5 ** (ages / params.recency_half_life_years)
    else:
        weights = np.ones_like(ages)

    stats = topics[["id", "name", "syllabus_unit"]].rename(columns={"id": "topic_id"}).copy()
    stats = stats.set_index("topic_id")

    stats["n_questions"] = count_m.sum(axis=1)
    stats["years_asked"] = (count_m > 0).sum(axis=1)
    stats["year_share"] = stats["years_asked"] / n_years
    stats["total_marks"] = marks_m.sum(axis=1)

    # Expected marks in the next paper: recency-weighted average of marks per paper
    stats["expected_marks"] = (marks_m.values * weights).sum(axis=1) / weights.sum()

    # Recency: last year asked and "due" score
    last_asked = count_m.apply(lambda row: max([y for y in all_years if row[y] > 0], default=np.nan), axis=1)
    stats["last_asked_year"] = last_asked
    stats["years_since_last"] = ref_year - last_asked
    usual_gap = n_years / stats["years_asked"].replace(0, np.nan)          # avg years between appearances
    ratio = stats["years_since_last"] / usual_gap
    stats["due_score"] = (ratio.clip(upper=params.due_cap) / params.due_cap).fillna(0.0)

    # Repeats: size of the biggest repeat group in the topic ('asked 4 times').
    # repeat_group_id is null for questions that are not part of a 2+ repeat group (per Member 4).
    if "repeat_group_id" in in_syllabus.columns:
        grp = (in_syllabus.dropna(subset=["repeat_group_id"])
               .groupby(["topic_id", "repeat_group_id"]).size().groupby("topic_id").max())
    else:
        grp = pd.Series(dtype=float)
    stats["max_repeat_count"] = grp.reindex(stats.index)
    stats["max_repeat_count"] = stats["max_repeat_count"].fillna(
        (stats["n_questions"] > 0).astype(int)).astype(int)

    # Notes coverage, via the note_topics link table (or legacy topic_ids column)
    counts = note_topic_counts(notes, note_topics)
    stats["n_notes"] = counts.reindex(stats.index).fillna(0).astype(int)
    stats["has_notes"] = stats["n_notes"] > 0

    # Effort, marks-per-hour, priority
    base = topics.set_index("id")["effort_hours"] if "effort_hours" in topics.columns else params.base_effort_hours
    stats["effort_hours"] = base * np.where(stats["has_notes"], 1.0, params.no_notes_penalty)
    stats["marks_per_hour"] = stats["expected_marks"] / stats["effort_hours"]
    stats["priority"] = stats["marks_per_hour"] * (1 + params.due_weight * stats["due_score"])

    stats["years_since_last"] = stats["years_since_last"].astype("Float64")
    stats["last_asked_year"] = stats["last_asked_year"].astype("Int64")
    return stats.reset_index()
