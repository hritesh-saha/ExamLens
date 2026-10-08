"""Study planner v1: greedy pick by priority (marks per hour, boosted by 'due'),
then lay the chosen topics out day by day."""
import pandas as pd

from .config import DEFAULT_PARAMS, Params
from .topic_stats import compute_topic_stats
from .utils import validate_inputs


def build_study_plan(
    stats: pd.DataFrame,
    days_left: int,
    hours_per_day: float,
) -> dict:
    """`stats` is the output of compute_topic_stats. Returns a JSON-safe plan."""
    if days_left <= 0 or hours_per_day <= 0:
        raise ValueError("days_left and hours_per_day must both be positive.")

    budget = days_left * hours_per_day
    candidates = stats[stats["priority"] > 0].sort_values("priority", ascending=False)

    # 1) Greedy selection: highest priority first, skip a topic that no longer fits, keep going.
    chosen, remaining = [], budget
    for row in candidates.itertuples():
        if row.effort_hours <= remaining + 1e-9:
            chosen.append(row)
            remaining -= row.effort_hours

    # 2) Lay chosen topics onto days in priority order; a topic may spill over to the next day.
    days = [{"day": d + 1, "hours_used": 0.0, "blocks": []} for d in range(days_left)]
    day_idx = 0
    for row in chosen:
        need = float(row.effort_hours)
        while need > 1e-9 and day_idx < days_left:
            free = hours_per_day - days[day_idx]["hours_used"]
            if free <= 1e-9:
                day_idx += 1
                continue
            take = min(need, free)
            days[day_idx]["blocks"].append({
                "topic_id": int(row.topic_id),
                "topic": row.name,
                "syllabus_unit": row.syllabus_unit,
                "hours": round(take, 2),
                "needs_notes": not bool(row.has_notes),
                "priority": round(float(row.priority), 3),
            })
            days[day_idx]["hours_used"] = round(days[day_idx]["hours_used"] + take, 2)
            need -= take

    planned_ids = {int(r.topic_id) for r in chosen}
    total_expected = stats["expected_marks"].sum()
    planned_expected = stats[stats["topic_id"].isin(planned_ids)]["expected_marks"].sum()
    return {
        "inputs": {"days_left": days_left, "hours_per_day": hours_per_day, "total_hours": budget},
        "days": days,
        "summary": {
            "topics_planned": len(chosen),
            "hours_planned": round(budget - remaining, 2),
            "hours_unused": round(remaining, 2),
            "expected_marks_covered_pct": round(100 * planned_expected / total_expected, 1) if total_expected else 0.0,
            "topics_needing_notes": [r.name for r in chosen if not r.has_notes],
            "topics_not_scheduled": [r.name for r in candidates.itertuples() if int(r.topic_id) not in planned_ids],
        },
    }


def plan_from_tables(topics, questions, notes, days_left, hours_per_day,
                     note_topics=None, params: Params = DEFAULT_PARAMS, ref_year: int | None = None) -> dict:
    """Convenience wrapper: raw tables in, plan out. This is what the API endpoint will call."""
    validate_inputs(topics, questions, notes, note_topics)
    stats = compute_topic_stats(topics, questions, notes, note_topics, params, ref_year)
    return build_study_plan(stats, days_left, hours_per_day)
