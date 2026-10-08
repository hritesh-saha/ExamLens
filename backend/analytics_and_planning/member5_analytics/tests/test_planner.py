import json

import pytest

from examlens_analytics import build_study_plan, compute_topic_stats, plan_from_tables
from examlens_analytics.dummy_data import make_dummy_data
from .conftest import P


def test_greedy_picks_by_priority_and_skips_what_does_not_fit(tiny):
    topics, questions, notes, note_topics = tiny
    stats = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    plan = build_study_plan(stats, days_left=2, hours_per_day=2.25)      # 4.5h budget
    names = [b["topic"] for d in plan["days"] for b in d["blocks"]]
    assert names[0] == "T1"                                              # highest priority first
    assert set(names) == {"T1", "T2"}                                    # 2h + 2.5h = 4.5h exactly
    assert plan["summary"]["hours_unused"] == 0


def test_topic_can_spill_over_to_next_day(tiny):
    topics, questions, notes, note_topics = tiny
    stats = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    plan = build_study_plan(stats, days_left=3, hours_per_day=2)         # 6h budget
    day_blocks = [[(b["topic"], b["hours"]) for b in d["blocks"]] for d in plan["days"]]
    assert day_blocks == [[("T1", 2.0)], [("T2", 2.0)], [("T2", 0.5)]]   # T4 (2.5h) no longer fits


def test_never_asked_topics_are_not_scheduled(tiny):
    topics, questions, notes, note_topics = tiny
    stats = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    plan = build_study_plan(stats, days_left=30, hours_per_day=8)        # huge budget
    scheduled = {b["topic"] for d in plan["days"] for b in d["blocks"]}
    assert "T3" not in scheduled and scheduled == {"T1", "T2", "T4"}


def test_missing_notes_are_flagged(tiny):
    topics, questions, notes, note_topics = tiny
    stats = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    plan = build_study_plan(stats, days_left=3, hours_per_day=2)
    assert plan["summary"]["topics_needing_notes"] == ["T2"]
    flags = {b["topic"]: b["needs_notes"] for d in plan["days"] for b in d["blocks"]}
    assert flags == {"T1": False, "T2": True}


@pytest.mark.parametrize("days,hours", [(0, 3), (5, 0), (-1, 2)])
def test_bad_inputs_rejected(tiny, days, hours):
    topics, questions, notes, note_topics = tiny
    stats = compute_topic_stats(topics, questions, notes, note_topics, params=P)
    with pytest.raises(ValueError):
        build_study_plan(stats, days, hours)


def test_never_exceeds_budget_and_gains_with_more_time():
    t, q, n, nt = make_dummy_data()
    small = plan_from_tables(t, q, n, 3, 2, note_topics=nt)
    large = plan_from_tables(t, q, n, 10, 4, note_topics=nt)
    for plan in (small, large):
        assert plan["summary"]["hours_planned"] <= plan["inputs"]["total_hours"]
        assert all(d["hours_used"] <= plan["inputs"]["hours_per_day"] + 1e-9 for d in plan["days"])
    assert large["summary"]["expected_marks_covered_pct"] >= small["summary"]["expected_marks_covered_pct"]
    json.dumps(large)                                                    # JSON-safe
