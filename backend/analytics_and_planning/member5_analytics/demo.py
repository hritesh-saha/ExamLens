"""Run:  python -m examlens_analytics.demo      (from the folder that contains examlens_analytics/)
Prints a readable summary and writes sample JSON outputs for Member 6 (frontend shape)."""
import json
from pathlib import Path

from . import compute_topic_stats, coverage_report, plan_from_tables, add_answer_length_hints, build_lecture_timeline
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


if __name__ == "__main__":
    main()
