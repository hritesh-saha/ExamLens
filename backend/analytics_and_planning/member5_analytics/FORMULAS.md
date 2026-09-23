# Member 5: Formulas and Design Notes (Week 1)

Every number the planner shows comes from these definitions. All tunable values are in `config.py`.
Notation: for topic **t**, exam years **y** ∈ {all years in the past-paper data}, `n_years` = number of years.
The **upcoming exam year** `R` = latest paper year + 1.

## 1. Per-topic statistics (`topic_stats.py`)

| Quantity | Definition | Meaning |
|---|---|---|
| `years_asked` | number of years with ≥1 question on t | how often it appears |
| `year_share` | years_asked / n_years | "frequently asked" if ≥ 0.4 |
| `expected_marks` | Σ_y w_y · marks(t,y) / Σ_y w_y | likely marks in the next paper |
| `w_y` | 0.5 ^ ((R−1−y) / half_life), half_life = 5 years | recent papers count more |
| `usual_gap` | n_years / years_asked | average years between appearances |
| `years_since_last` | R − last year t was asked | how long since it appeared |
| `due_score` | min(years_since_last / usual_gap, 2) / 2, range 0 to 1 | 1 means it is overdue |
| `effort_hours` | 2.0 h (×1.25 if no notes exist) | time to prepare the topic |
| `marks_per_hour` | expected_marks / effort_hours | return on study time |
| **`priority`** | marks_per_hour × (1 + 0.3 × due_score) | final ranking score |

**Why marks per hour:** the goal is to maximise exam marks for limited time, so rank by return on effort, not raw marks.

**Why the no-notes penalty:** a topic without notes needs extra time to find or make material.

**About the due score (defend this carefully):** it assumes a topic that is asked often but has been missing for a while is more likely to return. This is a *heuristic*, not a proven law. Exam setters do not necessarily follow it. That is why the weight is small (max +30% boost) and why the Week 3 back-test matters: hide the last paper, run the model on the earlier ones, and check whether topics that scored high actually appeared. If `due_weight = 0` performs equally well, say so honestly in the report.

**Repeats:** `max_repeat_count` is the size of the largest repeat group in the topic (the "asked 4 times" figure). It is shown, not scored, in v1.

## 2. Coverage gaps (`coverage.py`)

1. **Never asked:** syllabus topics with 0 questions in all papers.
2. **Out of syllabus:** questions whose `topic_id` is null or not in the Topic table.
3. **Frequent without notes:** `year_share ≥ 0.4` and no note tagged with that topic. Sorted by expected marks.
4. **Notes coverage %:** (expected marks of topics that have notes) / (expected marks of all topics). It measures how much of the *likely exam* your notes cover, not just how many topics.
5. **Heatmap data:** marks per topic per year.

## 3. Study planner (`planner.py`)

Input: `days_left`, `hours_per_day`. Budget = days × hours.

1. Sort topics with priority > 0 by priority, highest first.
2. Greedy pick: add a topic if its `effort_hours` still fits in the remaining budget, otherwise skip it and try the next.
3. Lay picked topics onto days in priority order; a topic may continue on the next day.
4. Output flags `needs_notes` per block, and a summary (expected marks covered %, unused hours, topics not scheduled).

**Known limitations (mention in the report):**
- Greedy by ratio is a standard approximation of the knapsack problem, not guaranteed optimal.
- The last few hours may go unused if no remaining topic fits.
- Effort is a flat 2 h per topic (no per-topic difficulty data). It can be overridden by adding an `effort_hours` column to the Topic table.
- Topics are not grouped by syllabus unit within a day (possible Week 2 improvement).

## 4. Confirmed with teammates (Week 1 answers)

| With | Answer | What changed in the code |
|---|---|---|
| Member 3 | `year` and `marks` are both nullable. `marks` can be null for alternative/optional questions sharing one mark value, or missed parsing. `year` is set once per document and should be present almost always. `topic_id` is an int PK, starts null, filled in by topic classification. | Questions with null `year` are excluded from all year-based stats (can't be placed on the topic×year grid). Questions with null `marks` are treated as 0 in sums (undercounts them). Both are now counted and surfaced in a `data_quality` block in every report, so missing data is visible, not silently absorbed. |
| Member 4 | "No confident topic" = `topic_id = null` (no placeholder string). Notes link to topics via a separate **`note_topics` link table** (`note_id`, `topic_id`), not a JSON/CSV column on Note. `repeat_group_id` is null unless 2+ similar questions exist. | `compute_topic_stats`, `coverage_report` and `plan_from_tables` now take an optional `note_topics` DataFrame and join through it. A legacy `topic_ids` column on `notes` is still supported as a fallback if that's ever what actually ships. |
| Member 6 | Schema confirmed (see `sql_loader.py`). FastAPI will query with SQLAlchemy/raw SQL, `pd.read_sql` into a DataFrame, and pass it straight to these functions. | `sql_loader.py` has the exact `SELECT` per table against this schema, so Member 6 can copy them directly into the FastAPI endpoints. |

### ⚠️ Open conflict to resolve before Week 2 build starts

Member 6's schema draft still lists `topic_ids` as a column on the **Note** table. Member 4 said notes will link to topics through a separate **`note_topics`** table instead. These can't both be true — pick one:

- **Recommended:** drop `topic_ids` from `Note`, use `note_topics(note_id, topic_id)`. Cleaner for joins/aggregation, and it's what my code is built against by default.
- If Member 6 prefers to keep the column instead, tell me and I'll switch the default (the fallback path already works, just needs to become primary).

Get Member 3, 4 and 6 to align on this on Day 1 of Week 2 so the schema is only built once.

## 5. Open items for Week 2

- Answer-length hints (marks -> suggested word count)
- Lecture timeline (chronological notes with subject/topic tags)
- Practice set generator (sampling that matches the historical marks distribution)
- Back-test: hide the latest paper, run the model on earlier years, check whether high-priority topics actually appeared (this is how you defend the due-score heuristic)
