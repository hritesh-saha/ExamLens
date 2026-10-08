"""Coverage gaps: what the exam asks vs what the syllabus and the notes cover."""
import pandas as pd

from .config import DEFAULT_PARAMS, Params
from .topic_stats import compute_topic_stats
from .utils import data_quality_report, to_records, validate_inputs


def never_asked_topics(stats: pd.DataFrame) -> pd.DataFrame:
    """Syllabus topics that never appear in any (dated) past paper."""
    return stats[stats["n_questions"] == 0][["topic_id", "name", "syllabus_unit", "has_notes"]]


def out_of_syllabus_questions(topics: pd.DataFrame, questions: pd.DataFrame) -> pd.DataFrame:
    """Questions with no topic (null - either not yet classified or no confident
    match, per Member 4) or a topic id that is not in the syllabus table."""
    mask = questions["topic_id"].isna() | ~questions["topic_id"].isin(topics["id"])
    cols = [c for c in ("id", "year", "marks", "text", "document_id", "page") if c in questions.columns]
    return questions.loc[mask, cols]


def frequent_without_notes(stats: pd.DataFrame, params: Params = DEFAULT_PARAMS) -> pd.DataFrame:
    """Frequently asked topics that have no lecture notes yet - the most valuable gap."""
    hit = stats[(stats["year_share"] >= params.frequent_year_share) & (~stats["has_notes"])]
    cols = ["topic_id", "name", "syllabus_unit", "years_asked", "year_share",
            "expected_marks", "max_repeat_count"]
    return hit.sort_values("expected_marks", ascending=False)[cols]


def topic_year_heatmap(topics: pd.DataFrame, questions: pd.DataFrame) -> dict:
    """Marks per topic per year, ready for a heatmap (rows = topics, cols = years).
    Questions with a null year cannot be placed and are excluded."""
    dated = questions.dropna(subset=["year"]).copy()
    dated["year"] = dated["year"].astype(int)
    dated["marks"] = dated["marks"].fillna(0)
    years = [int(y) for y in sorted(dated["year"].unique())]
    q = dated[dated["topic_id"].isin(topics["id"])]
    m = (q.groupby(["topic_id", "year"])["marks"].sum().unstack(fill_value=0)
         .reindex(index=topics["id"], columns=years, fill_value=0))
    return {
        "years": years,
        "topics": [{"topic_id": int(tid), "name": name, "marks_by_year": [int(v) for v in row]}
                   for tid, name, row in zip(topics["id"], topics["name"], m.values)],
    }


def coverage_report(
    topics: pd.DataFrame,
    questions: pd.DataFrame,
    notes: pd.DataFrame,
    note_topics: pd.DataFrame | None = None,
    params: Params = DEFAULT_PARAMS,
    ref_year: int | None = None,
) -> dict:
    """Everything the Coverage panel needs, as JSON-safe dicts."""
    validate_inputs(topics, questions, notes, note_topics)
    stats = compute_topic_stats(topics, questions, notes, note_topics, params, ref_year)
    total_expected = stats["expected_marks"].sum()
    noted_expected = stats.loc[stats["has_notes"], "expected_marks"].sum()

    return {
        "summary": {
            "n_topics": len(stats),
            "n_topics_asked": int((stats["n_questions"] > 0).sum()),
            "n_topics_with_notes": int(stats["has_notes"].sum()),
            "n_questions": len(questions),
            "n_out_of_syllabus": int(len(out_of_syllabus_questions(topics, questions))),
            # share of likely exam marks that the current notes actually cover
            "expected_marks_covered_by_notes_pct": round(100 * noted_expected / total_expected, 1) if total_expected else 0.0,
        },
        "data_quality": data_quality_report(questions),
        "never_asked_topics": to_records(never_asked_topics(stats)),
        "out_of_syllabus_questions": to_records(out_of_syllabus_questions(topics, questions)),
        "frequent_without_notes": to_records(frequent_without_notes(stats, params).round(3)),
        "heatmap": topic_year_heatmap(topics, questions),
    }
