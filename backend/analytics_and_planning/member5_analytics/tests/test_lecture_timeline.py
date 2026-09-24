import json

import pandas as pd
import pytest

from examlens_analytics import build_lecture_timeline
from examlens_analytics.dummy_data import make_dummy_data


@pytest.fixture
def timeline_data():
    """Two lectures: L1 (2 pages, 2 topics), L2 (1 page, no topics tagged yet).
    A third 'ghost' note has a null lecture_date (not yet given a date)."""
    topics = pd.DataFrame({"id": [1, 2], "name": ["Recursion", "Sorting"],
                           "syllabus_unit": ["Unit 1", "Unit 1"]})
    notes = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "document_id": ["L1", "L1", "L2", "L3"],
        "page": [1, 2, 1, 1],
        "lecture_date": ["2026-08-10", "2026-08-10", "2026-08-05", None],
    })
    note_topics = pd.DataFrame({"note_id": [1, 2], "topic_id": [1, 2]})
    return topics, notes, note_topics


def test_groups_pages_under_one_lecture(timeline_data):
    topics, notes, note_topics = timeline_data
    r = build_lecture_timeline(notes, note_topics, topics)
    l1 = next(e for e in r["timeline"] if e["document_id"] == "L1")
    assert l1["n_pages"] == 2


def test_shows_all_topics_not_just_one(timeline_data):
    """Member 4's requirement: a multi-topic lecture must list every topic,
    not just one -- otherwise the others look like false coverage gaps."""
    topics, notes, note_topics = timeline_data
    r = build_lecture_timeline(notes, note_topics, topics)
    l1 = next(e for e in r["timeline"] if e["document_id"] == "L1")
    assert {t["name"] for t in l1["topics"]} == {"Recursion", "Sorting"}
    assert l1["syllabus_units"] == ["Unit 1"]


def test_chronological_order(timeline_data):
    topics, notes, note_topics = timeline_data
    r = build_lecture_timeline(notes, note_topics, topics)
    dates = [e["lecture_date"] for e in r["timeline"]]
    assert dates == sorted(dates)
    assert [e["document_id"] for e in r["timeline"]] == ["L2", "L1"]   # L2 (Aug 5) before L1 (Aug 10)


def test_lecture_with_no_topics_yet_has_empty_list(timeline_data):
    topics, notes, note_topics = timeline_data
    r = build_lecture_timeline(notes, note_topics, topics)
    l2 = next(e for e in r["timeline"] if e["document_id"] == "L2")
    assert l2["topics"] == [] and l2["syllabus_units"] == []


def test_null_lecture_date_goes_to_unscheduled_not_timeline(timeline_data):
    topics, notes, note_topics = timeline_data
    r = build_lecture_timeline(notes, note_topics, topics)
    assert [e["document_id"] for e in r["unscheduled"]] == ["L3"]
    assert "L3" not in [e["document_id"] for e in r["timeline"]]
    assert r["data_quality"]["n_unscheduled"] == 1


def test_conflicting_dates_within_one_lecture_are_flagged_and_earliest_wins():
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    notes = pd.DataFrame({"id": [1, 2], "document_id": ["L1", "L1"], "page": [1, 2],
                          "lecture_date": ["2026-08-10", "2026-08-05"]})
    r = build_lecture_timeline(notes, None, topics)
    assert r["timeline"][0]["lecture_date"] == "2026-08-05"          # earliest wins
    assert r["data_quality"]["n_date_conflicts"] == 1
    assert r["data_quality"]["date_conflicts"][0]["document_id"] == "L1"


def test_works_with_no_note_topics_link_table_at_all():
    """note_topics=None shouldn't crash -- e.g. before Member 4's classifier has run."""
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    notes = pd.DataFrame({"id": [1], "document_id": ["L1"], "page": [1], "lecture_date": ["2026-08-10"]})
    r = build_lecture_timeline(notes, None, topics)
    assert r["timeline"][0]["topics"] == []


def test_missing_column_gives_clear_error():
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    notes = pd.DataFrame({"id": [1], "lecture_date": ["2026-08-10"]})   # no document_id
    with pytest.raises(ValueError, match="document_id"):
        build_lecture_timeline(notes, None, topics)


def test_runs_on_dummy_data_and_is_json_serialisable():
    topics, questions, notes, note_topics = make_dummy_data()
    r = build_lecture_timeline(notes, note_topics, topics)
    assert len(r["timeline"]) == 6                     # 6 lectures in _LECTURES
    assert r["data_quality"]["n_unscheduled"] == 0
    # the two multi-topic lectures should show both topics, not one
    multi = [e for e in r["timeline"] if len(e["topics"]) > 1]
    assert len(multi) == 3                              # 3 of the 6 lectures cover 2 topics each
    json.dumps(r)


def test_dummy_timeline_is_chronological():
    topics, questions, notes, note_topics = make_dummy_data()
    r = build_lecture_timeline(notes, note_topics, topics)
    dates = [e["lecture_date"] for e in r["timeline"]]
    assert dates == sorted(dates)
