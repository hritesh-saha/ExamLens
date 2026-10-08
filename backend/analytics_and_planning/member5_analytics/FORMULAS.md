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

## 4. Answer-length hints (`answer_length.py`)

Maps a question's `marks` to a suggested word count and writing time, shown on the practice set and flashcards.

**Why not a flat "words per mark" ratio:** real mark schemes aren't perfectly linear — a 2-mark "define X" needs relatively more words per mark than a 10-mark "discuss X in detail," because there's a fixed minimum to write a coherent sentence at all. So instead of `words = marks × constant`, the code interpolates between three anchor points from the project brief (2 marks → 50 words, 5 → 150, 10 → 300) and extrapolates beyond them using the slope of the nearest segment. Time estimate: `words / 12` (12 words/minute is a typical handwritten exam speed — tune this in `config.py` if it doesn't match your syllabus's expectations).

| marks | suggested words | suggested minutes |
|---|---|---|
| 1 | 15 | 1 |
| 2 | 50 | 4 |
| 5 | 150 | 12 |
| 10 | 300 | 25 |
| 15 | 450 | 38 |

A question with null `marks` gets `None` for both fields rather than a guessed value.

## 5. Lecture timeline (`lecture_timeline.py`)

One entry per lecture, sorted chronologically, showing every topic it covers.

**Grouping (confirmed with Member 1):** a lecture is one `document_id`. All pages/photos merged into that document share one `lecture_date`, so lectures group by `document_id`, not by individual page timestamp.

**All topics shown, not just one (confirmed with Member 4):** if a lecture is tagged with 3 topics and only 1 is shown, the other 2 would look like they have no notes yet -- a false coverage gap. So every topic tagged to any page of the lecture is listed.

**No subject field (confirmed with Member 6):** subject/unit context comes from `NoteTopic -> Topic.syllabus_unit`, joined at read time. A lecture's `syllabus_units` list is the deduplicated set of units its topics belong to.

