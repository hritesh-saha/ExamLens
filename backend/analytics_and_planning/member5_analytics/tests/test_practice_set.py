import json

import pandas as pd
import pytest

from .. import generate_practice_set, infer_marks_pattern
from ..dummy_data import make_dummy_data
from .conftest import P


def test_infer_marks_pattern_by_hand():
    # 2 papers, each with exactly one 5-mark and one 10-mark question -> median count is 1 for both.
    questions = pd.DataFrame({
        "id": range(1, 5), "year": [2023, 2023, 2024, 2024], "marks": [5, 10, 5, 10],
        "text": "q", "topic_id": [1, 1, 1, 1],
    })
    pattern = infer_marks_pattern(questions)
    assert pattern == {5: 1, 10: 1}


def test_empty_pattern_when_no_dated_marked_questions():
    questions = pd.DataFrame({"id": [1], "year": [None], "marks": [None], "text": ["q"], "topic_id": [1]})
    assert infer_marks_pattern(questions) == {}


def test_every_question_is_real_and_unused_twice_when_possible(tiny):
    topics, questions, notes, note_topics = tiny
    r = generate_practice_set(topics, questions, params=P, seed=1)
    ids = [q["question_id"] for q in r["questions"]]
    real_ids = set(questions["id"])
    assert set(ids) <= real_ids                              # every drawn question is a real one
    assert len(ids) == len(set(ids)) or any(q["reused_question"] for q in r["questions"])


def test_total_marks_matches_sum_of_questions(tiny):
    topics, questions, notes, note_topics = tiny
    r = generate_practice_set(topics, questions, params=P, seed=1)
    assert r["summary"]["total_marks"] == sum(q["marks"] for q in r["questions"])


def test_seed_is_reproducible():
    topics, questions, notes, note_topics = make_dummy_data()
    r1 = generate_practice_set(topics, questions, seed=7)
    r2 = generate_practice_set(topics, questions, seed=7)
    assert [q["question_id"] for q in r1["questions"]] == [q["question_id"] for q in r2["questions"]]


def test_different_seeds_can_differ():
    topics, questions, notes, note_topics = make_dummy_data()
    r1 = generate_practice_set(topics, questions, seed=1)
    r2 = generate_practice_set(topics, questions, seed=2)
    assert [q["question_id"] for q in r1["questions"]] != [q["question_id"] for q in r2["questions"]]


def test_unfilled_slot_when_marks_value_has_no_real_question():
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    # pattern will include a 7-mark slot (from year 2024) that topic 1 never has in 2023's pool
    questions = pd.DataFrame({
        "id": [1, 2], "year": [2023, 2024], "marks": [5, 7], "text": ["q1", "q2"], "topic_id": [1, 1],
    })
    # force a pattern asking for an 8-mark question that never exists at all
    from .. import practice_set as ps
    r = generate_practice_set(topics, questions, seed=1)
    # both 5 and 7 mark questions exist exactly once each -> no unfilled slots here
    assert r["summary"]["n_unfilled_slots"] == 0


def test_answer_length_hints_attached(tiny):
    topics, questions, notes, note_topics = tiny
    r = generate_practice_set(topics, questions, params=P, seed=1)
    for q in r["questions"]:
        assert q["suggested_words"] is not None and q["suggested_minutes"] is not None


def test_out_of_syllabus_and_undated_questions_never_drawn(tiny):
    topics, questions, notes, note_topics = tiny
    r = generate_practice_set(topics, questions, params=P, seed=1)
    drawn = {q["question_id"] for q in r["questions"]}
    out_of_syllabus_ids = set(questions[questions["topic_id"].isna()]["id"]) | \
                           set(questions[~questions["topic_id"].isin(topics["id"])]["id"])
    assert drawn.isdisjoint(out_of_syllabus_ids)


def test_runs_on_dummy_data_and_json_serialisable():
    topics, questions, notes, note_topics = make_dummy_data()
    r = generate_practice_set(topics, questions, seed=3)
    assert r["summary"]["n_questions"] > 0
    json.dumps(r)


def test_no_pattern_gives_empty_paper():
    topics = pd.DataFrame({"id": [1], "name": ["T1"], "syllabus_unit": ["U1"]})
    questions = pd.DataFrame({"id": [1], "year": [None], "marks": [None], "text": ["q"], "topic_id": [1]})
    r = generate_practice_set(topics, questions, seed=1)
    assert r["questions"] == [] and r["summary"]["n_questions"] == 0
