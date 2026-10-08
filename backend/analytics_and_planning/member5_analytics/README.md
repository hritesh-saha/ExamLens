# examlens_analytics (Member 5)

Week 1 deliverable: formulas, dummy data, coverage gaps, planner v1, tests.

```bash
pip install -r requirements.txt
# from the folder that CONTAINS examlens_analytics/
python -m pytest examlens_analytics -q          # 26 tests
python -m examlens_analytics.demo               # prints summary + writes sample_outputs/
```

## Use it
```python
from examlens_analytics import coverage_report, plan_from_tables
from examlens_analytics.dummy_data import make_dummy_data

topics, questions, notes, note_topics = make_dummy_data()   # later: DataFrames from SQLite
coverage_report(topics, questions, notes, note_topics)      # -> dict for the Coverage panel
plan_from_tables(topics, questions, notes, days_left=7, hours_per_day=3, note_topics=note_topics)
build_lecture_timeline(notes, note_topics, topics)           # -> dict for the Timeline panel
add_answer_length_hints(questions)                            # -> questions table + word/time columns
generate_practice_set(topics, questions, seed=42)             # -> dict for the Practice Set panel
compare_due_score_contribution(topics, questions, top_k=5)    # -> is the due-score heuristic worth it?
```

`note_topics` (note_id, topic_id) is the link table Member 4 confirmed. See `FORMULAS.md`
section 4 for a schema conflict with Member 6 that still needs resolving.

## Files
- `FORMULAS.md`: every formula, why it exists, limitations, answers from teammates, open conflict
- `topic_stats.py`: per-topic features (the core)
- `coverage.py`, `planner.py`: the two Week 1 features
- `dummy_data.py`: fake data following the shared contract, with planted gaps and null year/marks
- `sql_loader.py`: reference SQL queries for Member 6's FastAPI layer, against the confirmed schema
- `answer_length.py`: marks -> suggested word count / time (for practice set + flashcards)
- `lecture_timeline.py`: chronological lecture list with all tagged topics
- `practice_set.py`: mock paper from real past questions on likely topics
- `backtest.py`: leave-one-year-out validation of the due-score heuristic
- `sample_outputs/`: example JSON for Member 6's frontend
- `tests/`: hand-verified tests (63)

## Status
All planned features are built and tested. Nothing left to build -- only
re-validating against real data once it lands (see FORMULAS.md section 9).
