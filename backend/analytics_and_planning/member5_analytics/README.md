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
```

`note_topics` (note_id, topic_id) is the link table Member 4 confirmed. See `FORMULAS.md`
section 4 for a schema conflict with Member 6 that still needs resolving.

## Files
- `FORMULAS.md`: every formula, why it exists, limitations, answers from teammates, open conflict
- `topic_stats.py`: per-topic features (the core)
- `coverage.py`, `planner.py`: the two Week 1 features
- `dummy_data.py`: fake data following the shared contract, with planted gaps and null year/marks
- `sql_loader.py`: reference SQL queries for Member 6's FastAPI layer, against the confirmed schema
- `sample_outputs/`: example JSON for Member 6's frontend
- `tests/`: hand-verified tests (21)

## Coming in Weeks 2-3
Answer-length hints, lecture timeline, FastAPI endpoints, practice set, back-test.
