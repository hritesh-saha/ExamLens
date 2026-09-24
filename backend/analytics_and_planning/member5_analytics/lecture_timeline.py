"""Lecture timeline: notes ordered chronologically, each lecture tagged with
every topic covered in it (project brief section 2, Member 5's ownership).

Confirmed with teammates:
  - Member 1: all pages of one lecture share one document_id and one
    lecture_date. Group by document_id, not by individual page/timestamp.
  - Member 4: show ALL topics tagged to a lecture, not just one -- picking a
    single "main" topic would make the other topics it also covers look like
    coverage gaps that don't actually exist.
  - Member 6: no separate subject field. Subject/unit context comes from
    joining note_topics -> Topic.syllabus_unit. lecture_date is a sortable
    ISO 8601 string (date or datetime), so plain string sort/comparison is
    reliable -- no date parsing needed.
"""
import pandas as pd

REQUIRED_NOTE_COLUMNS = {"id", "document_id", "lecture_date"}


def build_lecture_timeline(notes: pd.DataFrame, note_topics: pd.DataFrame | None,
                           topics: pd.DataFrame) -> dict:
    """One entry per lecture (document_id), sorted chronologically by
    lecture_date, each carrying every topic tagged to any of its pages plus
    the syllabus units those topics belong to.

    Lectures with no lecture_date on any page go into `unscheduled` instead
    of the sorted `timeline`. If a lecture's pages disagree on lecture_date
    (a data-quality issue upstream), the earliest date is used and the
    conflict is reported in `data_quality.date_conflicts`.
    """
    missing = REQUIRED_NOTE_COLUMNS - set(notes.columns)
    if missing:
        raise ValueError(f"'notes' table is missing columns: {sorted(missing)}")

    topics_idx = topics.set_index("id")[["name", "syllabus_unit"]]

    nt = note_topics if note_topics is not None else pd.DataFrame(columns=["note_id", "topic_id"])
    note_to_topics = nt.groupby("note_id")["topic_id"].apply(list).to_dict()

    scheduled, unscheduled, date_conflicts = [], [], []

    for doc_id, group in notes.groupby("document_id"):
        doc_id = doc_id.item() if hasattr(doc_id, "item") else doc_id
        dates = sorted(d for d in group["lecture_date"].dropna().unique().tolist())

        if len(dates) == 0:
            canonical_date = None
        elif len(dates) == 1:
            canonical_date = dates[0]
        else:
            canonical_date = dates[0]                      # earliest; ISO strings sort correctly
            date_conflicts.append({"document_id": doc_id, "dates_found": dates})

        topic_ids = sorted({int(tid) for nid in group["id"] for tid in note_to_topics.get(nid, [])})
        topic_entries, syllabus_units = [], []
        for tid in topic_ids:
            if tid in topics_idx.index:
                name = topics_idx.loc[tid, "name"]
                unit = topics_idx.loc[tid, "syllabus_unit"]
                topic_entries.append({"topic_id": tid, "name": name, "syllabus_unit": unit})
                if unit not in syllabus_units:
                    syllabus_units.append(unit)

        entry = {
            "document_id": doc_id,
            "lecture_date": canonical_date,
            "n_pages": int(len(group)),
            "topics": topic_entries,
            "syllabus_units": sorted(syllabus_units),
        }
        (unscheduled if canonical_date is None else scheduled).append(entry)

    scheduled.sort(key=lambda e: e["lecture_date"])

    return {
        "timeline": scheduled,
        "unscheduled": unscheduled,
        "data_quality": {
            "n_lectures": len(scheduled) + len(unscheduled),
            "n_unscheduled": len(unscheduled),
            "n_date_conflicts": len(date_conflicts),
            "date_conflicts": date_conflicts,
        },
    }
