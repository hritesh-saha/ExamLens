"""Realistic fake Topic / Question / Note / note_topics tables following the
shared contract confirmed by Members 3, 4 and 6, so Member 5 can build
everything before real data lands.

Built-in gaps and edge cases (so every feature has something to show):
  * 'B-Trees' and 'Tries' (and maybe 1-2 unlucky topics) are never asked -> never-asked gap
  * 2 questions have no topic (topic_id null)        -> out-of-syllabus gap
  * BST, Shortest Path, Hashing, ... are frequent but have no notes -> frequent-without-notes gap
  * A few questions have null year or null marks     -> data-quality edge case (Member 3's note)
  * notes link to topics via a separate note_topics table, not a topic_ids column (Member 4's note)
"""
import numpy as np
import pandas as pd

# (name, syllabus unit, chance of being picked for a paper)
_TOPICS = [
    ("Arrays and Complexity Analysis", "Unit 1: Fundamentals", 0.30),
    ("Recursion", "Unit 1: Fundamentals", 0.40),
    ("Sorting Algorithms", "Unit 1: Fundamentals", 0.90),
    ("Searching Algorithms", "Unit 1: Fundamentals", 0.30),
    ("Linked Lists", "Unit 2: Linear Structures", 0.80),
    ("Stacks", "Unit 2: Linear Structures", 0.60),
    ("Queues", "Unit 2: Linear Structures", 0.50),
    ("Hashing", "Unit 2: Linear Structures", 0.50),
    ("Binary Trees and Traversals", "Unit 3: Trees", 0.80),
    ("Binary Search Trees", "Unit 3: Trees", 0.70),
    ("AVL Trees", "Unit 3: Trees", 0.45),
    ("Heaps", "Unit 3: Trees", 0.40),
    ("Graph Representation", "Unit 4: Graphs", 0.30),
    ("BFS and DFS", "Unit 4: Graphs", 0.70),
    ("Shortest Path", "Unit 4: Graphs", 0.60),
    ("Minimum Spanning Tree", "Unit 4: Graphs", 0.40),
    ("Dynamic Programming", "Unit 5: Advanced", 0.35),
    ("Greedy Algorithms", "Unit 5: Advanced", 0.15),
    ("B-Trees", "Unit 5: Advanced", 0.0),
    ("Tries", "Unit 5: Advanced", 0.0),
]

# two question wordings per marks class -> same wording in a later year = a repeat
_STEMS = {
    2: ["Define {t}.", "State two applications of {t}."],
    5: ["Explain {t} with a suitable example.", "Compare two approaches to {t}."],
    10: ["Discuss {t} in detail with algorithms and diagrams.",
         "Write an algorithm for {t} and analyse its time complexity."],
}
_SECTION = {2: "A", 5: "B", 10: "C"}
_PAPER_PATTERN = [10, 10, 5, 5, 5, 5, 2, 2, 2, 2, 2]   # marks per question in one paper (total 50)

# fake lectures: (topics covered, number of pages/photos merged into that lecture's document).
# Deliberately mixes single- and multi-topic lectures, since a real board lecture
# often covers more than one syllabus topic (tests that the timeline shows ALL of them).
_LECTURES = [
    (["Arrays and Complexity Analysis", "Recursion"], 2),
    (["Sorting Algorithms"], 1),
    (["Linked Lists", "Stacks"], 2),
    (["Queues"], 1),
    (["Binary Trees and Traversals"], 1),
    (["Graph Representation", "BFS and DFS"], 2),
]


