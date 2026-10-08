"""Practice set generator: build a mock paper from real past questions on
likely topics, with a marks distribution similar to history (project brief
section 2, Member 5's ownership).

Design notes:
  - "Likely topics" reuses the same `priority` score as the study planner
    (expected_marks x due-score boost), but computed with an EMPTY notes
    table on purpose. The planner should favour topics the student hasn't
    covered yet (that's its job); a practice paper should not -- whether a
    topic happens to have notes is irrelevant to whether it's likely to be
    asked, so note-availability is deliberately excluded from this ranking.
  - Every question in the output is a REAL past question (never generated
    text), per the brief. If a marks value in the target pattern has no real
    question left to draw from a topic, that slot is reported as unfilled
    rather than inventing one.
  - The marks pattern (how many 2-mark, 5-mark, 10-mark... questions a paper
    typically has) is inferred from history: the median count per marks
    value across all past papers, rounded to the nearest whole question.
"""
import numpy as np
import pandas as pd

from .answer_length import answer_length_hint
from .config import DEFAULT_PARAMS, Params
from .topic_stats import compute_topic_stats
from .utils import validate_inputs


def infer_marks_pattern(questions: pd.DataFrame) -> dict:
    """How many questions of each marks value a typical past paper has,
    as {marks: count}. Based on the median across all dated papers that
    have a marks value recorded; zero-count marks values are dropped."""
    dated = questions.dropna(subset=["year", "marks"]).copy()
    if dated.empty:
        return {}
    dated["year"] = dated["year"].astype(int)
    dated["marks"] = dated["marks"].astype(int)
    per_paper = dated.groupby(["year", "marks"]).size().unstack(fill_value=0)
    medians = per_paper.median(axis=0).round().astype(int)
    return {int(m): int(c) for m, c in medians.items() if c > 0}


def generate_practice_set(
    topics: pd.DataFrame,
    questions: pd.DataFrame,
    params: Params = DEFAULT_PARAMS,
    ref_year: int | None = None,
    seed: int | None = None,
) -> dict:
    """A mock paper: real past questions, weighted toward likely topics,
    with a marks distribution matching history. `seed` makes the topic/
    question draw reproducible (e.g. for tests); omit it for a fresh
    random paper each call."""
    empty_notes = pd.DataFrame(columns=["id", "lecture_date"])
    validate_inputs(topics, questions, empty_notes)

    pattern = infer_marks_pattern(questions)
    if not pattern:
        return {"questions": [], "summary": {
            "n_questions": 0, "total_marks": 0, "typical_paper_marks": None,
            "n_reused_questions": 0, "n_unfilled_slots": 0, "unfilled_slots": [],
            "topics_covered": [],
        }}

    stats = compute_topic_stats(topics, questions, empty_notes, None, params, ref_year)
    priority = stats.set_index("topic_id")["priority"].clip(lower=0)
    rng = np.random.default_rng(seed)

    dated = questions.dropna(subset=["year", "marks", "topic_id"]).copy()
    dated["marks"] = dated["marks"].astype(int)
    dated["topic_id"] = dated["topic_id"].astype(int)
    dated = dated[dated["topic_id"].isin(topics["id"])]

    used_ids: set = set()
    paper, unfilled = [], []

    for marks, count in sorted(pattern.items()):
        pool_m = dated[dated["marks"] == marks]
        for _ in range(count):
            available = pool_m[~pool_m["id"].isin(used_ids)]
            reused = False
            if available.empty:
                if pool_m.empty:
                    unfilled.append({"marks": marks, "reason": "no past question with this marks value"})
                    continue
                available = pool_m                              # allow reuse rather than leave the slot empty
                reused = True

            topic_ids = available["topic_id"].unique().astype(np.int64)
            weights = priority.reindex(topic_ids).fillna(0.0).to_numpy(dtype=np.float64)
            weights = weights if weights.sum() > 0 else np.ones(len(topic_ids), dtype=np.float64)
            chosen_topic = int(rng.choice(topic_ids, p=weights / weights.sum()))

            topic_pool = available[available["topic_id"] == chosen_topic]
            row = topic_pool.sample(n=1, random_state=int(rng.integers(0, 2**31))).iloc[0]
            used_ids.add(row["id"])

            topic_name = topics.set_index("id").loc[chosen_topic, "name"]
            hint = answer_length_hint(marks, params)
            paper.append({
                "question_id": int(row["id"]), "marks": marks,
                "topic_id": int(chosen_topic), "topic_name": topic_name,
                "text": row["text"], "year_asked": int(row["year"]),
                "reused_question": reused,
                "suggested_words": hint["suggested_words"] if hint else None,
                "suggested_minutes": hint["suggested_minutes"] if hint else None,
            })

    total_marks = sum(q["marks"] for q in paper)
    hist_totals = dated.dropna(subset=["marks"]).groupby("year")["marks"].sum() if not dated.empty else pd.Series(dtype=float)

    return {
        "questions": paper,
        "summary": {
            "n_questions": len(paper),
            "total_marks": int(total_marks),
            "typical_paper_marks": round(float(hist_totals.median()), 1) if len(hist_totals) else None,
            "n_reused_questions": sum(1 for q in paper if q["reused_question"]),
            "n_unfilled_slots": len(unfilled),
            "unfilled_slots": unfilled,
            "topics_covered": sorted({q["topic_name"] for q in paper}),
        },
    }
