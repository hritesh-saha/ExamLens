"""
test_evaluator.py
=================
Tests for evaluator benchmarking suite.
"""

from app.exam_parser.evaluator import run_evaluation, get_default_benchmarks


def test_evaluator_runs_and_scores_high():
    benchmarks = get_default_benchmarks()
    assert len(benchmarks) >= 3

    results = run_evaluation(benchmarks)
    assert len(results) == len(benchmarks)

    for r in results:
        assert r.accuracy_score >= 90.0
        assert r.year_matched is True
        assert r.exam_type_matched is True
        assert r.extracted_questions == r.expected_questions
