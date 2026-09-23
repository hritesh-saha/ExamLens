from .config import DEFAULT_PARAMS, Params
from .coverage import coverage_report
from .planner import build_study_plan, plan_from_tables
from .topic_stats import compute_topic_stats

__all__ = ["DEFAULT_PARAMS", "Params", "compute_topic_stats",
           "coverage_report", "build_study_plan", "plan_from_tables",
           "get_coverage_gaps", "generate_study_plan"]


def _empty_notes():
    import pandas as pd
    return pd.DataFrame(columns=["id", "lecture_date"])


def _empty_note_topics():
    import pandas as pd
    return pd.DataFrame(columns=["note_id", "topic_id"])


def get_coverage_gaps(topics_df, notes_df, questions_df, note_topics_df=None,
                       params: Params = DEFAULT_PARAMS, ref_year: int | None = None) -> dict:
    """Entry point for app/routers/analytics.py's /api/analytics/coverage.
    Argument order matches the router's existing call convention
    (topics, notes, questions); note_topics_df is the new NoteTopic table."""
    if note_topics_df is None:
        note_topics_df = _empty_note_topics()
    return coverage_report(topics_df, questions_df, notes_df, note_topics_df, params, ref_year)


def generate_study_plan(topics_df, questions_df, days_left, hours_per_day,
                        notes_df=None, note_topics_df=None,
                        params: Params = DEFAULT_PARAMS, ref_year: int | None = None) -> dict:
    """Entry point for app/routers/analytics.py's /api/analytics/planner.
    notes_df/note_topics_df are optional so the planner still runs (with the
    no-notes effort penalty applied to every topic) even before Notes exist."""
    if notes_df is None:
        notes_df = _empty_notes()
    if note_topics_df is None:
        note_topics_df = _empty_note_topics()
    return plan_from_tables(topics_df, questions_df, notes_df, days_left, hours_per_day,
                            note_topics_df, params, ref_year)
