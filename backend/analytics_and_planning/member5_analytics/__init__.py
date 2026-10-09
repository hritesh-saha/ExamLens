from .config import DEFAULT_PARAMS, Params
from .coverage import coverage_report
from .planner import build_study_plan, plan_from_tables
from .topic_stats import compute_topic_stats
from .answer_length import add_answer_length_hints, answer_length_hint
from .lecture_timeline import build_lecture_timeline
from .practice_set import generate_practice_set, infer_marks_pattern
from .backtest import backtest_single_year, run_backtest, compare_due_score_contribution

__all__ = ["DEFAULT_PARAMS", "Params", "compute_topic_stats",
           "coverage_report", "build_study_plan", "plan_from_tables",
           "answer_length_hint", "add_answer_length_hints", "build_lecture_timeline",
           "generate_practice_set", "infer_marks_pattern",
           "backtest_single_year", "run_backtest", "compare_due_score_contribution",
           "get_coverage_gaps", "generate_study_plan"]


def _empty_notes():
    import pandas as pd
    return pd.DataFrame(columns=["id", "lecture_date"])


def _empty_note_topics():
    import pandas as pd
    return pd.DataFrame(columns=["note_id", "topic_id"])


def get_coverage_gaps(topics_df, notes_df, questions_df, note_topics_df=None,
                       params: Params = DEFAULT_PARAMS, ref_year: int | None = None) -> dict:
    """Entry point for app/routers/analytics.py's /api/analytics/coverage."""
    if note_topics_df is None:
        note_topics_df = _empty_note_topics()
    return coverage_report(topics_df, questions_df, notes_df, note_topics_df, params, ref_year)


def generate_study_plan(topics_df, questions_df, days_left, hours_per_day,
                        notes_df=None, note_topics_df=None,
                        params: Params = DEFAULT_PARAMS, ref_year: int | None = None) -> dict:
    """Entry point for app/routers/analytics.py's /api/analytics/planner."""
    if notes_df is None:
        notes_df = _empty_notes()
    if note_topics_df is None:
        note_topics_df = _empty_note_topics()
    return plan_from_tables(topics_df, questions_df, notes_df, days_left, hours_per_day,
                            note_topics_df, params, ref_year)