**Sorting (confirmed with Member 6):** `lecture_date` is a sortable ISO 8601 string (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`), so chronological order is a plain string sort -- no date parsing needed.

**Edge cases handled:**
- A lecture with no `lecture_date` on any page goes into a separate `unscheduled` list rather than breaking the sort order of `timeline`.
- If a lecture's pages disagree on `lecture_date` (shouldn't happen per Member 1's design, but data can be messy), the earliest date is used and the conflict is reported in `data_quality.date_conflicts` so it's visible, not silently picked.
- A lecture with no topics tagged yet (classification hasn't run) shows an empty topic list rather than erroring.

## 6. Practice set generator (`practice_set.py`)

Builds a mock paper from real past questions, weighted toward likely topics, with a marks distribution matching history.

**Marks distribution:** for each marks value (2, 5, 10, ...), count how many questions of that value a typical past paper has (median across all papers), round to the nearest whole question. A paper that's historically had two 10-mark, four 5-mark and five 2-mark questions gets a practice set shaped the same way.

**Topic selection:** weighted by the same `priority` score as the study planner (expected marks x due-score boost) -- with one deliberate difference: **the practice set is built with an empty notes table**, so note-availability never influences which topics get tested. The planner *should* favour topics without notes (that's its job: tell the student what to study); a mock exam should not -- whether the student has notes for a topic has nothing to do with whether it's likely to appear on the real exam.

**Only real questions, never generated text:** every question in the output is pulled verbatim from the `Question` table, per the project brief. If a marks value has no real question left for any topic (exhausted or genuinely absent), that slot is either filled by reusing an already-used question (flagged `reused_question: true`) or, if there are no questions at all for that marks value, left out and reported in `unfilled_slots` rather than invented.

**Reproducibility:** pass `seed=<int>` for a deterministic paper (useful for tests or "regenerate the same paper"); omit it for a fresh random draw each call.

Each question in the output also carries its `answer_length_hint` (section 4), so the generated paper is ready to hand to the student with suggested word counts attached, as the demo flow in the project brief describes.

## 7. Back-test (`backtest.py`)

This is the evidence for or against the "due score" heuristic from section 1 -- the part of your report/viva that says "we didn't just assume this heuristic works, we checked."

**Method: leave-one-year-out.** For each exam year Y with enough prior years of data, compute topic priority using *only* data from before Y (exactly as if Y hadn't happened yet), then check it against what was *actually* asked in Y. Two metrics per year:
- **`top_k_marks_captured_pct`** -- of all marks actually awarded in year Y, what share came from the topics the model would have told you (before Y) to prioritise? This is the number that answers "would following the planner's advice have paid off."
- **`priority_vs_actual_marks_spearman`** -- rank correlation between predicted priority and actual marks earned, across *all* topics, not just the top ones. Catches whether the whole ranking is sensible, not just the top slice.

**The actual test:** `compare_due_score_contribution` runs this twice -- once with the configured `due_weight`, once with `due_weight=0` (plain marks-per-hour ranking, no "overdue" boost) -- and reports the difference plainly:

| On dummy data | with due-score | without due-score |
|---|---|---|
| top-5 captures | 33.6% of marks | 33.6% of marks |

**Honest result on dummy data: no measurable difference.** This isn't a bug -- the dummy data generator draws topics independently each year with fixed probabilities, so there's no genuine "topic X is overdue" signal built into it for the heuristic to find. **This is expected and says nothing about whether the heuristic will help on real exam data**, where topics may genuinely cycle. Re-run `compare_due_score_contribution` once real past papers are loaded -- that result is the one to report. If it still shows no improvement there, FORMULAS.md's original guidance holds: report that honestly rather than keep the complexity. If it does help, you now have the number to defend it with.

## 8. Confirmed with teammates (Week 1 answers)

| With | Answer | What changed in the code |
|---|---|---|
| Member 3 | `year` and `marks` are both nullable. `marks` can be null for alternative/optional questions sharing one mark value, or missed parsing. `year` is set once per document and should be present almost always. `topic_id` is an int PK, starts null, filled in by topic classification. | Questions with null `year` are excluded from all year-based stats (can't be placed on the topic×year grid). Questions with null `marks` are treated as 0 in sums (undercounts them). Both are now counted and surfaced in a `data_quality` block in every report, so missing data is visible, not silently absorbed. |
| Member 4 | "No confident topic" = `topic_id = null` (no placeholder string). Notes link to topics via a separate **`note_topics` link table** (`note_id`, `topic_id`), not a JSON/CSV column on Note. `repeat_group_id` is null unless 2+ similar questions exist. | `compute_topic_stats`, `coverage_report` and `plan_from_tables` now take an optional `note_topics` DataFrame and join through it. A legacy `topic_ids` column on `notes` is still supported as a fallback if that's ever what actually ships. |
| Member 6 | Schema confirmed (see `sql_loader.py`). FastAPI will query with SQLAlchemy/raw SQL, `pd.read_sql` into a DataFrame, and pass it straight to these functions. | `sql_loader.py` has the exact `SELECT` per table against this schema, so Member 6 can copy them directly into the FastAPI endpoints. |

### Schema conflict — resolved

Earlier the written schema draft listed `topic_ids` as a column on `Note`, which conflicted with Member 4's plan for a link table. Checked against Member 6's actual repo (`app/models.py`): `Note` has no `topic_ids` column, and there's a proper `NoteTopic(note_id, topic_id)` link table. No action needed — this matches what the code below is built against.

## 9. Open items

All planned Member 5 features are built: per-topic stats, coverage gaps, study planner,
answer-length hints, lecture timeline, practice set generator, and the back-test.

What's left is data-dependent, not code-dependent:
- Re-run `compare_due_score_contribution` once real past-paper data is loaded (section 7) --
  the dummy-data result above is a placeholder, not the real answer.
- Re-check `sample_outputs/` against the real schema once Members 1/2/3/4's pipelines are live.
