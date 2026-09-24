"""All tunable numbers for Member 5's module live here, so they can be
changed (and explained in the report) in one place."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Params:
    # --- effort model ---
    base_effort_hours: float = 2.0      # hours to prepare one topic (if Topic table has no effort column)
    no_notes_penalty: float = 1.25      # x effort if the topic has no lecture notes yet

    # --- expected marks model ---
    recency_half_life_years: float | None = 5.0   # a paper this many years older counts half. None = equal weights

    # --- "due" score (frequent topic, not asked recently) ---
    due_cap: float = 2.0                # ratio (years since last / usual gap) is capped here
    due_weight: float = 0.3             # priority boost = 1 + due_weight * due_score

    # --- coverage ---
    frequent_year_share: float = 0.4    # "frequently asked" = appeared in >= 40% of exam years

    # --- answer-length hints ---
    # (marks -> suggested words), anchors from the project brief; other mark
    # values are interpolated/extrapolated linearly between these.
    answer_length_anchors: tuple[tuple[int, int], ...] = ((2, 50), (5, 150), (10, 300))
    writing_words_per_minute: float = 12.0   # typical handwritten exam speed, for the time estimate


DEFAULT_PARAMS = Params()
