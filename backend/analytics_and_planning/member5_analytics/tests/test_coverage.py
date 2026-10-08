from examlens_analytics import coverage_report
from examlens_analytics.dummy_data import make_dummy_data
from .conftest import P


def test_gaps_on_tiny_data(tiny):
    topics, questions, notes, note_topics = tiny
    r = coverage_report(topics, questions, notes, note_topics, params=P)
    assert [t["name"] for t in r["never_asked_topics"]] == ["T3"]
    assert len(r["out_of_syllabus_questions"]) == 2            # null topic + unknown topic id 99
    # frequent (>=40% of years) and no notes: only T2 (2 of 4 years). T4 is 1 of 4 -> not frequent.
    assert [t["name"] for t in r["frequent_without_notes"]] == ["T2"]


def test_summary_numbers(tiny):
    topics, questions, notes, note_topics = tiny
    s = coverage_report(topics, questions, notes, note_topics, params=P)["summary"]
    assert s["n_topics"] == 4 and s["n_topics_asked"] == 3 and s["n_topics_with_notes"] == 1
    # expected marks: T1 5 + T2 5 + T4 0.5 = 10.5 ; notes cover T1 -> 5/10.5
    assert s["expected_marks_covered_by_notes_pct"] == round(100 * 5 / 10.5, 1)


def test_data_quality_surfaced_in_report(tiny):
    topics, questions, notes, note_topics = tiny
    dq = coverage_report(topics, questions, notes, note_topics, params=P)["data_quality"]
    assert dq["missing_year"] == 1 and dq["missing_marks"] == 1


def test_heatmap_shape(tiny):
    topics, questions, notes, note_topics = tiny
    h = coverage_report(topics, questions, notes, note_topics, params=P)["heatmap"]
    assert h["years"] == [2021, 2022, 2023, 2024]
    t2 = next(t for t in h["topics"] if t["name"] == "T2")
    assert t2["marks_by_year"] == [10, 10, 0, 0]


def test_report_is_json_serialisable():
    import json
    topics, questions, notes, note_topics = make_dummy_data()
    json.dumps(coverage_report(topics, questions, notes, note_topics))     # must not raise


def test_dummy_data_contains_the_planted_gaps():
    topics, questions, notes, note_topics = make_dummy_data()
    r = coverage_report(topics, questions, notes, note_topics)
    never = {t["name"] for t in r["never_asked_topics"]}
    assert {"B-Trees", "Tries"} <= never
    assert r["summary"]["n_out_of_syllabus"] == 2
    assert len(r["frequent_without_notes"]) > 0
    assert r["data_quality"]["missing_marks"] == 2 and r["data_quality"]["missing_year"] == 1