def make_dummy_data(seed: int = 42, years=range(2018, 2026)):
    """Returns (topics, questions, notes, note_topics) as DataFrames."""
    rng = np.random.default_rng(seed)

    topics = pd.DataFrame(
        [{"id": i + 1, "name": n, "syllabus_unit": u} for i, (n, u, _) in enumerate(_TOPICS)])
    probs = np.array([p for _, _, p in _TOPICS])
    probs = probs / probs.sum()
    name_to_id = dict(zip(topics["name"], topics["id"]))

    rows = []
    for year in years:
        # topics drawn without replacement; likelier topics come first -> get the 10-mark slots
        picked = rng.choice(len(_TOPICS), size=len(_PAPER_PATTERN), replace=False, p=probs)
        for pos, (tidx, marks) in enumerate(zip(picked, _PAPER_PATTERN)):
            stem_idx = int(rng.choice(2, p=[0.6, 0.4]))
            rows.append({
                "document_id": f"paper_{year}", "page": 1 if pos < 6 else 2,
                "year": year, "section": _SECTION[marks], "marks": marks,
                "text": _STEMS[marks][stem_idx].format(t=_TOPICS[tidx][0]),
                "topic_id": int(tidx) + 1, "_group_key": f"{tidx}-{marks}-{stem_idx}",
            })
    # two questions outside the syllabus
    rows.append({"document_id": "paper_2019", "page": 2, "year": 2019, "section": "B", "marks": 5,
                 "text": "Explain the CAP theorem.", "topic_id": None, "_group_key": None})
    rows.append({"document_id": "paper_2023", "page": 2, "year": 2023, "section": "B", "marks": 5,
                 "text": "Describe how MapReduce works.", "topic_id": None, "_group_key": None})

    q = pd.DataFrame(rows)
    q.insert(0, "id", range(1, len(q) + 1))
    # repeat_group_id only for wordings that occurred 2+ times; singletons stay null (Member 4's convention)
    sizes = q["_group_key"].map(q["_group_key"].value_counts())
    codes = {k: i + 1 for i, k in enumerate(sorted(q["_group_key"].dropna().unique()))}
    q["repeat_group_id"] = [codes[k] if (k is not None and s >= 2) else None
                            for k, s in zip(q["_group_key"], sizes)]
    q["repeat_group_id"] = q["repeat_group_id"].astype("Int64")
    q["topic_id"] = q["topic_id"].astype("Int64")
    questions = q.drop(columns="_group_key")

    # Data-quality edge case (per Member 3): a few rows with null marks (shared
    # mark value across alternative sub-questions) or null year (rare, bad upload metadata).
    marks_null_idx = rng.choice(questions.index, size=2, replace=False)
    questions.loc[marks_null_idx, "marks"] = None
    remaining = questions.index.difference(marks_null_idx)
    year_null_idx = rng.choice(remaining, size=1, replace=False)
    questions.loc[year_null_idx, "year"] = None
    questions["marks"] = questions["marks"].astype("Int64")
    questions["year"] = questions["year"].astype("Int64")

    # Lectures: pages of the same lecture share one document_id and one
    # lecture_date (per Member 1). Topics are tagged per page (per Member 4's
    # note_topics link table); a multi-topic lecture spreads its topics
    # across its pages round-robin.
    note_rows, note_topic_rows = [], []
    note_id = 1
    for i, (topic_names, n_pages) in enumerate(_LECTURES):
        doc_id = f"lecture_{i + 1:02d}"
        date = (pd.Timestamp("2026-08-03") + pd.Timedelta(days=3 * i)).date().isoformat()
        page_note_ids = []
        for p in range(1, n_pages + 1):
            note_rows.append({
                "id": note_id, "document_id": doc_id, "page": p, "lecture_date": date,
                "text": f"Notes on {', '.join(topic_names)} (page {p}).", "latex": None,
                "confidence": round(float(rng.uniform(0.75, 0.97)), 2),
            })
            page_note_ids.append(note_id)
            note_id += 1
        for j, name in enumerate(topic_names):
            note_topic_rows.append({"note_id": page_note_ids[j % len(page_note_ids)],
                                    "topic_id": name_to_id[name]})

    notes = pd.DataFrame(note_rows)
    note_topics = pd.DataFrame(note_topic_rows)

    return topics, questions, notes, note_topics


if __name__ == "__main__":
    t, q, n, nt = make_dummy_data()
    print(t.head(), "\n", q.head(), "\n", n.head(), "\n", nt.head())
