"""Run:  python -m examlens_analytics.demo      (from the folder that contains examlens_analytics/)
Prints a readable summary and writes sample JSON outputs for Member 6 (frontend shape)."""
import json
from pathlib import Path

from . import (compute_topic_stats, coverage_report, plan_from_tables, add_answer_length_hints,
               build_lecture_timeline, generate_practice_set, compare_due_score_contribution)
from .dummy_data import make_dummy_data

OUT = Path(__file__).parent / "sample_outputs"


def main():
    topics, questions, notes, note_topics = make_dummy_data()
    OUT.mkdir(exist_ok=True)

    report = coverage_report(topics, questions, notes, note_topics)
    plan = plan_from_tables(topics, questions, notes, days_left=7, hours_per_day=3, note_topics=note_topics)
    stats = compute_topic_stats(topics, questions, notes, note_topics)
    with_hints = add_answer_length_hints(questions)
    with_hints[["id", "marks", "suggested_words", "suggested_minutes"]].to_csv(
        OUT / "answer_length_hints.csv", index=False)

    timeline = build_lecture_timeline(notes, note_topics, topics)
    (OUT / "lecture_timeline.json").write_text(json.dumps(timeline, indent=2))

    practice = generate_practice_set(topics, questions, seed=42)
    (OUT / "practice_set.json").write_text(json.dumps(practice, indent=2))

    backtest = compare_due_score_contribution(topics, questions, top_k=5)
    (OUT / "backtest.json").write_text(json.dumps(backtest, indent=2))

    (OUT / "coverage_report.json").write_text(json.dumps(report, indent=2))
    (OUT / "study_plan.json").write_text(json.dumps(plan, indent=2))
    stats.round(3).to_csv(OUT / "topic_stats.csv", index=False)

    print("DATA QUALITY:", json.dumps(report["data_quality"], indent=2))
    print("\nCOVERAGE SUMMARY:", json.dumps(report["summary"], indent=2))
    print("\nNever asked:", [t["name"] for t in report["never_asked_topics"]])
    print("Frequent but no notes:", [t["name"] for t in report["frequent_without_notes"]])
    print(f"\nSTUDY PLAN (7 days x 3h) - covers {plan['summary']['expected_marks_covered_pct']}% of expected marks")
    for d in plan["days"]:
        blocks = ", ".join(f"{b['topic']} ({b['hours']}h{' *needs notes' if b['needs_notes'] else ''})" for b in d["blocks"])
        print(f"  Day {d['day']}: {blocks}")
    print(f"\nSample JSON written to {OUT}")
    print("Answer-length hints sample:")
    print(with_hints[["marks", "suggested_words", "suggested_minutes"]].dropna().head(5).to_string(index=False))
    print("\nLECTURE TIMELINE:")
    for e in timeline["timeline"]:
        print(f"  {e['lecture_date']}  {e['document_id']} ({e['n_pages']}p) -> "
              f"{[t['name'] for t in e['topics']]}")
    print(f"\nPRACTICE SET: {practice['summary']['n_questions']} questions, "
          f"{practice['summary']['total_marks']} marks (typical paper: {practice['summary']['typical_paper_marks']})")
    for q in practice["questions"][:5]:
        print(f"  [{q['marks']}m] {q['topic_name']}: {q['text'][:55]}")
    print(f"\nBACK-TEST (due-score heuristic): {backtest['verdict']}")
    print(f"  with due-score:    top-5 captures {backtest['with_due_score']['mean_top_k_marks_captured_pct']}% of marks on average")
    print(f"  without due-score: top-5 captures {backtest['without_due_score']['mean_top_k_marks_captured_pct']}% of marks on average")


if __name__ == "__main__":
    main()
